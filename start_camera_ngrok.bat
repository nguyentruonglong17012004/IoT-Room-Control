@echo off
cd /d "C:\IoT Control Room"
call venv\Scripts\activate

for /f "usebackq tokens=1,* delims==" %%A in (".env.camera") do (
  set "%%A=%%B"
)

start "camera-proxy" cmd /k python -m uvicorn camera_proxy:app --host 0.0.0.0 --port %CAM_PROXY_PORT%
start "ngrok" cmd /k ngrok http %CAM_PROXY_PORT%
