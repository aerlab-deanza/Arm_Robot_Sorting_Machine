# Current Pipeline Limits

Ready for a detection demo. Automatic picking still needs work.

Applies to [tray_object_pipeline.py](../vision/tray_object_pipeline.py). See [current pipeline](computer_vision_pipeline.md) for the steps and [findings](documentation.md) for setup decisions.

## 1. No robot coordinates

- Reports tray positions from 0 to 1. No positions in millimeters relative to the arm.
- No camera calibration or lens-distortion correction.
- **Needed:** Calibrate camera-to-arm mapping. Measure position error across the whole tray.

## 2. No grasp height or angle

- Finds the center of a colored region. This may not be a good gripping point.
- No object height, gripper angle, or clearance estimate.
- Angled camera views can shift the apparent positions of tall objects. Straightening the tray does not fix object height.
- **Needed:** Define pick heights and grip rules for the supported objects. Add height sensing if needed.

## 3. Lighting still affects detection

- Fixed color limits. Shadows, glare, exposure, and white balance can change which pixels pass.
- Black tray reduces shadow interference. Does not remove it completely.
- Other dark surfaces can be mistaken for the tray.
- **Needed:** Keep lighting consistent. Check detection under expected lighting changes.

## 4. Limited object support

- Labels red, orange, and purple. Does not identify object types.
- Touching objects of similar color can merge. Hidden objects may be missed.
- Small or narrow objects can fail the size and shape filters.
- Overlap suppression can remove a real object when boxes overlap strongly.
- **Needed:** Define supported objects and spacing. Improve separation or detection for harder cases.

## 5. Tray border can crop objects

- Mask follows four tracked corners. No extra space beyond the border.
- Tall objects near an edge can extend outside the mask and get cropped.
- Tray must pass shape checks and stay away from the image border.
- **Needed:** Keep objects inside a suitable picking area. Adjust camera angle or masking if tall objects are required.

## 6. No stable target confirmation

- Tray corners are smoothed. Objects have no tracking IDs or position smoothing.
- Object positions can jump between frames. No check that a target stopped moving.
- Tracker keeps the old tray outline for up to 8 missed frames.
- **Needed:** Require several consistent object detections before picking. Reject uncertain or outdated targets.

## 7. Two-second wait does not detect hands

- Countdown starts after first finding the tray. Gives time to move hands away.
- Does not check that hands are gone or the tray stayed still.
- **Needed:** A reliable clear-workspace check before arm movement. The countdown alone is insufficient.

## 8. Stream freshness and recovery are limited

- No frame-age check. Buffered video can show an old object position.
- No automatic reconnect after the script exits on repeated read failures.
- **Needed:** Check frame freshness. Stop issuing targets when video fails. Add reconnect handling.

## 9. No arm control or pick feedback

- Displays boxes and prints positions. No target commands sent to the arm.
- No reach checks, collision checks, movement handshake, or pick-success check.
- **Needed:** Connect to the arm controller. Check targets before movement. Confirm completion and handle failed picks.

## 10. Performance and accuracy unmeasured

- No measured position error, detection accuracy, or pick success rate.
- Speed on cheaper boards has not been benchmarked with this script.
- A correct-looking box does not prove the arm can grip the object.
- **Needed:** Measure accuracy, delay, and processing speed on the actual setup.

## What to address first

1. Calibrate camera-to-arm coordinates. Measure position error.
2. Define supported objects, pick heights, and grip angles.
3. Confirm stable, fresh targets and a clear workspace.
4. Connect the arm controller and handle movement failures.
5. Measure repeated pick success across the tray.
