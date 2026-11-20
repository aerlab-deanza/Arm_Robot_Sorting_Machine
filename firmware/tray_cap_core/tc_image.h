// Small picture tools: color conversion, gap filling / speck removal, and
// finding blobs. All work on plain byte arrays, with no OpenCV.
#pragma once

#include "tc_types.h"

namespace tc {

// RGB565 pixel as the ESP32 camera delivers it: two bytes, high byte first.
inline void unpack_rgb565(const uint8_t* p, int& r, int& g, int& b) {
  const int px = (p[0] << 8) | p[1];
  const int r5 = (px >> 11) & 31, g6 = (px >> 5) & 63, b5 = px & 31;
  r = (r5 << 3) | (r5 >> 2);
  g = (g6 << 2) | (g6 >> 4);
  b = (b5 << 3) | (b5 >> 2);
}

// Reads pixel number `index` of a frame in either format.
inline void read_rgb(const uint8_t* frame, PixelFormat format, int index, int& r, int& g, int& b) {
  if (format == RGB888) {
    const uint8_t* p = frame + 3 * index;
    r = p[0]; g = p[1]; b = p[2];
  } else {
    unpack_rgb565(frame + 2 * index, r, g, b);
  }
}

// Same scale as OpenCV: hue 0-179, saturation and value 0-255.
inline void rgb_to_hsv(int r, int g, int b, uint8_t& h, uint8_t& s, uint8_t& v) {
  const int mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
  const int mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
  const int delta = mx - mn;
  v = (uint8_t)mx;
  if (mx == 0 || delta == 0) {
    s = 0;
    h = 0;
    return;
  }
  s = (uint8_t)((255 * delta + mx / 2) / mx);
  int hue;  // in OpenCV units (degrees / 2)
  if (mx == r) {
    hue = (30 * (g - b)) / delta;
  } else if (mx == g) {
    hue = 60 + (30 * (b - r)) / delta;
  } else {
    hue = 120 + (30 * (r - g)) / delta;
  }
  if (hue < 0) hue += 180;
  if (hue > 179) hue -= 180;
  h = (uint8_t)hue;
}

// Black-and-white pictures are byte arrays: 0 = black, 255 = white.
// Grow white by `radius` pixels (a square brush). `tmp` is scratch, same size.
void dilate(const uint8_t* in, uint8_t* out, uint8_t* tmp, int w, int h, int radius);
// Shrink white by `radius` pixels.
void erode(const uint8_t* in, uint8_t* out, uint8_t* tmp, int w, int h, int radius);
// Fill small black gaps (grow, then shrink).
void close_mask(uint8_t* mask, uint8_t* scratch1, uint8_t* scratch2, int w, int h, int radius);
// Remove small white specks (shrink, then grow).
void open_mask(uint8_t* mask, uint8_t* scratch1, uint8_t* scratch2, int w, int h, int radius);

// One white blob.
struct Blob {
  int area;
  int min_x, min_y, max_x, max_y;
  long long sum_x, sum_y;
};

constexpr int MAX_BLOBS = 64;

// Label the blobs of a black-and-white picture (8 neighbors). `labels` gets a
// blob number per pixel (0 = background). Returns how many blobs were found
// (at most MAX_BLOBS; the biggest ones are kept). Blob numbers start at 1, so
// `blobs` must have room for MAX_BLOBS + 1 entries.
int find_blobs(const uint8_t* mask, uint16_t* labels, int w, int h, Blob* blobs);

}  // namespace tc
