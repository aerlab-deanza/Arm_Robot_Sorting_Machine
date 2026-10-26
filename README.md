# Arm Robot Sorting Machine

## Authors

|  |  |
|:---|:---|
|  |  |
|  |  |
|  |  |

---

## Computer Vision
### Documents

- [Current pipeline](docs/computer_vision_pipeline.md) — Steps, algorithms, and current output.
- [Findings and setup decisions](docs/documentation.md) — Image comparisons showing why we chose this setup.
- [Pipeline limits](docs/limitation.md) — Current limits and work needed before automatic picking.
- [Video project](video/README.md) — Manim animations, narration, and render commands.

### Important files

- [TrayObjectDetection.ino](firmware/TrayObjectDetection/TrayObjectDetection.ino) — AMB82-Mini camera and object-detection sketch.
- [ObjectDetectionSetup.ino](firmware/TrayObjectDetection/ObjectDetectionSetup/ObjectDetectionSetup.ino) — Realtek object-detection example.
- [ObjectClassList.h](firmware/TrayObjectDetection/ObjectDetectionSetup/ObjectClassList.h) — Class names used by the example.
- [tray_object_pipeline.py](vision/tray_object_pipeline.py) — Finds the tray and colored objects on the PC.
- [requirements.txt](requirements.txt) — Python packages used by the vision script.

### Commands

Run commands in PowerShell from the project folder. Replace `192.168.0.25` if the camera IP changes.

Install the Python packages needed by the vision script:

```powershell
python -m pip install -r requirements.txt
```

Run tray and object detection with camera

The pipeline looks for a black tray. It waits 2 seconds after first finding it, so move your hand away during this time. The mask follows the detected tray corners.

USB Camera:
```powershell
python vision/tray_object_pipeline.py --camera-index 0
```

Laptop Camera:
```powershell
python vision/tray_object_pipeline.py --camera-index 1
```

View the live camera stream in VLC: open **Media → Open Network Stream**, enter `rtsp://192.168.0.25:554`, then click **Play**.

View the live camera stream in FFplay with low buffering:

```powershell
ffplay -rtsp_transport udp -fflags nobuffer -flags low_delay -framedrop -an "rtsp://192.168.0.25:554"
```

Run tray and object detection on the PC using the AMB82-Mini camera stream:

```powershell
python vision/tray_object_pipeline.py --url rtsp://192.168.0.25:554
```

If OpenCV cannot read the RTSP stream, start this VLC relay. It converts the
camera stream to local HTTP. Keep this PowerShell window open:

```powershell
& "C:\Program Files\VideoLAN\VLC\vlc.exe" --no-one-instance -I dummy "rtsp://192.168.0.25:554" --sout "#std{access=http,mux=ts,dst=:8090/stream}" --sout-keep
```

In a second PowerShell window, run detection using the local HTTP relay:

```powershell
python vision/tray_object_pipeline.py --url http://127.0.0.1:8090/stream
```
