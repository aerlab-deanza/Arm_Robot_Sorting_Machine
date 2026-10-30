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

The docs have animations and plain-language explanations. Click a link below to open one.

![Tour of the docs: each guide has animations and short explanations](docs/images/docs-tour.gif)

- [Current pipeline](docs/computer_vision_pipeline.md) — Steps, algorithms, and current output.
- [Findings and setup decisions](docs/documentation.md) — Image comparisons showing why we chose this setup.
- [Pipeline limits](docs/limitation.md) — Current limits and work needed before automatic picking.
- [Task Delegation](docs/task_delegation.md) — Manim animations, narration, and render commands.

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

