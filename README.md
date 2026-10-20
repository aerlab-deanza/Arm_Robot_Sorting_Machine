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
[Computer vision pipeline guide](docs/computer_vision_pipeline.md) — Documents of the progress to improve the Computer Vision Pipeline

### Important files

- [TrayObjectDetection.ino](firmware/TrayObjectDetection/TrayObjectDetection.ino) — AMB82-Mini camera and object-detection sketch.
- [ObjectDetectionSetup.ino](firmware/TrayObjectDetection/ObjectDetectionSetup/ObjectDetectionSetup.ino) — Realtek object-detection example.
- [ObjectClassList.h](firmware/TrayObjectDetection/ObjectDetectionSetup/ObjectClassList.h) — Class names used by the example.
- [tray_object_pipeline.py](vision/tray_object_pipeline.py) — Finds the tray and colored objects on the PC.
- [requirements.txt](requirements.txt) — Python packages used by the vision script.

### Commands

Run these in PowerShell from the project folder. Replace `192.168.0.25` if the camera IP changes.

Install the Python packages:

```powershell
python -m pip install -r requirements.txt
```

View the camera in VLC: open **Media → Open Network Stream**, enter `rtsp://192.168.0.25:554`, then click **Play**.

View the camera in FFplay with low buffering:

```powershell
ffplay -rtsp_transport udp -fflags nobuffer -flags low_delay -framedrop -an "rtsp://192.168.0.25:554"
```

Run tray and object detection with the AMB82-Mini stream:

```powershell
python vision/tray_object_pipeline.py --url rtsp://192.168.0.25:554
```

Run it with a USB camera (index `0`):

```powershell
python vision/tray_object_pipeline.py --camera-index 0
```

If OpenCV cannot read the RTSP stream, start the VLC relay in one PowerShell window:

```powershell
& "C:\Program Files\VideoLAN\VLC\vlc.exe" --no-one-instance -I dummy "rtsp://192.168.0.25:554" --sout "#std{access=http,mux=ts,dst=:8090/stream}" --sout-keep
```

Then run the pipeline through the relay in another window:

```powershell
python vision/tray_object_pipeline.py --url http://127.0.0.1:8090/stream
```
