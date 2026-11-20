// Draws the tray outline and the cap boxes on an RGB565 camera frame, so the
// debug page shows what the pipeline sees. Only used when the Wi-Fi debug page is on.
#pragma once

#include <stdint.h>

#include "../core/tc_pipeline.h"

namespace overlay {

inline void put_pixel(uint8_t* frame, int w, int h, int x, int y, uint16_t rgb565) {
  if (x < 0 || y < 0 || x >= w || y >= h) return;
  uint8_t* p = frame + 2 * (y * w + x);
  p[0] = (uint8_t)(rgb565 >> 8);  // high byte first, like the camera
  p[1] = (uint8_t)(rgb565 & 255);
}

inline void line(uint8_t* frame, int w, int h, int x0, int y0, int x1, int y1, uint16_t color) {
  int dx = abs(x1 - x0), dy = -abs(y1 - y0);
  int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  while (true) {
    put_pixel(frame, w, h, x0, y0, color);
    if (x0 == x1 && y0 == y1) break;
    const int e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

constexpr uint16_t GREEN = 0x07E0;
constexpr uint16_t CYAN = 0x07FF;
constexpr uint16_t YELLOW = 0xFFE0;

// Tray outline: green while finding, cyan when locked. Cap boxes are drawn
// in the camera picture (the straightened box is mapped back to the camera).
inline void draw(uint8_t* frame, int w, int h, const tc::FrameResult& result) {
  if (!result.has_outline) return;
  const uint16_t color = result.state == tc::LOCKED ? CYAN : GREEN;
  for (int i = 0; i < 4; i++) {
    const tc::Point& a = result.outline.p[i];
    const tc::Point& b = result.outline.p[(i + 1) % 4];
    line(frame, w, h, (int)a.x, (int)a.y, (int)b.x, (int)b.y, color);
  }
  // Mark each cap with a small cross at its place on the tray: u, v -> camera picture.
  const tc::Point* c = result.outline.p;
  for (int i = 0; i < result.cap_count; i++) {
    const float u = result.caps[i].u, v = result.caps[i].v;
    const float top_x = c[0].x + (c[1].x - c[0].x) * u, top_y = c[0].y + (c[1].y - c[0].y) * u;
    const float bottom_x = c[3].x + (c[2].x - c[3].x) * u, bottom_y = c[3].y + (c[2].y - c[3].y) * u;
    const int x = (int)(top_x + (bottom_x - top_x) * v), y = (int)(top_y + (bottom_y - top_y) * v);
    line(frame, w, h, x - 4, y, x + 4, y, YELLOW);
    line(frame, w, h, x, y - 4, x, y + 4, YELLOW);
  }
}

}  // namespace overlay
