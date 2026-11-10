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

The whole pipeline in about 50 seconds:

![The vision pipeline, from camera picture to cap color and position](docs/images/pipeline/09a-recap.gif)

- [Current pipeline](docs/computer_vision_pipeline.md) - Steps, algorithms, and current output.
- [Findings and setup decisions](docs/documentation.md) - Image comparisons showing why we chose this setup.
- [What is left to do](docs/task_delegation.md) - The 3 open tasks: goal, steps, how to check you're done, and code help.

### Folder map

<pre>
Arm_Robot_Sorting_Machine/
+-- <a href="vision/">vision/</a>                        Python code that runs on the PC
|   +-- <a href="vision/tray_object_pipeline.py">tray_object_pipeline.py</a>    Entry point: runs all steps, shows windows, prints cap positions
|   +-- <a href="vision/camera.py">camera.py</a>                  Opens the USB camera or the network stream
|   +-- <a href="vision/tray.py">tray.py</a>                    Finds, steadies, locks and straightens the tray
|   +-- <a href="vision/caps.py">caps.py</a>                    Finds caps by color and steadies their boxes
+-- <a href="firmware/TrayObjectDetection/">firmware/TrayObjectDetection/</a>  Sketch for the AMB82-Mini camera board (Arduino)
+-- <a href="docs/">docs/</a>                          Guides, findings and the open tasks
|   +-- <a href="docs/images/">images/</a>                    Screenshots and GIFs used by the guides
|   +-- <a href="docs/animations/">animations/</a>                Scripts that make the GIFs (Manim)
+-- <a href="requirements.txt">requirements.txt</a>               Python packages for the vision code
+-- <a href="AGENTS.md">AGENTS.md</a>                      Instructions for AI coding agents
+-- <a href="README.md">README.md</a>                      This file
</pre>

### How the code fits together

1. **Camera.** The AMB82-Mini streams video over the network (RTSP). A USB or laptop camera works too. `camera.py` opens either one and gives the program one picture (frame) at a time.
2. **Tray.** `tray.py` finds the black tray in the picture, keeps its outline steady, locks it, and straightens it into a top-down view.
3. **Caps.** `caps.py` finds red, blue and purple caps, and keeps their boxes steady.
4. **Output.** `tray_object_pipeline.py` shows six windows and prints one JSON line per second with each cap's color and position as a fraction of the tray (`u` across, `v` down, 0 to 1). The "Rectified tray / detected objects" window also shows how many caps were found. It does not give robot millimeters yet. See [what is left to do](docs/task_delegation.md).

```text
camera  ->  camera.py  ->  tray.py  ->  caps.py  ->  tray_object_pipeline.py
```

### Important files

- [tray_object_pipeline.py](vision/tray_object_pipeline.py) - Entry point. Shows the windows and prints the cap positions on the PC.
- [camera.py](vision/camera.py) - Opens the USB camera or network stream.
- [tray.py](vision/tray.py) - Finds, steadies, locks and straightens the tray.
- [caps.py](vision/caps.py) - Finds caps by color and steadies their boxes.
- [requirements.txt](requirements.txt) - Python packages used by the vision script.

### Commands

Run commands in PowerShell from the project folder. Replace `192.168.0.25` if the camera IP changes.

Install the Python packages needed by the vision script:

```powershell
python -m pip install -r requirements.txt
```

Run tray and object detection with camera

The pipeline looks for a black tray. It waits 0.5 seconds after first finding it, so keep your hand out of the tray during this time.

- **Tray lock:** once the outline stays still for 0.75 seconds, it locks (cyan, `TRAY LOCKED`). A hand or glare can't move it. Press `r` in a window to find the tray again. The tray unlocks by itself if the tray really moves.
- **Steady caps:** a cap shows only after it is seen in 3 of the last 5 frames. A new or removed cap appears or disappears about 3 frames late.

USB Camera:

``*NOTES: If you don't have USB Camera plugged in, this command could be used for your laptop camera.``
```powershell
python vision/tray_object_pipeline.py --camera-index 0
```

Laptop Camera:
```powershell
python vision/tray_object_pipeline.py --camera-index 1
```

If a dark floor or chair makes "TRAY NOT FOUND", search only inside a rectangle around the tray (left, top, right, bottom, as fractions of the picture; it is drawn in orange):
```powershell
python vision/tray_object_pipeline.py --camera-index 0 --tray-region 0.05,0.28,0.95,0.97
```

If the picture changes color when something white moves in view (the black tray turns blue), freeze the camera's automatic white balance and exposure. USB camera only, and some cameras ignore it:
```powershell
python vision/tray_object_pipeline.py --camera-index 0 --lock-camera
```

No windows (for the robot PC). It prints one JSON line per frame with the tray state and the caps' positions. Stop with Ctrl+C:
```powershell
python vision/tray_object_pipeline.py --camera-index 0 --no-gui
```

