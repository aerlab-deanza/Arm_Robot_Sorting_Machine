/*
  AMB82Pipeline - the tray and cap pipeline running on the AMB82-Mini itself.

  Finds the black tray and the red, blue and purple caps. No PC runs the pipeline.
  Results:
    - Serial Monitor (115200 baud): one line of JSON per frame, like the Python
      program's --no-gui output. Lines starting with # are information.
    - RTSP video (open the address with VLC) with the tray outline and caps drawn on it.

  Serial commands: send r to forget the locked tray and find it again.

  Board:  Tools > Board > AMB82-MINI
  Guide:  firmware/AMB82Pipeline/README.md
  The pipeline code is in src/core (a copy of firmware/tray_cap_core, made by
  python firmware/sync_core.py). Do not edit the copy.
*/

#include "RTSP.h"
#include "StreamIO.h"
#include "VideoStream.h"
#include "VideoStreamOverlay.h"
#include "WiFi.h"

#include "src/core/tc_jpeg.h"
#include "src/core/tc_pipeline.h"

// ---- Settings you may want to change -------------------------------------

// Wi-Fi name and password (needed for the RTSP video). Do not commit real ones.
char ssid[] = "KHANH";
char pass[] = "keswick3616";

// Freeze the camera's automatic exposure and white balance, like --lock-camera in the
// Python program. EXPOSURE_TIME and GAIN are the frozen values: change them if the
// picture is too dark or too bright.
#define LOCK_CAMERA 0
const int EXPOSURE_TIME = 10000;
const int GAIN = 64;

// Where the tray is in the picture, as fractions: left, top, right, bottom.
// Only this box is searched, so other dark things (a dresser, a bag) are ignored.
// Leave a gap around the tray. Set USE_TRAY_REGION to 0 to search the whole picture.
#define USE_TRAY_REGION 0
const float TRAY_REGION[4] = {0.235f, 0.22f, 0.515f, 0.74f};

// Debug page: open http://<board address>/ in a browser to see 4 views, like the Python
// windows: tray mask, tray localization, object detection, object mask. About one new
// picture per second. It slows the pipeline while a browser has the page open, so turn
// it off (0) when the robot runs. Needs Wi-Fi.
#define USE_DEBUG_PAGE 0

// Print how long each frame took, every 20 frames, as a line starting with #.
#define PRINT_TIMING 1

// Print a "# debug:" line after every result: how many pixels were dark, how many dark
// shapes were found and why they were not the tray, the tray's brightness, and the caps
// found before steadying. Explains a "not_found" or a missing cap. 0 = off.
#define PRINT_DEBUG 1

// Draw the tray outline and caps on the RTSP video. Set 0 when the PC viewer
// (view_core.py) reads the video, so the drawings do not end up in its pictures.
#define SHOW_OVERLAY 1

// ---------------------------------------------------------------------------

// Channel 0: H264 video for RTSP (what you watch). Channel 1: JPEG pictures for the pipeline.
#define CHANNEL_VIDEO 0
#define CHANNEL_JPEG 1
static const int VIDEO_W = 1280, VIDEO_H = 720;
static const int PIPE_W = 640, PIPE_H = 360;  // 16:9, same shape as the video

VideoSetting videoConfig(VIDEO_W, VIDEO_H, 15, VIDEO_H264, 0);
VideoSetting jpegConfig(PIPE_W, PIPE_H, 10, VIDEO_JPEG, 1);
CameraSetting cameraSettings;
RTSP rtsp;
StreamIO videoStreamer(1, 1);

static tc::Pipeline pipeline;
static tc::FrameResult result;
static uint8_t* rgb = nullptr;
static uint32_t frame_number = 0;
static char json_line[2048];

#if USE_DEBUG_PAGE
#include "debug_page.h"
#endif

// Draws the tray outline and the caps on the RTSP video (pipeline pixels -> video pixels).
static void draw_overlay() {
  const float sx = (float)VIDEO_W / PIPE_W, sy = (float)VIDEO_H / PIPE_H;
  OSD.createBitmap(CHANNEL_VIDEO);
  if (result.has_outline) {
    const uint32_t color = (result.state == tc::LOCKED) ? OSD_COLOR_CYAN : OSD_COLOR_GREEN;
    for (int i = 0; i < 4; i++) {
      const tc::Point& a = result.outline.p[i];
      const tc::Point& b = result.outline.p[(i + 1) % 4];
      OSD.drawLine(CHANNEL_VIDEO, (int)(a.x * sx), (int)(a.y * sy), (int)(b.x * sx), (int)(b.y * sy), 3, color); 
    }
    // Each cap: a cross at its place on the tray (u, v -> picture), with its name.
    const tc::Point* c = result.outline.p;
    for (int i = 0; i < result.cap_count; i++) {
      const float u = result.caps[i].u, v = result.caps[i].v;
      const float top_x = c[0].x + (c[1].x - c[0].x) * u, top_y = c[0].y + (c[1].y - c[0].y) * u;
      const float bottom_x = c[3].x + (c[2].x - c[3].x) * u, bottom_y = c[3].y + (c[2].y - c[3].y) * u;
      const int x = (int)((top_x + (bottom_x - top_x) * v) * sx);
      const int y = (int)((top_y + (bottom_y - top_y) * v) * sy);
      OSD.drawPlus(CHANNEL_VIDEO, x, y, 24, 3, OSD_COLOR_YELLOW);
      char text[40];
      snprintf(text, sizeof(text), "%s %.2f %.2f", tc::color_name(result.caps[i].color), u, v);
      OSD.drawText(CHANNEL_VIDEO, x + 14, y - 14, text, OSD_COLOR_YELLOW);
    }
  }
  OSD.update(CHANNEL_VIDEO);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("# AMB82Pipeline starting");

  rgb = (uint8_t*)malloc((size_t)PIPE_W * PIPE_H * 3);
  if (rgb == nullptr || !pipeline.begin(PIPE_W, PIPE_H)) {
    Serial.println("# ERROR: out of memory for the pipeline");
    while (true) delay(1000);
  }

#if USE_TRAY_REGION
  pipeline.config().use_region = true;
  for (int i = 0; i < 4; i++) pipeline.config().region[i] = TRAY_REGION[i];
#endif

  int status = WL_IDLE_STATUS;
  for (int tries = 0; status != WL_CONNECTED && tries < 10; tries++) {
    Serial.print("# connecting to Wi-Fi: ");
    Serial.println(ssid);
    status = WiFi.begin(ssid, pass);
    delay(2000);
  }
  if (status != WL_CONNECTED) Serial.println("# Wi-Fi did not connect. No video, but the pipeline still runs.");

  videoConfig.setBitrate(2 * 1024 * 1024);
  Camera.configVideoChannel(CHANNEL_VIDEO, videoConfig);
  Camera.configVideoChannel(CHANNEL_JPEG, jpegConfig);
  Camera.videoInit();

  rtsp.configVideo(videoConfig);
  rtsp.begin();
  videoStreamer.registerInput(Camera.getStream(CHANNEL_VIDEO));
  videoStreamer.registerOutput(rtsp);
  if (videoStreamer.begin() != 0) Serial.println("# RTSP link failed to start");
  Camera.channelBegin(CHANNEL_VIDEO);
  Camera.channelBegin(CHANNEL_JPEG);

  OSD.configVideo(CHANNEL_VIDEO, videoConfig);
  OSD.begin();

#if LOCK_CAMERA
  cameraSettings.setExposureMode(0);
  cameraSettings.setExposureTime(EXPOSURE_TIME);
  cameraSettings.setAEGain(GAIN);
  cameraSettings.setAWB(0);
#endif

  if (status == WL_CONNECTED) {
    Serial.print("# video: rtsp://");
    Serial.print(WiFi.localIP());
    Serial.print(":");
    Serial.println(rtsp.getPort());
#if USE_DEBUG_PAGE
    debug_page::begin();
    Serial.print("# debug page: http://");
    Serial.println(WiFi.localIP());
#endif
  }
  Serial.println("# running");
}

void loop() {
  if (Serial.available() && Serial.read() == 'r') {
    pipeline.reset_tray();
    Serial.println("# tray forgotten, searching again");
  }

  uint32_t jpeg_addr = 0, jpeg_len = 0;
  Camera.getImage(CHANNEL_JPEG, &jpeg_addr, &jpeg_len);
  int w = 0, h = 0;
  if (jpeg_len == 0 ||
      !tc::decode_jpeg((const uint8_t*)jpeg_addr, jpeg_len, rgb, (size_t)PIPE_W * PIPE_H * 3, 0, w, h) ||
      w != PIPE_W || h != PIPE_H) {
    Serial.println("# no usable picture");
    delay(100);
    return;
  }

  const uint32_t start = micros();
  pipeline.process(rgb, tc::RGB888, millis(), result);
  const uint32_t took_us = micros() - start;
  frame_number++;

  if (tc::result_to_json(json_line, sizeof(json_line), frame_number, millis(), result) > 0) {
    Serial.println(json_line);
  }
#if PRINT_DEBUG
  if (tc::debug_to_text(json_line, sizeof(json_line), result) > 0) Serial.println(json_line);
#endif
#if SHOW_OVERLAY
  draw_overlay();
#endif
#if USE_DEBUG_PAGE
  debug_page::serve(pipeline, result, rgb, PIPE_W, PIPE_H);
#endif
#if PRINT_TIMING
  if (frame_number % 20 == 0) {
    Serial.print("# frame ");
    Serial.print(frame_number);
    Serial.print(": pipeline ");
    Serial.print(took_us / 1000);
    Serial.println(" ms");
  }
#endif
}
