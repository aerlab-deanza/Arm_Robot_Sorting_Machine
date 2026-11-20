// A small C interface to the core, so Python (view_core.py) can run the exact board
// code on the PC and show its in-between pictures. Built as tc_core.dll by view_core.py.
#include <string.h>

#include "../tc_pipeline.h"

namespace {

struct Handle {
  tc::Pipeline pipeline;
  tc::FrameResult result;
  int w = 0, h = 0;
};

}  // namespace

extern "C" {

#if defined(_WIN32)
#define TC_API __declspec(dllexport)
#else
#define TC_API
#endif

// Creates a pipeline for w x h RGB888 pictures. Returns nullptr if it is too big.
TC_API void* tc_new(int w, int h, int min_side) {
  Handle* handle = new Handle();
  handle->pipeline.config().object_min_side = min_side;
  if (!handle->pipeline.begin(w, h)) {
    delete handle;
    return nullptr;
  }
  handle->w = w;
  handle->h = h;
  return handle;
}

TC_API void tc_free(void* p) { delete (Handle*)p; }

TC_API void tc_set_region(void* p, float left, float top, float right, float bottom) {
  tc::Config& config = ((Handle*)p)->pipeline.config();
  config.use_region = true;
  config.region[0] = left;
  config.region[1] = top;
  config.region[2] = right;
  config.region[3] = bottom;
}

TC_API void tc_reset_tray(void* p) { ((Handle*)p)->pipeline.reset_tray(); }

// Runs one frame. Writes the JSON line into `json` and the debug line into `debug`.
TC_API void tc_process(void* p, const uint8_t* rgb, uint32_t now_ms, uint32_t frame_number, char* json,
                       int json_size, char* debug, int debug_size) {
  Handle* handle = (Handle*)p;
  handle->pipeline.process(rgb, tc::RGB888, now_ms, handle->result);
  if (tc::result_to_json(json, json_size, frame_number, now_ms, handle->result) < 0 && json_size > 0) json[0] = 0;
  if (tc::debug_to_text(debug, debug_size, handle->result) < 0 && debug_size > 0) debug[0] = 0;
}

// The tray outline of the last frame: 8 numbers (x, y of 4 corners: top-left, top-right,
// bottom-right, bottom-left). Returns 1 if there is one, else 0.
TC_API int tc_outline(void* p, float* xy) {
  const tc::FrameResult& r = ((Handle*)p)->result;
  if (!r.has_outline) return 0;
  for (int i = 0; i < 4; i++) {
    xy[2 * i] = r.outline.p[i].x;
    xy[2 * i + 1] = r.outline.p[i].y;
  }
  return 1;
}

// The dark-pixel picture (w x h, 0 or 255) of the last tray search.
TC_API void tc_dark(void* p, uint8_t* out) {
  Handle* handle = (Handle*)p;
  memcpy(out, handle->pipeline.dark_picture(), (size_t)handle->w * handle->h);
}

// Size of the straightened tray of the last frame (0 x 0 when there is none).
TC_API void tc_straight_size(void* p, int* w, int* h) {
  Handle* handle = (Handle*)p;
  const bool have = handle->result.straight_w > 0;
  *w = have ? handle->pipeline.straight().w : 0;
  *h = have ? handle->pipeline.straight().h : 0;
}

// The straightened tray as hue, saturation, value (3 bytes per pixel, OpenCV scale), and
// the three color masks (red, blue, purple; 0 or 255). Each buffer holds w x h (x3) bytes.
TC_API void tc_straight(void* p, uint8_t* hsv, uint8_t* red, uint8_t* blue, uint8_t* purple) {
  Handle* handle = (Handle*)p;
  const tc::Straight& s = handle->pipeline.straight();
  const int n = s.w * s.h;
  for (int i = 0; i < n; i++) {
    hsv[3 * i] = s.hue[i];
    hsv[3 * i + 1] = s.sat[i];
    hsv[3 * i + 2] = s.val[i];
  }
  memcpy(red, handle->pipeline.color_mask(tc::RED), n);
  memcpy(blue, handle->pipeline.color_mask(tc::BLUE), n);
  memcpy(purple, handle->pipeline.color_mask(tc::PURPLE), n);
}

}  // extern "C"
