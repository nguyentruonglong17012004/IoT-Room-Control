# app/api/routes_room.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
import secrets

from app.api.deps import get_db, get_current_user
from app.models import Room, RoomStatus, Device, Telemetry, User, DeviceType

router = APIRouter(prefix="/rooms", tags=["rooms"])


def _generate_unique_api_key(db: Session, nbytes: int = 16) -> str:
    for _ in range(20):
        k = secrets.token_hex(nbytes)
        if not db.query(Device).filter(Device.api_key == k).first():
            return k
    raise HTTPException(status_code=500, detail="Không thể sinh api_key")


def _ensure_room1_devices(db: Session, owner_id: int) -> Room:
    # Room 1 (KD)
    room = db.query(Room).filter(Room.id == 1).first()
    if not room:
        room = Room(id=1, name="Phòng Kinh Doanh", description="Sales Office")
        db.add(room)
        db.flush()

    # RoomStatus
    if not room.status:
        st = RoomStatus(room_id=room.id, people_count=0, temperature=None)
        db.add(st)
        db.flush()

    defaults = [
    ("KD_DOOR_1", "Cửa chính", None, 2, 1),
]


    for did, name, dtype, x, y in defaults:
        dev = db.query(Device).filter(Device.device_id == did).first()
        if not dev:
            dev = Device(
                device_id=did,
                name=name,
                owner_id=owner_id,
                api_key=_generate_unique_api_key(db),
                room_id=room.id,
                device_type=dtype,
                pos_x=float(x),
                pos_y=float(y),
                is_active=1,
                is_on=False,
                value=0.0,
            )
            db.add(dev)

    db.commit()
    db.refresh(room)
    return room


def _latest_metric_for_room(db: Session, room_id: int, metric_type: str):
    dev_ids = [r[0] for r in db.query(Device.device_id).filter(Device.room_id == room_id).all()]
    if not dev_ids:
        return None

    row = (
        db.query(Telemetry)
        .filter(Telemetry.device_id.in_(dev_ids), Telemetry.metric_type == metric_type)
        .order_by(desc(Telemetry.ts))
        .first()
    )
    return row.value if row else None


@router.get("")
def list_rooms(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_room1_devices(db, current_user.id)
    rooms = db.query(Room).order_by(Room.id.asc()).all()
    return [{"id": r.id, "name": r.name, "description": r.description} for r in rooms]


@router.get("/{room_id}/status")
def room_status(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if room_id != 1:
        raise HTTPException(status_code=404, detail="Demo hiện chỉ dùng phòng 1")

    room = _ensure_room1_devices(db, current_user.id)
    devices = db.query(Device).filter(Device.room_id == room.id).order_by(Device.id.asc()).all()

    people = int(room.status.people_count or 0) if room.status else 0

    # Nếu chưa có sensor thật -> mặc định 0
    if room.status and room.status.temperature is not None:
        temp = float(room.status.temperature)
    else:
        v = _latest_metric_for_room(db, room.id, "room_temperature")
        temp = float(v) if v is not None else 0.0

    hv = _latest_metric_for_room(db, room.id, "room_humidity")
    humidity = float(hv) if hv is not None else 0.0

    def dtype_str(d: Device) -> str:
        # dashboard.html đang switch theo "LIGHT"/"FAN"/"AC"
        if d.device_type is None:
            return "LIGHT"
        return d.device_type.name  # LIGHT/FAN/AC

    return {
        "room": {
            "id": room.id,
            "name": room.name,
            "description": room.description,
            "status": {
                "people_count": people,
                "temperature": temp,
                "humidity": humidity,
            },
            "devices": [
                {
                    "id": d.id,
                    "device_id": d.device_id,
                    "name": d.name,
                    "device_type": dtype_str(d),
                    "pos_x": int(d.pos_x or 0),
                    "pos_y": int(d.pos_y or 0),
                    "is_on": bool(d.is_on),
                    "value": float(d.value) if d.value is not None else (1.0 if d.is_on else 0.0),
                }
                for d in devices
            ],
        }
    }
