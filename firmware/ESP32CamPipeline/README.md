# ESP32CamPipeline

The tray and cap pipeline running **on the ESP32-CAM itself**. It finds the black tray and the red, blue and purple caps, and prints one line of JSON per frame on the serial port. No PC is needed while it runs.

It is a C++ copy of the Python pipeline in [`vision/`](../../vision/), made smaller to fit the board.

## What you need

- An **ESP32-CAM** (AI-Thinker, with the OV2640 camera and PSRAM).
- A **USB-to-serial adapter** (FTDI, 3.3 V) to upload code, or an ESP32-CAM-MB programmer board.
- The **Arduino IDE** (2.x).
- The black tray, caps and light, as for the Python program.

## 1. Set up the Arduino IDE (once)

1. Open **File > Preferences**. In "Additional boards manager URLs" add:
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json`
2. Open **Tools > Board > Boards Manager**, search `esp32`, and install **esp32 by Espressif Systems**.
3. Open `firmware/ESP32CamPipeline/ESP32CamPipeline.ino`.
4. Set the board:
   - **Tools > Board > ESP32 Arduino > AI Thinker ESP32-CAM**
   - **Tools > PSRAM > Enabled**
   - **Tools > CPU Frequency > 240 MHz**
   - **Tools > Partition Scheme > Huge APP (3MB No OTA/1MB SPIFFS)**

## 2. Upload

1. Wire the adapter: `5V` to `5V`, `GND` to `GND`, `U0R` to adapter `TX`, `U0T` to adapter `RX`.
2. Connect **IO0 to GND** (this puts the board in upload mode).
3. Choose the port in **Tools > Port**, and click **Upload**.
4. When it says "Connecting...", press the **reset** button on the board.
5. After the upload: **remove the IO0-GND wire**, and press reset.

## 3. Run

Open **Tools > Serial Monitor** at **115200 baud**. You will see:

```
# ESP32CamPipeline starting
# running
{"frame": 1, "time_ms": 1203, "tray": "settling", "caps": []}
{"frame": 14, "time_ms": 3340, "tray": "locked", "caps": [{"color": "red", "u": 0.412, "v": 0.688, ...}]}
# frame 20: pipeline 96 ms, free PSRAM 3170 KB
```

- A line starting with `#` is information. A line starting with `{` is a result, in the same format as the Python program's `--no-gui` output.
- `tray` is `settling`, `not_found`, `finding` or `locked`, as in Python.
- Type `r` and press Enter in the Serial Monitor to forget the locked tray and search again.
- `pipeline 96 ms` is how long the pipeline took for that frame. **Please note this number for your board** and add it to the table below.

To read the lines from the robot controller, connect `TX` of the ESP32-CAM (`U0T`) to the controller's receive pin. Use a **common GND**. The ESP32 pins are **3.3 V**, so a 5 V controller needs a level shifter.

## 4. Settings

At the top of `ESP32CamPipeline.ino`:

| Setting | What it does |
| --- | --- |
| `LOCK_CAMERA` (1) | Freezes the camera's automatic exposure, gain and white balance, like `--lock-camera` in Python. `EXPOSURE` (0-1200) and `GAIN` (0-30) are the frozen values: raise `EXPOSURE` if the picture is too dark. |
| `PRINT_TIMING` (1) | Prints the time per frame every 20 frames. |
| `SWAP_BYTES` (0) | Set to 1 if red and blue are swapped in the results. |
| `USE_WIFI_DEBUG` (0) | Set to 1, and enter your Wi-Fi name and password, to open a page at the board's address with the camera picture, the tray outline and the caps. It slows the pipeline while it is open. Turn it off when the robot runs. |

The tuning numbers (brightness limit, color ranges, and so on) are in `firmware/tray_cap_core/tc_types.h`, in `struct Config`, with the same defaults as the Python program. Change them there, run `python firmware/sync_core.py`, and upload again. `src/core` is a copy: do not edit it. `setup()` sets `object_min_side = 8`, because on a 320 x 240 picture a cap is about half as many pixels as on 640 x 480.

## 5. What is different from the Python program

| | Python (PC) | ESP32-CAM |
| --- | --- | --- |
| Picture size | any (we use 640 x 480) | 320 x 240 |
| Speed | about 150 frames/s at 640 x 480 | a few to about 10 frames/s (see the table) |
| Preview windows | six | none; optional Wi-Fi debug page |
| Straightening | blends neighbor pixels | takes the nearest pixel |
| Gap filling, speck removal | round brush | square brush |
| Tray outline | `approxPolyDP` (breaks with a cable) | the 4 main corners (Task 1 is already built in) |
| Camera | your USB camera | OV2640: noisier, weaker colors |
| Settings | command-line flags | edit `Config`, upload again |
| Not included | | `--tray-region` is in the code (`use_region`), but has no setting in the sketch; calibration tools; saved logs |

## 6. How well does it match the Python program?

The test [`tests/test_esp32_parity.py`](../../tests/test_esp32_parity.py) builds the C++ core on the PC, runs it on drawn 320 x 240 pictures, and compares it with the Python pipeline:

```powershell
python -m pytest tests/test_esp32_parity.py
```

It checks that the tray state is the same, the cap colors are the same, positions are within 0.02 of the tray, and box sizes are within 4 pixels. (It needs `g++`. It is skipped without it.)

To run the core on your own picture:

```powershell
sh firmware/tray_cap_core/pc_test/build.sh
firmware/tray_cap_core/pc_test/pc_test picture.rgb 320 240 3 100 --rgb565 --time
```

`picture.rgb` is raw red, green, blue bytes (320 x 240 x 3). Drop `--rgb565` for the AMB82 pixel format, or pass a `.jpg` file.

## 7. Speed on the board

Measured on a PC, the C++ core takes about **2 ms per frame** at 320 x 240. The ESP32-CAM is much slower, and its picture memory (PSRAM) is slower too. Our estimate is **5-10 frames per second**. Fill in your real numbers:

| Board | Settings | `pipeline` time | Frames per second |
| --- | --- | --- | --- |
| *your ESP32-CAM* | 240 MHz, QVGA | *ms* | *fps* |

## 8. If something goes wrong

| You see | Do |
| --- | --- |
| `ERROR: PSRAM not found` | **Tools > PSRAM > Enabled**, and check the board is the AI-Thinker model. |
| `ERROR: camera did not start` | Check the camera ribbon is fully pushed in. Power from a good 5 V supply (USB ports are often too weak). Press reset. |
| Upload fails ("Failed to connect") | IO0 must be connected to GND, and you must press reset when it says "Connecting...". |
| The board restarts again and again | The power supply is too weak. Use 5 V with at least 500 mA, or add a 100 µF capacitor between 5V and GND. |
| `tray` stays `not_found` | The tray must be dark and fully inside the picture, with room around it. Try the Wi-Fi debug page to see what the camera sees. |
| Colors are wrong (red shows as blue) | Set `SWAP_BYTES` to 1. |
| The picture is too dark or too bright | Change `EXPOSURE` (and `GAIN`). |
| Caps are missed | They are small at 320 x 240. Put the camera closer, or lower `object_min_side` in `Config`. |
