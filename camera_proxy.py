import os
import time
import threading

import cv2
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

# Camera index: 0 là webcam mặc định, nếu không lên thử 1
CAM_INDEX = int(os.getenv("CAM_INDEX", "0"))
# Bảo vệ stream (khuyến nghị). Nếu để rỗng "" thì không cần key.
STREAM_KEY = (os.getenv("STREAM_KEY") or "").strip()

JPEG_QUALITY = int(os.getenv("JPEG_QUALITY", "80"))
FPS = float(os.getenv("CAM_FPS", "12"))

app = FastAPI()

_latest = None
_lock = threading.Lock()

def _capture_loop():
    global _latest
    # CAP_DSHOW giúp ổn định hơn trên Windows
    cap = cv2.VideoCapture(CAM_INDEX, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print(f"[CAM] Cannot open camera index={CAM_INDEX}")
        return

    delay = 1.0 / max(FPS, 1.0)

    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
            continue

        ok2, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY])
        if ok2:
            with _lock:
                _latest = jpg.tobytes()

        time.sleep(delay)

@app.on_event("startup")
def startup():
    threading.Thread(target=_capture_loop, daemon=True).start()

def gen():
    boundary = b"--frame"
    while True:
        with _lock:
            jpg = _latest
        if jpg:
            yield boundary + b"\r\n"
            yield b"Content-Type: image/jpeg\r\n"
            yield f"Content-Length: {len(jpg)}\r\n\r\n".encode()
            yield jpg + b"\r\n"
        time.sleep(0.02)

@app.get("/stream")
def stream(key: str = Query(default="")):
    if STREAM_KEY and key != STREAM_KEY:
        raise HTTPException(status_code=403, detail="Bad stream key")
    return StreamingResponse(
        gen(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )
