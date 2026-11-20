// Debug web page for AMB82Pipeline: four views of the pipeline in a browser,
// like the Python preview windows. Open http://<board address>/
//   1 Tray mask            (dark pixels used to find the tray)
//   2 Tray localization    (camera picture, tray outline, cap crosses)
//   3 Object detection     (straightened tray with a box around each cap)
//   4 Object mask          (red, blue, purple masks on the straightened tray)
// The pictures are BMP files, made one row at a time and sent while the pipeline waits.
#pragma once

#include <string.h>

#include "WiFi.h"
#include "src/core/tc_pipeline.h"

namespace debug_page {

static WiFiServer server(80);
static bool running = false;

// What the picture functions draw from. Set by serve() on every call.
static tc::Pipeline* g_pipeline = nullptr;
static const tc::FrameResult* g_result = nullptr;
static uint8_t* g_rgb = nullptr;
static int g_w = 0, g_h = 0;

typedef void (*PixelFn)(int x, int y, uint8_t* rgb_out);

static void put_le(uint8_t* p, uint32_t value, int bytes) {
  for (int i = 0; i < bytes; i++) p[i] = (uint8_t)(value >> (8 * i));
}

// Sends a BMP of src_w x src_h pixels, taking every `step`-th pixel to keep it small.
static void send_bmp(WiFiClient& client, int src_w, int src_h, int step, PixelFn pixel) {
  const int w = src_w / step, h = src_h / step;
  const int row_bytes = (w * 3 + 3) & ~3;
  const uint32_t data_bytes = (uint32_t)row_bytes * h;
  uint8_t head[54];
  memset(head, 0, sizeof(head));
  head[0] = 'B';
  head[1] = 'M';
  put_le(head + 2, 54 + data_bytes, 4);
  put_le(head + 10, 54, 4);
  put_le(head + 14, 40, 4);
  put_le(head + 18, (uint32_t)w, 4);
  put_le(head + 22, (uint32_t)(-h), 4);  // negative height = top row first
  put_le(head + 26, 1, 2);
  put_le(head + 28, 24, 2);
  put_le(head + 34, data_bytes, 4);
  char text[160];
  snprintf(text, sizeof(text),
           "HTTP/1.1 200 OK\r\nContent-Type: image/bmp\r\nContent-Length: %lu\r\n"
           "Cache-Control: no-store\r\nConnection: close\r\n\r\n",
           (unsigned long)(54 + data_bytes));
  client.print(text);
  client.write(head, 54);
  static uint8_t row[(tc::MAX_W + 4) * 3];
  for (int y = 0; y < h; y++) {
    memset(row, 0, row_bytes);
    for (int x = 0; x < w; x++) {
      uint8_t c[3];
      pixel(x * step, y * step, c);
      row[3 * x] = c[2];  // BMP order is blue, green, red
      row[3 * x + 1] = c[1];
      row[3 * x + 2] = c[0];
    }
    client.write(row, row_bytes);
  }
}

// Hue 0-179, saturation and value 0-255 (OpenCV scale) to red, green, blue.
static void hsv_to_rgb(int h, int s, int v, uint8_t* out) {
  const float hf = h * 2.0f / 60.0f, sf = s / 255.0f;
  const int sector = ((int)hf) % 6;
  const float f = hf - (int)hf;
  const float p = v * (1 - sf), q = v * (1 - sf * f), t = v * (1 - sf * (1 - f));
  float r, g, b;
  switch (sector) {
    case 0: r = v; g = t; b = p; break;
    case 1: r = q; g = v; b = p; break;
    case 2: r = p; g = v; b = t; break;
    case 3: r = p; g = q; b = v; break;
    case 4: r = t; g = p; b = v; break;
    default: r = v; g = p; b = q; break;
  }
  out[0] = (uint8_t)r;
  out[1] = (uint8_t)g;
  out[2] = (uint8_t)b;
}

static void pixel_black(int, int, uint8_t* c) { c[0] = c[1] = c[2] = 0; }

// View 1.
static void pixel_tray_mask(int x, int y, uint8_t* c) {
  c[0] = c[1] = c[2] = g_pipeline->dark_picture()[y * g_w + x];
}

// View 2 (the outline and crosses are drawn into the picture before this).
static void pixel_camera(int x, int y, uint8_t* c) {
  const uint8_t* p = g_rgb + 3 * (y * g_w + x);
  c[0] = p[0];
  c[1] = p[1];
  c[2] = p[2];
}

// View 3.
static void pixel_objects(int x, int y, uint8_t* c) {
  const tc::Straight& tray = g_pipeline->straight();
  const int i = y * tray.w + x;
  hsv_to_rgb(tray.hue[i], tray.sat[i], tray.val[i], c);
  for (int k = 0; k < g_result->cap_count; k++) {
    const tc::Cap& cap = g_result->caps[k];
    const bool in_outer = x >= cap.bx - 1 && x <= cap.bx + cap.bw && y >= cap.by - 1 && y <= cap.by + cap.bh;
    const bool in_inner = x >= cap.bx + 1 && x < cap.bx + cap.bw - 1 && y >= cap.by + 1 && y < cap.by + cap.bh - 1;
    if (in_outer && !in_inner) {
      c[0] = 255;
      c[1] = 255;
      c[2] = 0;
    }
  }
}

// View 4.
static void pixel_object_mask(int x, int y, uint8_t* c) {
  const int i = y * g_pipeline->straight().w + x;
  c[0] = c[1] = c[2] = 0;
  if (g_pipeline->color_mask(tc::RED)[i]) {
    c[0] = 255; c[1] = 40; c[2] = 40;
  } else if (g_pipeline->color_mask(tc::BLUE)[i]) {
    c[0] = 60; c[1] = 100; c[2] = 255;
  } else if (g_pipeline->color_mask(tc::PURPLE)[i]) {
    c[0] = 200; c[1] = 80; c[2] = 220;
  }
}

// Draws a line into the camera picture, 2 pixels thick.
static void rgb_line(int x0, int y0, int x1, int y1, uint8_t r, uint8_t g, uint8_t b) {
  int dx = abs(x1 - x0), dy = -abs(y1 - y0);
  const int sx = x0 < x1 ? 1 : -1, sy = y0 < y1 ? 1 : -1;
  int err = dx + dy;
  while (true) {
    for (int oy = 0; oy < 2; oy++) {
      for (int ox = 0; ox < 2; ox++) {
        const int x = x0 + ox, y = y0 + oy;
        if (x < 0 || y < 0 || x >= g_w || y >= g_h) continue;
        uint8_t* p = g_rgb + 3 * (y * g_w + x);
        p[0] = r;
        p[1] = g;
        p[2] = b;
      }
    }
    if (x0 == x1 && y0 == y1) break;
    const int e2 = 2 * err;
    if (e2 >= dy) { err += dy; x0 += sx; }
    if (e2 <= dx) { err += dx; y0 += sy; }
  }
}

// Tray outline (cyan when locked, green while finding) and a yellow cross on each cap.
static void draw_on_picture() {
  if (!g_result->has_outline) return;
  const bool locked = g_result->state == tc::LOCKED;
  for (int i = 0; i < 4; i++) {
    const tc::Point& a = g_result->outline.p[i];
    const tc::Point& b = g_result->outline.p[(i + 1) % 4];
    rgb_line((int)a.x, (int)a.y, (int)b.x, (int)b.y, 0, 255, locked ? 255 : 0);
  }
  const tc::Point* c = g_result->outline.p;
  for (int i = 0; i < g_result->cap_count; i++) {
    const float u = g_result->caps[i].u, v = g_result->caps[i].v;
    const float tx = c[0].x + (c[1].x - c[0].x) * u, ty = c[0].y + (c[1].y - c[0].y) * u;
    const float bx = c[3].x + (c[2].x - c[3].x) * u, by = c[3].y + (c[2].y - c[3].y) * u;
    const int x = (int)(tx + (bx - tx) * v), y = (int)(ty + (by - ty) * v);
    rgb_line(x - 6, y, x + 6, y, 255, 255, 0);
    rgb_line(x, y - 6, x, y + 6, 255, 255, 0);
  }
}

static const char PAGE[] =
    "<html><body style='background:#111;color:#eee;font-family:sans-serif'>"
    "<h3>AMB82Pipeline debug</h3>"
    "<div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;max-width:1100px'>"
    "<div>1 Tray mask<br><img id=i1 style='width:100%'></div>"
    "<div>2 Tray localization<br><img id=i2 style='width:100%'></div>"
    "<div>3 Object detection<br><img id=i3 style='width:100%'></div>"
    "<div>4 Object mask<br><img id=i4 style='width:100%'></div></div><script>"
    "function r(n){var m=new Image();"
    "m.onload=function(){document.getElementById('i'+n).src=m.src;setTimeout(function(){r(n)},300)};"
    "m.onerror=function(){setTimeout(function(){r(n)},2000)};"
    "m.src='/'+n+'.bmp?t='+Date.now();}"
    "for(var n=1;n<=4;n++)r(n);</script></body></html>";

inline void begin() {
  server.begin();
  running = true;
}

// Answers one browser request, if one is waiting. Call once per frame, after the pipeline ran.
// `rgb` is the camera picture (w x h, RGB888). It gets the outline drawn on it.
inline void serve(tc::Pipeline& pipeline, const tc::FrameResult& result, uint8_t* rgb, int w, int h) {
  if (!running) return;
  WiFiClient client = server.available();
  if (!client) return;

  Serial.println("# web: client waiting");
  g_pipeline = &pipeline;
  g_result = &result;
  g_rgb = rgb;
  g_w = w;
  g_h = h;

  char line[96];
  int n = 0;
  const uint32_t start = millis();
  while (client.connected() && millis() - start < 300) {
    if (!client.available()) continue;
    const char c = client.read();
    if (c == '\n') break;
    if (n < (int)sizeof(line) - 1) line[n++] = c;
  }
  line[n] = 0;
  Serial.print("# web: request: ");
  Serial.println(line);
  while (client.available()) client.read();  // ignore the rest of the request

  const tc::Straight& tray = pipeline.straight();
  const bool have_tray = result.has_outline && tray.w > 0 && tray.h > 0;
  int step = (tray.w + 319) / 320;  // keep views 3 and 4 at most 320 wide
  if (step < 1) step = 1;

  if (!strncmp(line, "GET /1.bmp", 10)) {
    send_bmp(client, w, h, 2, pixel_tray_mask);
  } else if (!strncmp(line, "GET /2.bmp", 10)) {
    draw_on_picture();
    send_bmp(client, w, h, 2, pixel_camera);
  } else if (!strncmp(line, "GET /3.bmp", 10)) {
    if (have_tray) send_bmp(client, tray.w, tray.h, step, pixel_objects);
    else send_bmp(client, 320, 180, 1, pixel_black);
  } else if (!strncmp(line, "GET /4.bmp", 10)) {
    if (have_tray) send_bmp(client, tray.w, tray.h, step, pixel_object_mask);
    else send_bmp(client, 320, 180, 1, pixel_black);
  } else if (!strncmp(line, "GET / ", 6)) {
    client.print("HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n");
    client.print(PAGE);
  } else {
    client.print("HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\n");
  }
  Serial.println("# web: answer sent");
  client.stop();
  Serial.println("# web: closed");
}

}  // namespace debug_page
