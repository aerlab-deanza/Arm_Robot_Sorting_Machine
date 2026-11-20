# AMB82Pipeline

The tray and cap pipeline running **on the AMB82-Mini itself**. No PC runs the pipeline. It finds the black tray and the red, blue and purple caps, then:

- prints one line of JSON per frame on the **Serial Monitor** (same format as the Python program's `--no-gui`),
- streams **RTSP video** with the tray outline and the caps drawn on it (open it with VLC).

The code is the same C++ core as the ESP32 version: [`firmware/tray_cap_core/`](../tray_cap_core/). It is tested against the Python pipeline in `tests/test_esp32_parity.py`.

**Status:** it compiles for the AMB82-Mini (checked with arduino-cli, Realtek AmebaPro2 4.1.0). It has **not been run on a real board yet**. Please run it and report the numbers in section 6.

## What you need

- AMB82-Mini with its camera, USB cable.
- Arduino IDE 2.x with the Realtek board package: add this URL in **File > Preferences > Additional boards manager URLs**, then install **Realtek AmebaPro2** in the Boards Manager:
  `https://github.com/Ameba-AIoT/ameba-arduino-pro2/raw/main/Arduino_package/package_realtek_amebapro2_index.json`
- Wi-Fi (for the video). VLC on a PC (to watch it).

## 1. Upload

1. Open `firmware/AMB82Pipeline/AMB82Pipeline.ino`.
2. Put your Wi-Fi name and password in `ssid` and `pass`. **Do not commit them.**
3. **Tools > Board > AMB82-MINI**, choose the port, click **Upload**. (For upload mode, hold UART_DOWNLOAD, press RESET, release both, as the board guide says.)

## 2. Run

Open the Serial Monitor at **115200 baud**:

```
# AMB82Pipeline starting
# video: rtsp://192.168.0.25:554
# running
{"frame": 14, "time_ms": 3340, "tray": "locked", "caps": [{"color": "red", "u": 0.412, "v": 0.688, ...}]}
# frame 20: pipeline 35 ms
```

- Lines starting with `#` are information. Lines starting with `{` are results.
- Open the `rtsp://...` address in VLC to see the video. Cyan outline = tray locked, green = finding. Yellow crosses = caps.
- Type `r` and press Enter to forget the locked tray.

## 3. Settings

At the top of `AMB82Pipeline.ino`:

| Setting | What it does |
| --- | --- |
| `LOCK_CAMERA` (0) | 1 = freeze auto exposure and white balance (like `--lock-camera`). Then `EXPOSURE_TIME` and `GAIN` are the frozen values. Untested numbers: change them until the picture looks right. |
| `USE_TRAY_REGION` (1), `TRAY_REGION` | Only search this box (left, top, right, bottom, as fractions of the picture) for the tray. Needed when other dark things are in view. Move the tray, or change the numbers, if it is not found. |
| `USE_DEBUG_PAGE` (1) | Browser page with 4 views (tray mask, tray localization, object detection, object mask). Open the `http://` address printed in the Serial Monitor. Slows the pipeline while open. Set 0 when the robot runs. |
| `PRINT_TIMING` (1) | Prints the time per frame every 20 frames. |

Tuning numbers (brightness limit, color ranges, ...) are in `firmware/tray_cap_core/tc_types.h`, in `struct Config`. Change them **there**, then run `python firmware/sync_core.py` and upload again. Never edit `src/core` by hand: it is a copy.

## 4. How it works

- Channel 0: H264 1280 x 720 for RTSP. The outline is drawn on it with the board's on-screen-display (OSD).
- Channel 1: JPEG 640 x 360, 10 per second. The sketch cannot read raw pictures from the board, only JPEG. So each JPEG is decoded on the board (small TJpgDec decoder, in `third_party/`), then the pipeline runs.
- JPEG adds small color noise. The test `test_a_jpeg_picture_gives_the_same_answer` checks it still matches Python.

## 5. Different from the Python program

| | Python (PC) | AMB82-Mini |
| --- | --- | --- |
| Picture size | any (we use 640 x 480) | 640 x 360 |
| Pixels | straight from the camera | after JPEG decoding |
| Straightening | blends neighbor pixels | nearest pixel |
| Tray outline | `approxPolyDP` | the 4 main corners (Task 1 built in) |
| Preview windows | six | RTSP video with outline |
| Settings | command-line flags | edit `Config`, upload again |

## 6. Numbers to report

| What | Value |
| --- | --- |
| `pipeline` time in the Serial Monitor | *ms* |
| Frames per second of the JSON lines | *fps* |
| Does the outline match the real tray in VLC? | *yes / no* |

## 7. If something goes wrong

| You see | Do |
| --- | --- |
| `# Wi-Fi did not connect` | Check name and password. The pipeline still runs, but there is no video. |
| `# no usable picture` again and again | The JPEG channel did not start or the picture is not 640 x 360. Press reset. |
| `tray` stays `not_found` | The tray must be dark and fully in view. Check the video in VLC. |
| Colors wrong or washed out | Try `LOCK_CAMERA 1` and change `EXPOSURE_TIME`. |
| Caps missed | Move the camera closer or lower `object_min_side` in `Config`. |
