"""Open the camera: a USB camera index or an RTSP / network stream."""

import os
import sys


def _configure_ffmpeg_from_args():
    """Set FFmpeg network options from the command line, before OpenCV loads.

    OpenCV reads the ``OPENCV_FFMPEG_CAPTURE_OPTIONS`` environment variable
    only once, when it is imported, so this runs before ``import cv2``. It
    looks at ``--url`` and ``--transport`` directly in ``sys.argv``.
    """
    url = "rtsp://192.168.0.25:554"
    transport = "auto"
    args = sys.argv[1:]
    for i, arg in enumerate(args[:-1]):
        if arg == "--url":
            url = args[i + 1]
        elif arg == "--transport":
            transport = args[i + 1]

    if url.lower().startswith(("http://", "https://")):
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "timeout;7000000"
    elif transport == "udp":
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_transport;udp|timeout;7000000"
        )
    else:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
            "rtsp_flags;prefer_tcp|timeout;7000000"
        )


_configure_ffmpeg_from_args()


import cv2  # noqa: E402  (must load after the FFmpeg options are set)


def open_capture(source, transport):
    """Open a USB camera or a network video stream.

    For a USB camera, tries the Windows camera backends in turn and skips any
    that only give black frames. For RTSP with ``transport="auto"``, tries
    TCP first, then UDP.

    Args:
        source: Camera index (int, e.g. 0) or stream URL (str, e.g.
            "rtsp://192.168.0.25:554").
        transport: "auto", "tcp" or "udp". Only used for RTSP URLs.

    Returns:
        An opened cv2.VideoCapture.

    Raises:
        SystemExit: If no usable video can be opened. The message says what
            to check.
    """
    if isinstance(source, int):
        backends = []
        for name, backend in (
            ("DirectShow", "CAP_DSHOW"),
            ("Media Foundation", "CAP_MSMF"),
            ("default", "CAP_ANY"),
        ):
            api = getattr(cv2, backend, None)
            if api is not None and all(api != existing[1] for existing in backends):
                backends.append((name, api))

        for name, api in backends:
            video = cv2.VideoCapture(source, api)
            if video.isOpened():
                video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                # Some Windows camera backends report an open device but return
                # black startup frames. Skip those before choosing a backend.
                for _ in range(8):
                    ok, frame = video.read()
                    if (ok and frame is not None and frame.size and
                            (frame.max() > 2 or frame.mean() > 1)):
                        print(
                            "Connected to USB camera index {} using {}.".format(
                                source, name
                            ),
                            flush=True,
                        )
                        return video
                print(
                    "Camera index {} opened with {}, but returned empty/black frames."
                    .format(source, name),
                    flush=True,
                )
            video.release()
        raise SystemExit(
            "Could not get a usable image from USB camera index {}. Try another "
            "index, close apps using the camera, and check Windows Camera "
            "privacy settings.".format(source)
        )

    timeout = []
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 7000]
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        timeout += [cv2.CAP_PROP_READ_TIMEOUT_MSEC, 7000]
    is_rtsp = source.lower().startswith("rtsp://")
    transports = ("tcp", "udp") if is_rtsp and transport == "auto" else (transport,)
    last_error = None
    for attempt_transport in transports:
        if is_rtsp:
            if attempt_transport == "udp":
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_transport;udp|timeout;7000000"
                )
            else:
                os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = (
                    "rtsp_flags;prefer_tcp|timeout;7000000"
                )
            print("Trying RTSP over {}...".format(attempt_transport.upper()), flush=True)
        try:
            if timeout:
                video = cv2.VideoCapture(source, cv2.CAP_FFMPEG, timeout)
            else:
                video = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
        except (TypeError, cv2.error) as exc:
            last_error = exc
            break
        if video.isOpened():
            video.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            print("Connected{}.".format(
                " using " + attempt_transport.upper() if is_rtsp else ""
            ), flush=True)
            return video
        video.release()
        print("{} connection attempt failed.".format(
            attempt_transport.upper() if is_rtsp else "Video source"
        ), flush=True)

    if last_error is not None:
        raise SystemExit("OpenCV could not open the video source: {}".format(last_error))
    raise SystemExit(
        "Could not open {} over {}. Confirm the board is streaming, use the exact "
        "RTSP URL shown by its sketch, and close VLC if the camera permits only "
        "one viewer. You can force one transport with --transport tcp or udp."
        .format(source, "/".join(t.upper() for t in transports))
    )
