#include "tc_caps.h"

#include <string.h>

namespace tc {

CapFinder::CapFinder() : scratch1_(nullptr), scratch2_(nullptr), labels_(nullptr) {
  mask_[0] = mask_[1] = mask_[2] = nullptr;
}

CapFinder::~CapFinder() {
  for (int i = 0; i < 3; i++) release(mask_[i]);
  release(scratch1_); release(scratch2_); release(labels_);
}

bool CapFinder::begin() {
  const size_t n = (size_t)MAX_W * MAX_H;
  bool ok = true;
  for (int i = 0; i < 3; i++) { mask_[i] = (uint8_t*)alloc(n); ok = ok && mask_[i]; }
  scratch1_ = (uint8_t*)alloc(n);
  scratch2_ = (uint8_t*)alloc(n);
  labels_ = (uint16_t*)alloc(n * sizeof(uint16_t));
  return ok && scratch1_ && scratch2_ && labels_;
}

namespace {

// Median of the brightness (like np.median followed by int()).
int median_value(const uint8_t* val, int n) {
  int histogram[256] = {0};
  for (int i = 0; i < n; i++) histogram[val[i]]++;
  const int lower_index = (n - 1) / 2, upper_index = n / 2;
  int seen = 0, lower = 0, upper = 0;
  for (int v = 0; v < 256; v++) {
    const int before = seen;
    seen += histogram[v];
    if (before <= lower_index && lower_index < seen) lower = v;
    if (before <= upper_index && upper_index < seen) { upper = v; break; }
  }
  return (lower + upper) / 2;
}

struct Candidate {
  Cap cap;
};

float box_overlap_union(const Cap& a, const Cap& b, float& overlap_of_smaller) {
  const int left = a.bx > b.bx ? a.bx : b.bx, top = a.by > b.by ? a.by : b.by;
  const int right = (a.bx + a.bw) < (b.bx + b.bw) ? (a.bx + a.bw) : (b.bx + b.bw);
  const int bottom = (a.by + a.bh) < (b.by + b.bh) ? (a.by + a.bh) : (b.by + b.bh);
  const int iw = right - left > 0 ? right - left : 0, ih = bottom - top > 0 ? bottom - top : 0;
  const float inter = (float)iw * ih;
  const float area_a = (float)a.bw * a.bh, area_b = (float)b.bw * b.bh;
  const float uni = area_a + area_b - inter;
  const float smaller = area_a < area_b ? area_a : area_b;
  overlap_of_smaller = smaller > 0 ? inter / smaller : 0.f;
  return uni > 0 ? inter / uni : 0.f;
}

}  // namespace

int CapFinder::find(const Straight& tray, const Config& config, Cap* caps, int& tray_brightness,
                    int& cap_min_brightness) {
  const int w = tray.w, h = tray.h, n = w * h;
  tray_brightness = median_value(tray.val, n);
  int floor = tray_brightness + config.brightness_margin;
  if (floor < config.object_min_value) floor = config.object_min_value;
  if (floor > 255) floor = 255;
  cap_min_brightness = floor;

  // 1. Which pixels are red, blue or purple.
  for (int i = 0; i < n; i++) {
    const int hue = tray.hue[i], sat = tray.sat[i];
    uint8_t red = 0, blue = 0, purple = 0;
    if (tray.val[i] >= floor) {
      const bool red_in_purple_band = hue >= config.red_high_hue_min && hue <= config.purple_max_hue &&
                                      sat >= config.red_high_min_saturation;
      red = (((hue <= config.red_max_hue) || (hue > config.purple_max_hue)) &&
             sat >= config.red_min_saturation) || red_in_purple_band ? 255 : 0;
      blue = (hue >= config.blue_min_hue && hue <= config.blue_max_hue &&
              sat >= config.blue_min_saturation) ? 255 : 0;
      purple = (hue >= config.purple_min_hue && hue <= config.purple_max_hue &&
                sat >= config.object_min_saturation && !red_in_purple_band) ? 255 : 0;
    }
    mask_[RED][i] = red; mask_[BLUE][i] = blue; mask_[PURPLE][i] = purple;
  }

  // 2. Clean each color picture, then turn blobs into caps.
  static Cap found[MAX_CAPS * 3];
  int found_count = 0;
  const float minimum_area = (float)n * config.object_min_area_ratio;
  for (int color = 0; color < 3; color++) {
    open_mask(mask_[color], scratch1_, scratch2_, w, h, 2);   // remove specks
    close_mask(mask_[color], scratch1_, scratch2_, w, h, 2);  // fill small gaps
    Blob blobs[MAX_BLOBS + 1];
    const int blob_count = find_blobs(mask_[color], labels_, w, h, blobs);
    for (int id = 1; id <= blob_count; id++) {
      const Blob& b = blobs[id];
      if ((float)b.area < minimum_area) continue;
      const int bw = b.max_x - b.min_x + 1, bh = b.max_y - b.min_y + 1;
      const int small = bw < bh ? bw : bh, big = bw > bh ? bw : bh;
      if (small < config.object_min_side) continue;
      if ((float)big / (float)small > config.object_max_aspect) continue;
      Cap cap;
      cap.color = (uint8_t)color;
      cap.cx = (float)b.sum_x / b.area; cap.cy = (float)b.sum_y / b.area;
      cap.u = cap.cx / w; cap.v = cap.cy / h;
      cap.bx = b.min_x; cap.by = b.min_y; cap.bw = bw; cap.bh = bh;
      cap.area = (float)b.area;
      if (config.edge_margin > 0 &&
          !(cap.u >= config.edge_margin && cap.u <= 1 - config.edge_margin &&
            cap.v >= config.edge_margin && cap.v <= 1 - config.edge_margin)) continue;
      if (found_count < MAX_CAPS * 3) found[found_count++] = cap;
    }
  }

  // 3. Biggest first, then drop duplicates (small boxes inside a bigger one).
  for (int i = 1; i < found_count; i++) {
    const Cap key = found[i];
    int j = i - 1;
    while (j >= 0 && found[j].area < key.area) { found[j + 1] = found[j]; j--; }
    found[j + 1] = key;
  }
  int kept = 0;
  for (int i = 0; i < found_count && kept < MAX_CAPS; i++) {
    bool duplicate = false;
    for (int k = 0; k < kept; k++) {
      float overlap_of_smaller;
      const float iou = box_overlap_union(found[i], caps[k], overlap_of_smaller);
      if (iou >= 0.30f || overlap_of_smaller >= 0.75f) { duplicate = true; break; }
    }
    if (!duplicate) caps[kept++] = found[i];
  }
  return kept;
}

// ---------------------------------------------------------------- tracker

namespace {

float median_of(float* values, int n);

// Median of one number (u, box width, ...) over a cap's recent detections.
template <typename T>
float median_field(const Cap* recent, int count, T Cap::*member) {
  float values[8];
  for (int k = 0; k < count && k < 8; k++) values[k] = (float)(recent[k].*member);
  return median_of(values, count < 8 ? count : 8);
}

float median_of(float* values, int n) {
  for (int i = 1; i < n; i++) {
    const float key = values[i];
    int j = i - 1;
    while (j >= 0 && values[j] > key) { values[j + 1] = values[j]; j--; }
    values[j + 1] = key;
  }
  return n % 2 ? values[n / 2] : 0.5f * (values[n / 2 - 1] + values[n / 2]);
}

}  // namespace

int Tracker::update(const Cap* caps, int n, Cap* steady) {
  bool used[MAX_CAPS] = {false};
  for (int t = 0; t < count_; t++) {
    Track& track = tracks_[t];
    const Cap& last = track.recent[track.recent_count - 1];
    int best = -1;
    float best_distance = 0.08f;
    for (int i = 0; i < n; i++) {
      if (used[i] || caps[i].color != track.color) continue;
      const float du = caps[i].u - last.u, dv = caps[i].v - last.v;
      const float distance = sqrtf(du * du + dv * dv);
      if (distance <= best_distance) { best = i; best_distance = distance; }
    }
    if (best >= 0) {
      used[best] = true;
      if (track.recent_count == WINDOW) {
        for (int k = 1; k < WINDOW; k++) track.recent[k - 1] = track.recent[k];
        track.recent_count--;
      }
      track.recent[track.recent_count++] = caps[best];
    }
    if (track.seen_count == WINDOW) {
      for (int k = 1; k < WINDOW; k++) track.seen[k - 1] = track.seen[k];
      track.seen_count--;
    }
    track.seen[track.seen_count++] = best >= 0;
  }
  for (int i = 0; i < n; i++) {
    if (used[i] || count_ >= MAX_TRACKS) continue;
    Track& track = tracks_[count_++];
    track.color = caps[i].color;
    track.recent_count = 1; track.recent[0] = caps[i];
    track.seen_count = 1; track.seen[0] = true;
  }
  // Forget tracks that were not seen at all in the last WINDOW frames.
  int write = 0;
  for (int t = 0; t < count_; t++) {
    bool any = false;
    for (int k = 0; k < tracks_[t].seen_count; k++) any = any || tracks_[t].seen[k];
    if (any) tracks_[write++] = tracks_[t];
  }
  count_ = write;

  int out = 0;
  for (int t = 0; t < count_ && out < MAX_CAPS; t++) {
    const Track& track = tracks_[t];
    int hits = 0;
    for (int k = 0; k < track.seen_count; k++) hits += track.seen[k] ? 1 : 0;
    if (hits < MIN_HITS) continue;
    Cap cap;
    const int m = track.recent_count;
    cap.color = track.color;
    cap.cx = median_field(track.recent, m, &Cap::cx);
    cap.cy = median_field(track.recent, m, &Cap::cy);
    cap.u = median_field(track.recent, m, &Cap::u);
    cap.v = median_field(track.recent, m, &Cap::v);
    cap.area = median_field(track.recent, m, &Cap::area);
    cap.bx = (int)floorf(median_field(track.recent, m, &Cap::bx) + 0.5f);
    cap.by = (int)floorf(median_field(track.recent, m, &Cap::by) + 0.5f);
    cap.bw = (int)floorf(median_field(track.recent, m, &Cap::bw) + 0.5f);
    cap.bh = (int)floorf(median_field(track.recent, m, &Cap::bh) + 0.5f);
    steady[out++] = cap;
  }
  return out;
}

}  // namespace tc
