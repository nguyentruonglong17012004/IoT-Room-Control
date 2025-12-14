# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from dotenv import load_dotenv
# ==== Load .env ====
ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)
from app.db import Base, engine

# Import từng router
from app.api.routes_auth import router as auth_router
from app.api.routes_devices import router as devices_router
from app.api.routes_telemetry import router as telemetry_router
from app.api.routes_room import router as room_router
from app.api.routes_frontend import router as frontend_router
from app.api.routes_system import router as system_router
from app.api.routes_admin import router as admin_router
from app.api.routes_attendance import router as attendance_router
from fastapi.middleware.cors import CORSMiddleware
# ==== App chính ====
app = FastAPI(title="IoT Room Controlr")
@app.on_event("startup")
def _startup_db():
    Base.metadata.create_all(bind=engine)
origins = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "https://nguyentruonglong17012004.github.io",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import os
print("DEBUG CWD =", os.getcwd())
print("DEBUG SECRET_KEY LEN =", len(os.getenv("SECRET_KEY") or ""))





# ==== Static (nếu bạn có css/js riêng) ====
FRONTEND_DIR = ROOT_DIR / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# ==== Gắn routers ====
app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(telemetry_router)
app.include_router(room_router)
app.include_router(frontend_router)
app.include_router(system_router)
app.include_router(admin_router)
app.include_router(attendance_router)

