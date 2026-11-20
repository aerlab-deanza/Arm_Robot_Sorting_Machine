// Finding the tray, steadying and locking its outline, and straightening it.
// A C++ copy of vision/tray.py.
#pragma once

#include "tc_image.h"
#include "tc_types.h"

namespace tc {

// Put four corner points in the order top-left, top-right, bottom-right, bottom-left.
Quad order_corners(const Point* points);

// Reduce a convex outline to its 4 most important corners: while there are more than 4,
// remove the one whose triangle with its two neighbors is the smallest. A thin spike
// (a cable) makes a small triangle, so it goes first. (Task 1 in docs/task_delegation.md.)
int four_main_corners(const Point* hull, int count, Point* out4);

// Smallest rotated rectangle around a convex outline. Returns its width and height,
// and its four corners in `corners`.
void min_area_rect(const Point* hull, int count, float& width, float& height, Point* corners);

// Mean distance between matching corners.
float corner_distance(const Quad& a, const Quad& b);

// What the last tray search saw. Printed in the debug line, to explain why a tray
// was or was not found.
struct TrayStats {
  int dark_percent_x10 = 0;  // dark pixels, in tenths of a percent of the search area
  int shapes = 0;            // dark shapes found (after filling gaps)
  int too_small = 0;         // smaller than tray_min_area_ratio of the picture
  int at_edge = 0;           // touching the picture edge or the search region edge
  int wrong_shape = 0;       // failed the aspect, rectangularity or corner checks
  int tray_like = 0;         // passed every check (the best one is used)
  int dark_limit = 0;        // the brightness limit used for dark pixels
  int cover_percent = 0;     // how much of the chosen outline is dark (0 when none)
  int grey_edge_percent = 0; // how grey the strip outside the outline is, worst side
};

// Finds the dark tray in a camera frame.
class TrayFinder {
 public:
  TrayFinder();
  ~TrayFinder();
  bool begin(int width, int height);  // allocates the working pictures
  // Looks for the tray. On success fills `corners`. Strong light makes the black pad look
  // grey: then the brightness limit is raised in steps of LIMIT_STEP, from tray_max_value up
  // to tray_max_value_highest, until the outline is clean: dark pixels fill MIN_COVER of it,
  // and on every side at most MAX_GREY_EDGE of the strip just outside it is grey (like
  // find_tray_corners_any_light() in tray.py). In normal light an early try is clean.
  bool find(const uint8_t* frame, PixelFormat format, const Config& config, Quad& corners);
  static constexpr int LIMIT_STEP = 15;
  static constexpr float MIN_COVER = 0.80f;
  static constexpr float MAX_GREY_EDGE = 0.30f;
  static constexpr int EDGE_WIDTH = 4;  // pixels
  const uint8_t* dark_picture() const { return mask_; }
  const TrayStats& stats() const { return stats_; }

 private:
  // One search with a fixed brightness limit.
  bool find_with_limit(const uint8_t* frame, PixelFormat format, const Config& config, int limit,
                       Quad& corners);
  // How much of the outline is filled with dark pixels (0 to 1), from the last search.
  float outline_cover(const Quad& corners) const;
  // How grey the strip just outside the outline is on its greyest side: the share of
  // pixels brighter than `limit` but not brighter than `highest` (0 to 1). Uses the working
  // pictures, so call it after the search.
  float grey_edge(const uint8_t* frame, PixelFormat format, const Quad& corners, int limit, int highest);
  int w_, h_;
  TrayStats stats_;
  uint8_t* mask_;
  uint8_t* scratch1_;
  uint8_t* scratch2_;
  uint16_t* labels_;
};

// Steadies the tray corners across frames (see TrayOutlineSmoother in tray.py).
class Smoother {
 public:
  Smoother() { reset(); }
  void reset();
  // `detected` may be null (tray not seen). Returns true and fills `out` when there is an outline.
  bool update(const Quad* detected, float diagonal, Quad& out);
  bool has_outline() const { return has_; }
  void set_outline(const Quad& q) { outline_ = q; has_ = true; }

 private:
  bool has_;
  Quad outline_;
  int missed_;
  bool has_pending_;
  Quad pending_;
  int pending_frames_;
  float weight_;
  int hold_frames_;
  int confirm_frames_;
};

// Locks the outline once it has been still (see TrayLock in tray.py).
class Lock {
 public:
  Lock() { reset(); }
  void reset();
  bool locked() const { return locked_; }
  // Returns true and fills `out` when there is an outline to use. `moved` is set on the
  // frame where the lock opens because the tray really moved.
  bool update(const Quad* smoothed, const Quad* detected, float diagonal, uint32_t now_ms,
              const Config& config, Quad& out, bool& moved);
  // Seconds left before the lock closes, or -1 if not counting.
  float seconds_to_lock(uint32_t now_ms, const Config& config) const;

 private:
  bool locked_;
  Quad locked_corners_;
  bool still_;
  Quad still_corners_;
  uint32_t still_since_;
  bool moving_;
  Quad moved_corners_;
  uint32_t moved_since_;
};

// Straightened tray picture, as three byte pictures: hue, saturation, value.
struct Straight {
  int w = 0, h = 0;
  uint8_t* hue = nullptr;
  uint8_t* sat = nullptr;
  uint8_t* val = nullptr;
  bool begin();  // allocates MAX_W x MAX_H for each
  void end();
};

// Warps the tray into a top-down rectangle. The output size is the tray's longest
// top/bottom side and left/right side, like straighten_tray() in tray.py.
// Uses the nearest pixel (the Python version blends neighbors).
bool straighten(const uint8_t* frame, PixelFormat format, int frame_w, int frame_h, const Quad& tray,
                Straight& out);

}  // namespace tc
