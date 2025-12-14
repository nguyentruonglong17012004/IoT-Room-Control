from flask import Flask, Response
import cv2
import time

app = Flask(__name__)

# 0 = camera mặc định laptop
cap = cv2.VideoCapture(0)

# chỉnh độ phân giải (nhẹ hơn -> mượt hơn)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
cap.set(cv2.CAP_PROP_FPS, 20)

def gen():
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(0.1)
            continue

        # nén JPEG: số càng cao càng rõ nhưng nặng (60-80 là ổn)
        ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if not ok:
            continue

        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")

@app.get("/stream")
def stream():
    return Response(gen(), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.get("/")
def index():
    return "OK. Open /stream"

if __name__ == "__main__":
    # host 0.0.0.0 để ngrok / máy khác truy cập được
    app.run(host="0.0.0.0", port=5000, threaded=True)
