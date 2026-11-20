/*
  ESP32CamPipeline - the tray and cap pipeline on an ESP32-CAM (AI-Thinker).

  Finds the black tray and the red, blue and purple caps, and prints one line of
  JSON per frame on the serial port (115200 baud), like the Python program's
  --no-gui output:
    {"frame": 12, "time_ms": 4210, "tray": "locked", "caps": [{"color": "red", "u": 0.412, ...}]}
  Lines that start with # are information, not results. Ignore them when reading.

  Serial commands: send r to forget the locked tray and find it again.

  Board:   Tools > Board > ESP32 Arduino > "AI Thinker ESP32-CAM"
  PSRAM:   Tools > PSRAM > Enabled
  Speed:   Tools > CPU Frequency > 240 MHz
  Upload:  connect IO0 to GND while uploading, then remove it and press reset.
  Guide:   firmware/ESP32CamPipeline/README.md
*/

#include "esp_camera.h"

#include "src/board/overlay.h"
#include "src/core/tc_pipeline.h"

// ---- Settings you may want to change -------------------------------------

// Wi-Fi debug page: shows the camera picture with the tray outline and the caps.
// Slows the pipeline while someone looks at it. Turn it off when the robot runs.
#define USE_WIFI_DEBUG 0
#if USE_WIFI_DEBUG
#include <WebServer.h>
#include <WiFi.h>
const char* WIFI_SSID = "your-wifi-name";
const char* WIFI_PASSWORD = "your-wifi-password";
#endif

// Freeze the sensor's automatic exposure, gain and white balance. They change the
// picture's colors when something bright moves in view (the same problem as
// --lock-camera in the Python program). The numbers below are a starting point:
// raise EXPOSURE if the picture is too dark, lower it if too bright.
#define LOCK_CAMERA 1
const int EXPOSURE = 300;  // 0-1200
const int GAIN = 5;        // 0-30

// Print how long each frame took, every 20 frames, as a line starting with #.
#define PRINT_TIMING 1

// If red and blue are swapped in the results, the camera's byte order is the
// other way round on your board. Set this to 1.
#define SWAP_BYTES 0

// ---------------------------------------------------------------------------

// AI-Thinker ESP32-CAM pins.
#define PWDN_GPIO_NUM 32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM 0
#define SIOD_GPIO_NUM 26
#define SIOC_GPIO_NUM 27
#define Y9_GPIO_NUM 35
#define Y8_GPIO_NUM 34
#define Y7_GPIO_NUM 39
#define Y6_GPIO_NUM 36
#define Y5_GPIO_NUM 21
#define Y4_GPIO_NUM 19
#define Y3_GPIO_NUM 18
#define Y2_GPIO_NUM 5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM 23
#define PCLK_GPIO_NUM 22

static const int FRAME_W = 320, FRAME_H = 240;

static tc::Pipeline pipeline;
static tc::FrameResult result;
static uint32_t frame_number = 0;
static char json_line[1536];

#if USE_WIFI_DEBUG
static WebServer server(80);
static bool debug_wanted = false;  // set when the page asks for a picture
static uint8_t* debug_jpeg = nullptr;
static size_t debug_jpeg_size = 0;

static void send_page() {
  server.send(200, "text/html",
              "<html><body style='background:#111;color:#eee;font-family:sans-serif'>"
              "<h3>ESP32CamPipeline</h3><img id=p src='/frame.jpg' style='width:640px'>"
              "<pre id=s></pre><script>"
              "function t(){fetch('/frame.jpg').then(r=>r.blob()).then(b=>{p.src=URL.createObjectURL(b)});"
              "fetch('/status').then(r=>r.text()).then(x=>{s.textContent=x});}"
              "setInterval(t,700);</script></body></html>");
}

static void send_frame() {
  debug_wanted = true;
  if (debug_jpeg) server.send_P(200, "image/jpeg", (const char*)debug_jpeg, debug_jpeg_size);
  else server.send(503, "text/plain", "no picture yet");
}

static void send_status() { server.send(200, "application/json", json_line); }
#endif

static bool start_camera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_RGB565;  // raw colors: the pipeline needs them
  config.frame_size = FRAMESIZE_QVGA;      // 320 x 240
  config.jpeg_quality = 12;
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  if (esp_camera_init(&config) != ESP_OK) return false;

  sensor_t* sensor = esp_camera_sensor_get();
#if LOCK_CAMERA
  sensor->set_whitebal(sensor, 0);        // no automatic white balance
  sensor->set_awb_gain(sensor, 0);
  sensor->set_exposure_ctrl(sensor, 0);   // no automatic exposure
  sensor->set_aec2(sensor, 0);
  sensor->set_aec_value(sensor, EXPOSURE);
  sensor->set_gain_ctrl(sensor, 0);       // no automatic gain
  sensor->set_agc_gain(sensor, GAIN);
#endif
  sensor->set_lenc(sensor, 1);            // fixes dark corners
  return true;
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("# ESP32CamPipeline starting");

  if (!psramFound()) {
    Serial.println("# ERROR: PSRAM not found. In the Arduino IDE: Tools > PSRAM > Enabled");
    while (true) delay(1000);
  }
  if (!start_camera()) {
    Serial.println("# ERROR: camera did not start. Check the wiring, and press the reset button.");
    while (true) delay(1000);
  }
  if (!pipeline.begin(FRAME_W, FRAME_H)) {
    Serial.println("# ERROR: out of memory for the pipeline");
    while (true) delay(1000);
  }
  // Starting numbers for a 320 x 240 picture. See the README for what each one does.
  pipeline.config().object_min_side = 8;

#if USE_WIFI_DEBUG
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) delay(250);
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("# debug page: http://");
    Serial.println(WiFi.localIP());
    server.on("/", send_page);
    server.on("/frame.jpg", send_frame);
    server.on("/status", send_status);
    server.begin();
  } else {
    Serial.println("# Wi-Fi did not connect. The pipeline still runs.");
  }
#endif
  Serial.println("# running");
}

void loop() {
  if (Serial.available()) {
    if (Serial.read() == 'r') {
      pipeline.reset_tray();
      Serial.println("# tray forgotten, searching again");
    }
  }

  camera_fb_t* fb = esp_camera_fb_get();
  if (fb == nullptr) {
    Serial.println("# camera gave no picture");
    delay(50);
    return;
  }
  if (fb->format != PIXFORMAT_RGB565 || fb->width != FRAME_W || fb->height != FRAME_H) {
    Serial.println("# ERROR: wrong picture format");
    esp_camera_fb_return(fb);
    delay(500);
    return;
  }
#if SWAP_BYTES
  for (size_t i = 0; i + 1 < fb->len; i += 2) {
    const uint8_t t = fb->buf[i];
    fb->buf[i] = fb->buf[i + 1];
    fb->buf[i + 1] = t;
  }
#endif

  const uint32_t start = micros();
  pipeline.process(fb->buf, millis(), result);
  const uint32_t took_us = micros() - start;
  frame_number++;

  if (tc::result_to_json(json_line, sizeof(json_line), frame_number, millis(), result) > 0) {
    Serial.println(json_line);
  }
#if PRINT_TIMING
  if (frame_number % 20 == 0) {
    Serial.printf("# frame %lu: pipeline %lu ms, free PSRAM %u KB\n", (unsigned long)frame_number,
                  (unsigned long)(took_us / 1000), (unsigned)(ESP.getFreePsram() / 1024));
  }
#endif

#if USE_WIFI_DEBUG
  server.handleClient();
  if (debug_wanted) {
    debug_wanted = false;
    overlay::draw(fb->buf, FRAME_W, FRAME_H, result);
    free(debug_jpeg);
    debug_jpeg = nullptr;
    if (!frame2jpg(fb, 70, &debug_jpeg, &debug_jpeg_size)) debug_jpeg = nullptr;
  }
#endif
  esp_camera_fb_return(fb);
}
