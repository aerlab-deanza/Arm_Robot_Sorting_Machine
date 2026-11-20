#include "tc_tray.h"

#include <string.h>

namespace tc {

// ---------------------------------------------------------------- geometry

Quad order_corners(const Point* points) {
  float cx = 0, cy = 0;
  for (int i = 0; i < 4; i++) { cx += points[i].x; cy += points[i].y; }
  cx /= 4; cy /= 4;
  int order[4] = {0, 1, 2, 3};
  float angle[4];
  for (int i = 0; i < 4; i++) angle[i] = atan2f(points[i].y - cy, points[i].x - cx);
  for (int i = 1; i < 4; i++) {  // sort by angle (4 items: insertion sort)
    int j = i;
    while (j > 0 && angle[order[j - 1]] > angle[order[j]]) {
      const int t = order[j]; order[j] = order[j - 1]; order[j - 1] = t;
      j--;
    }
  }
  int top_left = 0;
  float best = points[order[0]].x + points[order[0]].y;
  for (int i = 1; i < 4; i++) {
    const float s = points[order[i]].x + points[order[i]].y;
    if (s < best) { best = s; top_left = i; }
  }
  Quad q;
  for (int i = 0; i < 4; i++) q.p[i] = points[order[(top_left + i) % 4]];
  return q;
}

namespace {

float cross(const Point& o, const Point& a, const Point& b) {
  return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
}

// Convex hull (monotone chain). `pts` is sorted and reused. Returns the hull size.
int convex_hull(Point* pts, int n, Point* hull) {
  // sort by x, then y (insertion sort is fine for the few hundred points we have)
  for (int i = 1; i < n; i++) {
    const Point key = pts[i];
    int j = i - 1;
    while (j >= 0 && (pts[j].x > key.x || (pts[j].x == key.x && pts[j].y > key.y))) {
      pts[j + 1] = pts[j];
      j--;
    }
    pts[j + 1] = key;
  }
  int k = 0;
  for (int i = 0; i < n; i++) {
    while (k >= 2 && cross(hull[k - 2], hull[k - 1], pts[i]) <= 0) k--;
    hull[k++] = pts[i];
  }
  for (int i = n - 2, t = k + 1; i >= 0; i--) {
    while (k >= t && cross(hull[k - 2], hull[k - 1], pts[i]) <= 0) k--;
    hull[k++] = pts[i];
  }
  return k - 1;
}

float polygon_area(const Point* p, int n) {
  float a = 0;
  for (int i = 0; i < n; i++) {
    const Point& q = p[i];
    const Point& r = p[(i + 1) % n];
    a += q.x * r.y - r.x * q.y;
  }
  return fabsf(a) * 0.5f;
}

}  // namespace

int four_main_corners(const Point* hull, int count, Point* out4) {
  static Point work[2 * (MAX_W + MAX_H) + 8];
  int n = count;
  for (int i = 0; i < n; i++) work[i] = hull[i];
  while (n > 4) {
    int smallest = 0;
    float smallest_area = 1e30f;
    for (int i = 0; i < n; i++) {
      const Point& before = work[(i + n - 1) % n];
      const Point& after = work[(i + 1) % n];
      const float area = fabsf((work[i].x - before.x) * (after.y - before.y) -
                               (after.x - before.x) * (work[i].y - before.y)) * 0.5f;
      if (area < smallest_area) { smallest_area = area; smallest = i; }
    }
    for (int i = smallest; i < n - 1; i++) work[i] = work[i + 1];
    n--;
  }
  for (int i = 0; i < n; i++) out4[i] = work[i];
  return n;
}

void min_area_rect(const Point* hull, int count, float& width, float& height, Point* corners) {
  float best_area = 1e30f;
  width = height = 0;
  for (int e = 0; e < count; e++) {
    const Point& a = hull[e];
    const Point& b = hull[(e + 1) % count];
    float dx = b.x - a.x, dy = b.y - a.y;
    const float len = sqrtf(dx * dx + dy * dy);
    if (len < 1e-6f) continue;
    dx /= len; dy /= len;
    float min_a = 1e30f, max_a = -1e30f, min_b = 1e30f, max_b = -1e30f;
    for (int i = 0; i < count; i++) {
      const float along = (hull[i].x - a.x) * dx + (hull[i].y - a.y) * dy;
      const float across = -(hull[i].x - a.x) * dy + (hull[i].y - a.y) * dx;
      if (along < min_a) min_a = along;
      if (along > max_a) max_a = along;
      if (across < min_b) min_b = across;
      if (across > max_b) max_b = across;
    }
    const float area = (max_a - min_a) * (max_b - min_b);
    if (area < best_area) {
      best_area = area;
      width = max_a - min_a;
      height = max_b - min_b;
      if (corners) {
        const float al[4] = {min_a, max_a, max_a, min_a};
        const float ac[4] = {min_b, min_b, max_b, max_b};
        for (int k = 0; k < 4; k++) {
          corners[k].x = a.x + al[k] * dx - ac[k] * dy;
          corners[k].y = a.y + al[k] * dy + ac[k] * dx;
        }
      }
    }
  }
}

float corner_distance(const Quad& a, const Quad& b) {
  float total = 0;
  for (int i = 0; i < 4; i++) {
    const float dx = a.p[i].x - b.p[i].x, dy = a.p[i].y - b.p[i].y;
    total += sqrtf(dx * dx + dy * dy);
  }
  return total / 4.0f;
}

namespace {

void side_lengths(const Quad& q, float* out) {
  for (int i = 0; i < 4; i++) {
    const Point& a = q.p[i];
    const Point& b = q.p[(i + 1) % 4];
    out[i] = sqrtf((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
  }
}

// Same-size tray, clearly moved? (tray_moved in tray.py)
bool tray_moved(const Quad& locked, const Quad& now, float diagonal) {
  if (corner_distance(locked, now) < 0.05f * diagonal) return false;
  float a[4], b[4];
  side_lengths(locked, a);
  side_lengths(now, b);
  for (int i = 0; i < 4; i++) {
    const float ratio = b[i] / (a[i] > 1.0f ? a[i] : 1.0f);
    if (fabsf(ratio - 1.0f) > 0.15f) return false;
  }
  return true;
}

}  // namespace

// ---------------------------------------------------------------- finding the tray

TrayFinder::TrayFinder() : w_(0), h_(0), mask_(nullptr), scratch1_(nullptr), scratch2_(nullptr), labels_(nullptr) {}

TrayFinder::~TrayFinder() {
  release(mask_); release(scratch1_); release(scratch2_); release(labels_);
}

bool TrayFinder::begin(int width, int height) {
  w_ = width; h_ = height;
  const size_t n = (size_t)width * height;
  mask_ = (uint8_t*)alloc(n);
  scratch1_ = (uint8_t*)alloc(n);
  scratch2_ = (uint8_t*)alloc(n);
  labels_ = (uint16_t*)alloc(n * sizeof(uint16_t));
  return mask_ && scratch1_ && scratch2_ && labels_;
}

bool TrayFinder::find(const uint8_t* frame, PixelFormat format, const Config& config, Quad& corners) {
  const int highest = config.tray_max_value_highest;
  bool have_found = false, have_filled = false;
  int found_limit = config.tray_max_value, filled_limit = config.tray_max_value;
  Quad first_found, first_filled;
  for (int limit = config.tray_max_value; limit <= highest || limit == config.tray_max_value;
       limit += LIMIT_STEP) {
    Quad outline;
    if (find_with_limit(frame, format, config, limit, outline)) {
      if (!have_found) { have_found = true; first_found = outline; found_limit = limit; }
      const float cover = outline_cover(outline);
      if (cover >= MIN_COVER) {
        if (!have_filled) { have_filled = true; first_filled = outline; filled_limit = limit; }
        const float grey = grey_edge(frame, format, outline, limit, highest);
        if (grey <= MAX_GREY_EDGE) {
          stats_.cover_percent = (int)(cover * 100.0f + 0.5f);
          stats_.grey_edge_percent = (int)(grey * 100.0f + 0.5f);
          corners = outline;
          return true;
        }
      }
    }
    if (limit + LIMIT_STEP > highest) break;
  }
  // No clean outline. Search again with the chosen limit, so the dark picture and the
  // debug numbers match what is used.
  Quad outline;
  if (!have_found) {
    find_with_limit(frame, format, config, config.tray_max_value, outline);  // the usual dark picture
    return false;
  }
  const int limit = have_filled ? filled_limit : found_limit;
  find_with_limit(frame, format, config, limit, outline);
  corners = have_filled ? first_filled : first_found;
  stats_.cover_percent = (int)(outline_cover(corners) * 100.0f + 0.5f);
  stats_.grey_edge_percent = (int)(grey_edge(frame, format, corners, limit, highest) * 100.0f + 0.5f);
  return true;
}

float TrayFinder::grey_edge(const uint8_t* frame, PixelFormat format, const Quad& q, int limit, int highest) {
  // The outline as a filled picture (in the labels memory, free after the search).
  uint8_t* inside = (uint8_t*)labels_;
  const size_t n = (size_t)w_ * h_;
  for (size_t i = 0; i < n; i++) inside[i] = 0;
  float min_x = q.p[0].x, max_x = q.p[0].x, min_y = q.p[0].y, max_y = q.p[0].y;
  for (int i = 1; i < 4; i++) {
    min_x = fminf(min_x, q.p[i].x); max_x = fmaxf(max_x, q.p[i].x);
    min_y = fminf(min_y, q.p[i].y); max_y = fmaxf(max_y, q.p[i].y);
  }
  const int x0 = (int)fmaxf(0.f, floorf(min_x)), x1 = (int)fminf((float)w_ - 1, ceilf(max_x));
  const int y0 = (int)fmaxf(0.f, floorf(min_y)), y1 = (int)fminf((float)h_ - 1, ceilf(max_y));
  for (int y = y0; y <= y1; y++) {
    for (int x = x0; x <= x1; x++) {
      bool positive = false, negative = false;
      for (int i = 0; i < 4; i++) {
        const Point& a = q.p[i];
        const Point& b = q.p[(i + 1) % 4];
        const float cross = (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x);
        if (cross > 0) positive = true;
        if (cross < 0) negative = true;
      }
      if (!(positive && negative)) inside[y * w_ + x] = 255;
    }
  }
  // The strip: grown outline minus the outline.
  dilate(inside, scratch1_, scratch2_, w_, h_, EDGE_WIDTH);
  long strip[4] = {0, 0, 0, 0}, grey[4] = {0, 0, 0, 0};
  const int sx0 = x0 - EDGE_WIDTH < 0 ? 0 : x0 - EDGE_WIDTH, sx1 = x1 + EDGE_WIDTH >= w_ ? w_ - 1 : x1 + EDGE_WIDTH;
  const int sy0 = y0 - EDGE_WIDTH < 0 ? 0 : y0 - EDGE_WIDTH, sy1 = y1 + EDGE_WIDTH >= h_ ? h_ - 1 : y1 + EDGE_WIDTH;
  for (int y = sy0; y <= sy1; y++) {
    for (int x = sx0; x <= sx1; x++) {
      const int i = y * w_ + x;
      if (!scratch1_[i] || inside[i]) continue;
      // The side this strip pixel is nearest to.
      int side = 0;
      float nearest = 1e30f;
      for (int k = 0; k < 4; k++) {
        const Point& a = q.p[k];
        const Point& b = q.p[(k + 1) % 4];
        const float sx = b.x - a.x, sy = b.y - a.y;
        const float length2 = fmaxf(sx * sx + sy * sy, 1e-6f);
        float t = ((x - a.x) * sx + (y - a.y) * sy) / length2;
        t = fminf(1.f, fmaxf(0.f, t));
        const float dx = x - (a.x + t * sx), dy = y - (a.y + t * sy);
        const float d2 = dx * dx + dy * dy;
        if (d2 < nearest) { nearest = d2; side = k; }
      }
      strip[side]++;
      int r, g, b;
      read_rgb(frame, format, i, r, g, b);
      const int value = r > g ? (r > b ? r : b) : (g > b ? g : b);
      if (value > limit && value <= highest) grey[side]++;
    }
  }
  float worst = 0.f;
  for (int k = 0; k < 4; k++) {
    if (strip[k] > 0) worst = fmaxf(worst, (float)grey[k] / (float)strip[k]);
  }
  return worst;
}

float TrayFinder::outline_cover(const Quad& q) const {
  float min_x = q.p[0].x, max_x = q.p[0].x, min_y = q.p[0].y, max_y = q.p[0].y;
  for (int i = 1; i < 4; i++) {
    min_x = fminf(min_x, q.p[i].x); max_x = fmaxf(max_x, q.p[i].x);
    min_y = fminf(min_y, q.p[i].y); max_y = fmaxf(max_y, q.p[i].y);
  }
  const int x0 = (int)fmaxf(0.f, floorf(min_x)), x1 = (int)fminf((float)w_ - 1, ceilf(max_x));
  const int y0 = (int)fmaxf(0.f, floorf(min_y)), y1 = (int)fminf((float)h_ - 1, ceilf(max_y));
  long inside = 0, dark = 0;
  for (int y = y0; y <= y1; y++) {
    for (int x = x0; x <= x1; x++) {
      // Inside a convex outline: on the same side of all four edges.
      bool positive = false, negative = false;
      for (int i = 0; i < 4; i++) {
        const Point& a = q.p[i];
        const Point& b = q.p[(i + 1) % 4];
        const float cross = (b.x - a.x) * (y - a.y) - (b.y - a.y) * (x - a.x);
        if (cross > 0) positive = true;
        if (cross < 0) negative = true;
      }
      if (positive && negative) continue;
      inside++;
      if (mask_[y * w_ + x]) dark++;
    }
  }
  return inside > 0 ? (float)dark / (float)inside : 0.f;
}

bool TrayFinder::find_with_limit(const uint8_t* frame, PixelFormat format, const Config& config, int limit,
                                 Quad& corners) {
  int left = 0, top = 0, right = w_, bottom = h_;
  if (config.use_region) {
    left = (int)(config.region[0] * w_); top = (int)(config.region[1] * h_);
    right = (int)(config.region[2] * w_); bottom = (int)(config.region[3] * h_);
  }
  stats_ = TrayStats();
  stats_.dark_limit = limit;
  long dark_count = 0;
  // 1. Dark pixels (and only inside the search region).
  for (int y = 0; y < h_; y++) {
    for (int x = 0; x < w_; x++) {
      uint8_t value = 0;
      if (x >= left && x < right && y >= top && y < bottom) {
        int r, g, b;
        read_rgb(frame, format, y * w_ + x, r, g, b);
        const int mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
        bool dark = mx <= limit;
        if (dark && config.tray_max_saturation < 255) {
          uint8_t hh, ss, vv;
          rgb_to_hsv(r, g, b, hh, ss, vv);
          dark = ss <= config.tray_max_saturation;
        }
        value = dark ? 255 : 0;
        if (dark) dark_count++;
      }
      mask_[y * w_ + x] = value;
    }
  }
  const long search_area = (long)(right - left) * (bottom - top);
  if (search_area > 0) stats_.dark_percent_x10 = (int)(dark_count * 1000 / search_area);
  // 2. Fill small gaps.
  close_mask(mask_, scratch1_, scratch2_, w_, h_, config.close_radius);

  // 3. Blobs, and the best tray-like one.
  Blob blobs[MAX_BLOBS + 1];
  const int count = find_blobs(mask_, labels_, w_, h_, blobs);
  stats_.shapes = count;
  const float frame_area = (float)w_ * h_;
  const int border = (int)fmaxf(4.f, floorf(fminf((float)w_, (float)h_) * 0.008f));
  float best_score = -1;
  bool found = false;

  static int row_min[MAX_H], row_max[MAX_H], col_min[MAX_W], col_max[MAX_W];
  static Point points[2 * (MAX_W + MAX_H) + 8];
  static Point hull[2 * (MAX_W + MAX_H) + 8];

  for (int id = 1; id <= count; id++) {
    const Blob& blob = blobs[id];
    const int bx = blob.min_x, by = blob.min_y;
    const int bw = blob.max_x - blob.min_x + 1, bh = blob.max_y - blob.min_y + 1;
    if ((float)blob.area / frame_area < config.tray_min_area_ratio) { stats_.too_small++; continue; }
    // A tray cut off by the frame (or by the search region) is unsafe to straighten.
    if (bx <= left + border || by <= top + border || bx + bw >= right - border ||
        by + bh >= bottom - border) { stats_.at_edge++; continue; }

    // Extreme points of the blob: leftmost / rightmost per row, top / bottom per column.
    for (int y = by; y < by + bh; y++) { row_min[y] = w_; row_max[y] = -1; }
    for (int x = bx; x < bx + bw; x++) { col_min[x] = h_; col_max[x] = -1; }
    float filled = 0;
    for (int y = by; y < by + bh; y++) {
      for (int x = bx; x < bx + bw; x++) {
        if (labels_[y * w_ + x] != id) continue;
        if (x < row_min[y]) row_min[y] = x;
        if (x > row_max[y]) row_max[y] = x;
        if (y < col_min[x]) col_min[x] = y;
        if (y > col_max[x]) col_max[x] = y;
      }
      if (row_max[y] >= 0) filled += row_max[y] - row_min[y] + 1;
    }
    int n = 0;
    for (int y = by; y < by + bh; y++) {
      if (row_max[y] < 0) continue;
      points[n++] = {(float)row_min[y], (float)y};
      points[n++] = {(float)row_max[y] + 1, (float)y};
    }
    for (int x = bx; x < bx + bw; x++) {
      if (col_max[x] < 0) continue;
      points[n++] = {(float)x, (float)col_min[x]};
      points[n++] = {(float)x, (float)col_max[x] + 1};
    }
    if (n < 3) { stats_.wrong_shape++; continue; }
    const int hn = convex_hull(points, n, hull);
    if (hn < 3) { stats_.wrong_shape++; continue; }

    float rect_w, rect_h;
    Point rect_corners[4];
    min_area_rect(hull, hn, rect_w, rect_h, rect_corners);
    const float short_side = fminf(rect_w, rect_h), long_side = fmaxf(rect_w, rect_h);
    if (short_side < 2) { stats_.wrong_shape++; continue; }
    const float aspect = long_side / short_side;
    const float rectangularity = filled / (rect_w * rect_h);
    if (aspect < 1.2f || aspect > 8.0f || rectangularity < 0.48f) { stats_.wrong_shape++; continue; }

    Quad candidate;
    Point four[4];
    const int fn = four_main_corners(hull, hn, four);
    if (fn == 4 && polygon_area(four, 4) >= 0.9f * polygon_area(hull, hn)) {
      candidate = order_corners(four);
    } else if (rectangularity >= 0.58f) {
      candidate = order_corners(rect_corners);
    } else {
      stats_.wrong_shape++;
      continue;
    }
    stats_.tray_like++;
    const float center_y = (by + bh * 0.5f) / h_;
    const float score = (filled / frame_area) * rectangularity * (0.8f + 0.2f * center_y);
    if (score > best_score) { best_score = score; corners = candidate; found = true; }
  }
  return found;
}

// ---------------------------------------------------------------- steady and lock

void Smoother::reset() {
  has_ = false; missed_ = 0; has_pending_ = false; pending_frames_ = 0;
  weight_ = 0.28f; hold_frames_ = 8; confirm_frames_ = 3;
}

bool Smoother::update(const Quad* detected, float diagonal, Quad& out) {
  if (detected == nullptr) {
    missed_++;
    if (has_ && missed_ <= hold_frames_) { out = outline_; return true; }
    has_ = false; has_pending_ = false; pending_frames_ = 0;
    return false;
  }
  Quad d = order_corners(detected->p);
  missed_ = 0;
  if (!has_) { outline_ = d; has_ = true; out = d; return true; }

  const float jump = corner_distance(d, outline_);
  if (jump > diagonal * 0.10f) {
    float to_pending = 1e30f;
    if (has_pending_) to_pending = corner_distance(d, pending_);
    if (to_pending <= diagonal * 0.035f) {
      for (int i = 0; i < 4; i++) {
        pending_.p[i].x = 0.5f * pending_.p[i].x + 0.5f * d.p[i].x;
        pending_.p[i].y = 0.5f * pending_.p[i].y + 0.5f * d.p[i].y;
      }
      pending_frames_++;
    } else {
      pending_ = d; has_pending_ = true; pending_frames_ = 1;
    }
    if (pending_frames_ < confirm_frames_) { out = outline_; return true; }
    outline_ = d; has_pending_ = false; pending_frames_ = 0;
    out = outline_;
    return true;
  }
  has_pending_ = false; pending_frames_ = 0;
  for (int i = 0; i < 4; i++) {
    outline_.p[i].x = (1.0f - weight_) * outline_.p[i].x + weight_ * d.p[i].x;
    outline_.p[i].y = (1.0f - weight_) * outline_.p[i].y + weight_ * d.p[i].y;
  }
  out = outline_;
  return true;
}

void Lock::reset() {
  locked_ = false; still_ = false; still_since_ = 0; moving_ = false; moved_since_ = 0;
}

float Lock::seconds_to_lock(uint32_t now_ms, const Config& config) const {
  if (locked_ || !still_) return -1.0f;
  const float left = config.lock_seconds - (now_ms - still_since_) / 1000.0f;
  return left < 0 ? 0 : left;
}

bool Lock::update(const Quad* smoothed, const Quad* detected, float diagonal, uint32_t now_ms,
                  const Config& config, Quad& out, bool& moved) {
  moved = false;
  if (!locked_) {
    if (smoothed == nullptr) { still_ = false; return false; }
    const bool moved_since_still = !still_ || corner_distance(*smoothed, still_corners_) > 0.015f * diagonal;
    if (moved_since_still) {
      still_corners_ = *smoothed; still_ = true; still_since_ = now_ms;
    } else if ((now_ms - still_since_) / 1000.0f >= config.lock_seconds) {
      locked_ = true; locked_corners_ = *smoothed;
    }
    out = *smoothed;
    return true;
  }
  // Locked: watch the raw detections for a tray that really moved.
  if (detected != nullptr) {
    const Quad now = order_corners(detected->p);
    if (tray_moved(locked_corners_, now, diagonal)) {
      const bool same_place = moving_ && corner_distance(now, moved_corners_) <= 0.02f * diagonal;
      if (!same_place) {
        moved_corners_ = now; moved_since_ = now_ms; moving_ = true;
      } else if ((now_ms - moved_since_) / 1000.0f >= config.move_seconds) {
        reset();
        out = now; moved = true;
        return true;
      }
    } else {
      moving_ = false;
    }
  }
  out = locked_corners_;
  return true;
}

// ---------------------------------------------------------------- straightening

bool Straight::begin() {
  const size_t n = (size_t)MAX_W * MAX_H;
  hue = (uint8_t*)alloc(n); sat = (uint8_t*)alloc(n); val = (uint8_t*)alloc(n);
  return hue && sat && val;
}

void Straight::end() {
  release(hue); release(sat); release(val);
  hue = sat = val = nullptr;
}

namespace {

// Solve for the 8 numbers of the map (x, y) -> (X, Y) that sends 4 points to 4 points.
bool solve_homography(const Point* from, const Point* to, double* h) {
  double a[8][9];
  for (int i = 0; i < 4; i++) {
    const double x = from[i].x, y = from[i].y, X = to[i].x, Y = to[i].y;
    const double r1[9] = {x, y, 1, 0, 0, 0, -X * x, -X * y, X};
    const double r2[9] = {0, 0, 0, x, y, 1, -Y * x, -Y * y, Y};
    for (int k = 0; k < 9; k++) { a[2 * i][k] = r1[k]; a[2 * i + 1][k] = r2[k]; }
  }
  for (int col = 0; col < 8; col++) {
    int pivot = col;
    for (int r = col + 1; r < 8; r++) if (fabs(a[r][col]) > fabs(a[pivot][col])) pivot = r;
    if (fabs(a[pivot][col]) < 1e-12) return false;
    for (int k = 0; k < 9; k++) { const double t = a[col][k]; a[col][k] = a[pivot][k]; a[pivot][k] = t; }
    for (int r = 0; r < 8; r++) {
      if (r == col) continue;
      const double f = a[r][col] / a[col][col];
      for (int k = col; k < 9; k++) a[r][k] -= f * a[col][k];
    }
  }
  for (int i = 0; i < 8; i++) h[i] = a[i][8] / a[i][i];
  return true;
}

}  // namespace

bool straighten(const uint8_t* frame, PixelFormat format, int frame_w, int frame_h, const Quad& tray,
                Straight& out) {
  const Point* c = tray.p;
  auto dist = [](const Point& a, const Point& b) {
    return sqrtf((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
  };
  int w = (int)fmaxf(dist(c[2], c[3]), dist(c[1], c[0]));
  int h = (int)fmaxf(dist(c[1], c[2]), dist(c[0], c[3]));
  if (w < 2) w = 2;
  if (h < 2) h = 2;
  if (w > MAX_W) w = MAX_W;
  if (h > MAX_H) h = MAX_H;
  const Point target[4] = {{0, 0}, {(float)(w - 1), 0}, {(float)(w - 1), (float)(h - 1)}, {0, (float)(h - 1)}};
  double m[8];
  if (!solve_homography(target, tray.p, m)) return false;
  out.w = w; out.h = h;
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      const double denom = m[6] * x + m[7] * y + 1.0;
      const double sx = (m[0] * x + m[1] * y + m[2]) / denom;
      const double sy = (m[3] * x + m[4] * y + m[5]) / denom;
      const int px = (int)floor(sx + 0.5), py = (int)floor(sy + 0.5);
      const int i = y * w + x;
      if (px < 0 || py < 0 || px >= frame_w || py >= frame_h) {
        out.hue[i] = out.sat[i] = out.val[i] = 0;
        continue;
      }
      int r, g, b;
      read_rgb(frame, format, py * frame_w + px, r, g, b);
      rgb_to_hsv(r, g, b, out.hue[i], out.sat[i], out.val[i]);
    }
  }
  return true;
}

}  // namespace tc
