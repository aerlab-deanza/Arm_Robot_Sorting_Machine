/*
 * AMB82-Mini tray object detection example.
 *
 * Based on Realtek's AmebaNN ObjectDetectionLoop example. This filters
 * detections by whether the bounding-box center falls inside TRAY_POLYGON.
 * Coordinates in TRAY_POLYGON are normalized to the full RTSP image:
 * x = 0 at the left, x = 1 at the right; y = 0 at the top, y = 1 at the bottom.
 *
 * Replace the Wi-Fi placeholders and calibrate the four tray corners below.
 */

#include "WiFi.h"
#include "StreamIO.h"
#include "VideoStream.h"
#include "RTSP.h"
#include "NNObjectDetection.h"
#include "VideoStreamOverlay.h"

#define CHANNEL   0
#define CHANNELNN 3
#define NNWIDTH   576
#define NNHEIGHT  320

VideoSetting config(VIDEO_FHD, 30, VIDEO_H264, 0);
VideoSetting configNN(NNWIDTH, NNHEIGHT, 10, VIDEO_RGB, 0);
NNObjectDetection ObjDet;
RTSP rtsp;
StreamIO videoStreamer(1, 1);
StreamIO videoStreamerNN(1, 1);

// Set your Wi-Fi credentials before uploading. Do not commit real credentials.
char ssid[] = "YOUR_WIFI_SSID";
char pass[] = "YOUR_WIFI_PASSWORD";
int status = WL_IDLE_STATUS;
IPAddress ip;
int rtsp_portnum;

struct Point {
    float x;
    float y;
};

// Approximate boundary traced around the visible black pad in the user's
// camera screenshot (1792x1008, same 16:9 proportions as the 1920x1080 stream).
// The top edge is partly obscured by the objects, so adjust after testing.
// Coordinates are normalized and must be entered around the boundary in order.
const Point TRAY_POLYGON[] = {
    {0.43f, 0.69f}, // back-left, approximate
    {0.76f, 0.72f}, // back-right, approximate
    {0.82f, 0.86f}, // right edge
    {0.80f, 0.93f}, // front-right
    {0.45f, 0.87f}, // front-left
    {0.35f, 0.82f}  // left edge
};
const size_t TRAY_VERTEX_COUNT = sizeof(TRAY_POLYGON) / sizeof(TRAY_POLYGON[0]);

bool pointInsideTray(float x, float y)
{
    bool inside = false;
    for (size_t i = 0, j = TRAY_VERTEX_COUNT - 1; i < TRAY_VERTEX_COUNT; j = i++) {
        const Point &a = TRAY_POLYGON[i];
        const Point &b = TRAY_POLYGON[j];
        const bool crosses = ((a.y > y) != (b.y > y)) &&
            (x < (b.x - a.x) * (y - a.y) / (b.y - a.y) + a.x);
        if (crosses) {
            inside = !inside;
        }
    }
    return inside;
}

void setup()
{
    Serial.begin(115200);

    while (status != WL_CONNECTED) {
        Serial.print("Attempting to connect to WPA SSID: ");
        Serial.println(ssid);
        status = WiFi.begin(ssid, pass);
        delay(2000);
    }

    ip = WiFi.localIP();

    config.setBitrate(2 * 1024 * 1024);
    Camera.configVideoChannel(CHANNEL, config);
    Camera.configVideoChannel(CHANNELNN, configNN);
    Camera.videoInit();

    rtsp.configVideo(config);
    rtsp.begin();
    rtsp_portnum = rtsp.getPort();

    ObjDet.configVideo(configNN);
    ObjDet.modelSelect(OBJECT_DETECTION, DEFAULT_YOLOV4TINY, NA_MODEL, NA_MODEL);
    ObjDet.begin();

    videoStreamer.registerInput(Camera.getStream(CHANNEL));
    videoStreamer.registerOutput(rtsp);
    if (videoStreamer.begin() != 0) {
        Serial.println("RTSP StreamIO link start failed");
    }
    Camera.channelBegin(CHANNEL);

    videoStreamerNN.registerInput(Camera.getStream(CHANNELNN));
    videoStreamerNN.setStackSize();
    videoStreamerNN.setTaskPriority();
    videoStreamerNN.registerOutput(ObjDet);
    if (videoStreamerNN.begin() != 0) {
        Serial.println("NN StreamIO link start failed");
    }
    Camera.channelBegin(CHANNELNN);

    OSD.configVideo(CHANNEL, config);
    OSD.begin();

    Serial.print("RTSP stream: rtsp://");
    Serial.print(ip);
    Serial.print(":");
    Serial.println(rtsp_portnum);
}

void loop()
{
    std::vector<ObjectDetectionResult> results = ObjDet.getResult();
    const int resultCount = ObjDet.getResultCount();
    const uint16_t imageWidth = config.width();
    const uint16_t imageHeight = config.height();
    int acceptedCount = 0;

    OSD.createBitmap(CHANNEL);

    for (int i = 0; i < resultCount; i++) {
        const int objType = results[i].type();
        ObjectDetectionResult item = results[i];
        const float centerX = (item.xMin() + item.xMax()) * 0.5f;
        const float centerY = (item.yMin() + item.yMax()) * 0.5f;
        const bool insideTray = pointInsideTray(centerX, centerY);

        printf("RAW class_id=%d center_norm=%.4f,%.4f inside_tray=%d\n",
               objType, centerX, centerY, insideTray ? 1 : 0);

        // Ignore detections whose center is outside the tray polygon.
        if (!insideTray) {
            continue;
        }

        acceptedCount++;
        const int xmin = (int)(item.xMin() * imageWidth);
        const int xmax = (int)(item.xMax() * imageWidth);
        const int ymin = (int)(item.yMin() * imageHeight);
        const int ymax = (int)(item.yMax() * imageHeight);

        printf("TRAY class_id=%d score=%d box=%d,%d,%d,%d center_norm=%.3f,%.3f\n",
               objType, item.score(), xmin, ymin, xmax, ymax,
               centerX, centerY);

        OSD.drawRect(CHANNEL, xmin, ymin, xmax, ymax, 3, OSD_COLOR_WHITE);
        char text[32];
        snprintf(text, sizeof(text), "class %d %d", objType, item.score());
        OSD.drawText(CHANNEL, xmin, ymin - OSD.getTextHeight(CHANNEL), text, OSD_COLOR_CYAN);
    }

    printf("Detected=%d, accepted_inside_tray=%d\n", resultCount, acceptedCount);
    OSD.update(CHANNEL);
    delay(100);
}
