// Shared types and settings for the tray and cap pipeline.
//
// This "core" is plain C++. It has no camera or Wi-Fi code, so the same files
// build on the ESP32-CAM (Arduino IDE) and on a PC (for testing against the
// Python pipeline in vision/).
#pragma once

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#if defined(ARDUINO_ARCH_ESP32)
#include <Arduino.h>
#endif

namespace tc {

// Memory for big pictures. On the ESP32-CAM it comes from the 4 MB PSRAM.
inline void* alloc(size_t bytes) {
#if defined(ARDUINO_ARCH_ESP32)
  void* p = ps_malloc(bytes);
  if (p == nullptr) p = malloc(bytes);
  return p;
#else
  return malloc(bytes);
#endif
}

inline void release(void* p) { free(p); }

// Biggest picture the core accepts. 320 x 240 (QVGA) is what the ESP32-CAM can handle.
// Bigger boards (the AMB82-Mini) and the PC use 640 x 360.
#if defined(ARDUINO_ARCH_ESP32)
constexpr int MAX_W = 320;
constexpr int MAX_H = 240;
#else
constexpr int MAX_W = 640;
constexpr int MAX_H = 360;
#endif
constexpr int MAX_CAPS = 16;

// How the pixels of a camera frame are stored.
//   RGB565_BE: 2 bytes per pixel, high byte first (the ESP32-CAM).
//   RGB888:    3 bytes per pixel, red, green, blue (a decoded JPEG, a PC picture).
enum PixelFormat : uint8_t { RGB565_BE = 0, RGB888 = 1 };

struct Point {
  float x, y;
};

// Four tray corners: top-left, top-right, bottom-right, bottom-left.
struct Quad {
  Point p[4];
};

enum Color : uint8_t { RED = 0, BLUE = 1, PURPLE = 2 };

inline const char* color_name(uint8_t color) {
  return color == RED ? "red" : (color == BLUE ? "blue" : "purple");
}

// One cap, in the same fields as the Python pipeline (vision/caps.py).
struct Cap {
  uint8_t color;
  float u, v;        // position as a fraction of the tray, 0 to 1
  float cx, cy;      // center in pixels of the straightened tray picture
  int bx, by, bw, bh;  // box: x, y, width, height in pixels
  float area;        // size in pixels
};

enum TrayState : uint8_t { SETTLING = 0, NOT_FOUND = 1, FINDING = 2, LOCKED = 3 };

inline const char* tray_state_name(uint8_t state) {
  switch (state) {
    case SETTLING: return "settling";
    case NOT_FOUND: return "not_found";
    case FINDING: return "finding";
    default: return "locked";
  }
}

// Every tuning number in one place. Defaults match the Python pipeline,
// except object_min_side: on a 320 x 240 picture a cap is about half as many
// pixels as on 640 x 480, so 8 is a better start than 12.
struct Config {
  // Finding the tray (vision/tray.py)
  int tray_max_value = 85;          // dark pixels: brightness <= this
  int tray_max_value_highest = 145; // strong light: raise the limit up to this (see TrayFinder)
  int tray_max_saturation = 255;    // 255 = colorfulness is ignored
  float tray_min_area_ratio = 0.04f;
  int close_radius = 8;             // fills gaps in the dark picture
  bool use_region = false;          // search only inside region (fractions)
  float region[4] = {0.f, 0.f, 1.f, 1.f};  // left, top, right, bottom
  float settle_seconds = 0.5f;
  float locked_check_seconds = 0.2f;
  float lock_seconds = 0.75f;
  float move_seconds = 1.0f;

  // Colors (vision/caps.py)
  int object_min_saturation = 70;   // purple
  int object_min_value = 45;
  int brightness_margin = 45;       // a cap must be this much brighter than the tray
  int red_max_hue = 10;
  int red_min_saturation = 150;
  int red_high_hue_min = 165;
  int red_high_min_saturation = 170;
  int purple_min_hue = 125;
  int purple_max_hue = 176;
  int blue_min_hue = 100;
  int blue_max_hue = 124;
  int blue_min_saturation = 120;

  // Caps
  float object_min_area_ratio = 0.0005f;
  float object_max_aspect = 1.9f;
  int object_min_side = 8;
  float edge_margin = 0.04f;
};

}  // namespace tc
