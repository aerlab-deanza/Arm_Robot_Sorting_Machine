// Runs the ESP32 core on a PC, on a raw picture file, and prints the JSON lines.
//
//   pc_test picture.rgb WIDTH HEIGHT SECONDS STEP_MS [options]
//   pc_test picture.jpg 0 0 SECONDS STEP_MS [options]        (JPEG: size is read from the file)
//
// picture.rgb is WIDTH * HEIGHT * 3 bytes (red, green, blue). The same picture is
// fed again and again, STEP_MS apart, for SECONDS seconds of pretend time (like the
// Python tests do). By default only the last frame's JSON is printed.
//
// Options:
//   --region l,t,r,b   search for the tray only in this part of the picture (fractions)
//   --min-side N       smallest cap side in pixels
//   --rgb565           feed the pipeline ESP32-CAM style pixels (default: RGB888)
//   --all              print every frame's JSON
//   --time             print the time per frame
//   --debug            print the debug line (# debug: ...) for every frame, on stderr
#include <chrono>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vector>

#include "../tc_jpeg.h"
#include "../tc_pipeline.h"

int main(int argc, char** argv) {
  if (argc < 6) {
    fprintf(stderr, "usage: pc_test picture.rgb W H SECONDS STEP_MS [--region l,t,r,b] [--all] [--time] [--debug]\n");
    return 2;
  }
  int w = atoi(argv[2]), h = atoi(argv[3]);
  const float seconds = (float)atof(argv[4]);
  const int step_ms = atoi(argv[5]);
  bool print_all = false, print_time = false, use_rgb565 = false, print_debug = false;
  tc::Config config;
  for (int i = 6; i < argc; i++) {
    if (!strcmp(argv[i], "--all")) print_all = true;
    else if (!strcmp(argv[i], "--time")) print_time = true;
    else if (!strcmp(argv[i], "--debug")) print_debug = true;
    else if (!strcmp(argv[i], "--rgb565")) use_rgb565 = true;
    else if (!strcmp(argv[i], "--region") && i + 1 < argc) {
      config.use_region = true;
      sscanf(argv[++i], "%f,%f,%f,%f", &config.region[0], &config.region[1], &config.region[2], &config.region[3]);
    } else if (!strcmp(argv[i], "--min-side") && i + 1 < argc) {
      config.object_min_side = atoi(argv[++i]);
    }
  }

  FILE* f = fopen(argv[1], "rb");
  if (!f) { fprintf(stderr, "cannot open %s\n", argv[1]); return 2; }
  std::vector<uint8_t> file;
  uint8_t chunk[4096];
  size_t got;
  while ((got = fread(chunk, 1, sizeof(chunk), f)) > 0) file.insert(file.end(), chunk, chunk + got);
  fclose(f);

  std::vector<uint8_t> rgb;
  const size_t name_len = strlen(argv[1]);
  if (name_len > 4 && (!strcmp(argv[1] + name_len - 4, ".jpg") || !strcmp(argv[1] + name_len - 5, ".jpeg"))) {
    rgb.resize((size_t)tc::MAX_W * tc::MAX_H * 3);
    if (!tc::decode_jpeg(file.data(), file.size(), rgb.data(), rgb.size(), 0, w, h)) {
      fprintf(stderr, "could not decode the JPEG (or it is bigger than %d x %d)\n", tc::MAX_W, tc::MAX_H);
      return 2;
    }
  } else {
    rgb = file;
    if (rgb.size() != (size_t)w * h * 3) { fprintf(stderr, "file size does not match W x H x 3\n"); return 2; }
  }

  // What the pipeline reads: RGB888 as it is, or RGB565 like the ESP32-CAM.
  std::vector<uint8_t> frame;
  if (use_rgb565) {
    frame.resize((size_t)w * h * 2);
    for (int i = 0; i < w * h; i++) {
      const int r = rgb[3 * i], g = rgb[3 * i + 1], b = rgb[3 * i + 2];
      const int px = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3);
      frame[2 * i] = (uint8_t)(px >> 8);
      frame[2 * i + 1] = (uint8_t)(px & 255);
    }
  } else {
    frame = rgb;
  }
  const tc::PixelFormat format = use_rgb565 ? tc::RGB565_BE : tc::RGB888;

  tc::Pipeline pipeline(config);
  if (!pipeline.begin(w, h)) { fprintf(stderr, "out of memory or picture too big\n"); return 2; }

  char line[2048];
  tc::FrameResult result;
  uint32_t frame_number = 0;
  double total_ms = 0, worst_ms = 0;
  for (uint32_t now = 0; now < (uint32_t)(seconds * 1000); now += step_ms) {
    const auto t0 = std::chrono::steady_clock::now();
    pipeline.process(frame.data(), format, now, result);
    const double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - t0).count();
    total_ms += ms;
    if (ms > worst_ms) worst_ms = ms;
    frame_number++;
    if (print_debug && tc::debug_to_text(line, sizeof(line), result) > 0) fprintf(stderr, "%s\n", line);
    if (print_all) {
      tc::result_to_json(line, sizeof(line), frame_number, now, result);
      puts(line);
    }
  }
  if (!print_all) {
    if (tc::result_to_json(line, sizeof(line), frame_number, 0, result) < 0) return 3;
    puts(line);
  }
  if (print_time) fprintf(stderr, "frames %u, average %.2f ms, worst %.2f ms\n", frame_number, total_ms / frame_number, worst_ms);
  return 0;
}
