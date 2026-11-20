// Finding red, blue and purple caps on the straightened tray, and steadying them.
// A C++ copy of vision/caps.py.
#pragma once

#include "tc_image.h"
#include "tc_tray.h"
#include "tc_types.h"

namespace tc {

// Finds caps by color. Keeps its working pictures between frames.
class CapFinder {
 public:
  CapFinder();
  ~CapFinder();
  bool begin();  // allocates the working pictures
  // Looks for caps in the straightened tray. Returns how many (at most MAX_CAPS),
  // biggest first. `tray_brightness` and `cap_min_brightness` are for debugging.
  // The cleaned-up mask of one color (RED, BLUE, PURPLE) from the last find(), for debugging.
  // Size is the straightened tray (w x h), 255 = that color.
  const uint8_t* mask(int color) const { return mask_[color]; }
  int find(const Straight& tray, const Config& config, Cap* caps, int& tray_brightness,
           int& cap_min_brightness);

 private:
  uint8_t* mask_[3];
  uint8_t* scratch1_;
  uint8_t* scratch2_;
  uint16_t* labels_;
};

// Shows a cap only after it was seen in `min_hits` of the last `window` frames, and
// reports the median box and center of its recent detections (ObjectTracker in caps.py).
class Tracker {
 public:
  Tracker() { reset(); }
  void reset() { count_ = 0; }
  // `caps` are this frame's detections. Fills `steady` and returns how many.
  int update(const Cap* caps, int n, Cap* steady);

 private:
  static constexpr int WINDOW = 5;
  static constexpr int MIN_HITS = 3;
  static constexpr int MAX_TRACKS = 24;
  struct Track {
    uint8_t color;
    int recent_count;
    Cap recent[WINDOW];
    int seen_count;
    bool seen[WINDOW];
  };
  Track tracks_[MAX_TRACKS];
  int count_;
};

}  // namespace tc
