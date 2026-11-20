// The whole pipeline for one camera, one frame at a time.
// A C++ copy of TrayCapPipeline in vision/tray_object_pipeline.py.
#pragma once

#include <stdio.h>

#include "tc_caps.h"
#include "tc_tray.h"
#include "tc_types.h"

namespace tc {

// What one frame produced.
struct FrameResult {
  uint8_t state = NOT_FOUND;   // SETTLING, NOT_FOUND, FINDING or LOCKED
  bool has_outline = false;
  Quad outline;                // the tray corners used (when has_outline)
  int cap_count = 0;
  Cap caps[MAX_CAPS];          // the steady caps
  int straight_w = 0, straight_h = 0;
  int tray_brightness = 0, cap_min_brightness = 0;
  // For the debug line: what the tray search saw (only on frames where it ran), and
  // how many caps of each color were found before the tracker steadied them.
  bool tray_searched = false;
  TrayStats tray_stats;
  int raw_caps[3] = {0, 0, 0};
};

class Pipeline {
 public:
  explicit Pipeline(const Config& config = Config());
  bool begin(int frame_w, int frame_h);  // allocates all working pictures
  // Runs every step on one frame of frame_w x frame_h pixels, in the given pixel format.
  void process(const uint8_t* frame, PixelFormat format, uint32_t now_ms, FrameResult& result);
  // The same, for an ESP32-CAM frame (RGB565, high byte first).
  void process(const uint8_t* frame, uint32_t now_ms, FrameResult& result) {
    process(frame, RGB565_BE, now_ms, result);
  }
  void reset_tray();                     // forget the locked outline and search again
  Config& config() { return config_; }
  const uint8_t* dark_picture() const { return finder_.dark_picture(); }
  // For debugging views: the straightened tray of the last frame, and the color masks on it.
  const Straight& straight() const { return straight_; }
  const uint8_t* color_mask(int color) const { return cap_finder_.mask(color); }

 private:
  Config config_;
  int w_, h_;
  TrayFinder finder_;
  Smoother smoother_;
  Lock lock_;
  Straight straight_;
  CapFinder cap_finder_;
  Tracker tracker_;
  bool settling_;
  uint32_t settle_until_;
  bool has_last_check_;
  uint32_t last_check_;
};

// Writes the result as one line of JSON, like the Python program's --no-gui output:
// {"frame": 12, "time_ms": 1730000000000, "tray": "locked", "caps": [{...}]}
// Returns the number of characters (without the end of line), or -1 if the buffer is too small.
int result_to_json(char* buffer, int size, uint32_t frame_number, uint64_t time_ms,
                   const FrameResult& result);

// Writes one line of numbers that explain the result, for people (not JSON):
// # debug: dark 23.4%, shapes 5 (small 3, edge 1, shape 0, tray-like 1) | tray 412x260, ...
// Programs that read the results skip it, because it starts with #.
// Returns the number of characters, or -1 if the buffer is too small.
int debug_to_text(char* buffer, int size, const FrameResult& result);

}  // namespace tc
