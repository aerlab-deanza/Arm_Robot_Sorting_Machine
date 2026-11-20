#include "tc_pipeline.h"

#include <inttypes.h>
#include <string.h>

namespace tc {

Pipeline::Pipeline(const Config& config)
    : config_(config), w_(0), h_(0), settling_(false), settle_until_(0), has_last_check_(false), last_check_(0) {}

bool Pipeline::begin(int frame_w, int frame_h) {
  w_ = frame_w;
  h_ = frame_h;
  if (w_ > MAX_W || h_ > MAX_H) return false;
  return finder_.begin(w_, h_) && straight_.begin() && cap_finder_.begin();
}

void Pipeline::reset_tray() {
  lock_.reset();
  smoother_.reset();
  tracker_.reset();
}

void Pipeline::process(const uint8_t* frame, PixelFormat format, uint32_t now_ms, FrameResult& result) {
  result = FrameResult();
  const float diagonal = sqrtf((float)w_ * w_ + (float)h_ * h_);

  // While the outline is locked, look for the tray only every locked_check_seconds.
  const bool search_tray = !lock_.locked() || !has_last_check_ ||
                           (now_ms - last_check_) / 1000.0f >= config_.locked_check_seconds;
  Quad detected;
  bool have_detected = false;
  if (search_tray) {
    have_detected = finder_.find(frame, format, config_, detected);
    result.tray_searched = true;
    result.tray_stats = finder_.stats();
    last_check_ = now_ms;
    has_last_check_ = true;
  }

  // First sighting: wait a moment before trusting the tray.
  if (!smoother_.has_outline() && !lock_.locked() && have_detected && !settling_ &&
      config_.settle_seconds > 0) {
    settling_ = true;
    settle_until_ = now_ms + (uint32_t)(config_.settle_seconds * 1000.0f);
  }
  if (settling_) {
    if ((int32_t)(settle_until_ - now_ms) > 0) {
      result.state = SETTLING;
      return;
    }
    settling_ = false;
  }

  Quad smoothed;
  bool have_smoothed = false;
  if (search_tray) have_smoothed = smoother_.update(have_detected ? &detected : nullptr, diagonal, smoothed);

  Quad tray;
  bool moved = false;
  const bool have_tray = lock_.update(have_smoothed ? &smoothed : nullptr, have_detected ? &detected : nullptr,
                                      diagonal, now_ms, config_, tray, moved);
  if (moved) {
    smoother_.set_outline(tray);
    tracker_.reset();
  }
  if (!have_tray) {
    tracker_.reset();
    result.state = NOT_FOUND;
    return;
  }
  result.has_outline = true;
  result.outline = tray;
  result.state = lock_.locked() ? LOCKED : FINDING;

  if (!straighten(frame, format, w_, h_, tray, straight_)) return;
  result.straight_w = straight_.w;
  result.straight_h = straight_.h;

  Cap found[MAX_CAPS];
  const int n = cap_finder_.find(straight_, config_, found, result.tray_brightness, result.cap_min_brightness);
  for (int i = 0; i < n; i++) result.raw_caps[found[i].color]++;
  result.cap_count = tracker_.update(found, n, result.caps);
}

int debug_to_text(char* buffer, int size, const FrameResult& result) {
  int used = 0;
  int n;
  if (result.tray_searched) {
    const TrayStats& s = result.tray_stats;
    n = snprintf(buffer, size,
                 "# debug: limit V<=%d, dark %d.%d%%, shapes %d (small %d, edge %d, shape %d, tray-like %d), "
                 "cover %d%%, grey edge %d%%",
                 s.dark_limit, s.dark_percent_x10 / 10, s.dark_percent_x10 % 10, s.shapes, s.too_small, s.at_edge,
                 s.wrong_shape, s.tray_like, s.cover_percent, s.grey_edge_percent);
  } else {
    n = snprintf(buffer, size, "# debug: tray search skipped (locked, checks every few frames)");
  }
  if (n < 0 || n >= size) return -1;
  used = n;
  if (result.straight_w > 0) {
    n = snprintf(buffer + used, size - used,
                 " | tray %dx%d, tray V %d, caps need V>=%d | raw caps red %d blue %d purple %d",
                 result.straight_w, result.straight_h, result.tray_brightness, result.cap_min_brightness,
                 result.raw_caps[RED], result.raw_caps[BLUE], result.raw_caps[PURPLE]);
    if (n < 0 || n >= size - used) return -1;
    used += n;
  }
  return used;
}

int result_to_json(char* buffer, int size, uint32_t frame_number, uint64_t time_ms,
                   const FrameResult& result) {
  int used = snprintf(buffer, size, "{\"frame\": %" PRIu32 ", \"time_ms\": %" PRIu64 ", \"tray\": \"%s\", \"caps\": [",
                      frame_number, time_ms, tray_state_name(result.state));
  if (used < 0 || used >= size) return -1;
  for (int i = 0; i < result.cap_count; i++) {
    const Cap& c = result.caps[i];
    const int n = snprintf(
        buffer + used, size - used,
        "%s{\"color\": \"%s\", \"u\": %.3f, \"v\": %.3f, \"center_x\": %.1f, \"center_y\": %.1f, "
        "\"box\": [%d, %d, %d, %d], \"area\": %d}",
        i ? ", " : "", color_name(c.color), c.u, c.v, c.cx, c.cy, c.bx, c.by, c.bw, c.bh, (int)(c.area + 0.5f));
    if (n < 0 || n >= size - used) return -1;
    used += n;
  }
  if (used + 3 > size) return -1;
  buffer[used++] = ']';
  buffer[used++] = '}';
  buffer[used] = 0;
  return used;
}

}  // namespace tc
