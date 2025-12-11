from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Device, Telemetry, User, Room, RoomStatus
from app.schemas import TelemetryIn, TelemetryOut

router = APIRouter(tags=["telemetry"])


@router.post("/ingest/telemetry")
def ingest_telemetry(
    payload: TelemetryIn,
    db: Session = Depends(get_db),
):
    """
    Endpoint cho thiết bị IoT gửi dữ liệu:
    - metric_type = "people_count"        -> cập nhật số người trong phòng
    - metric_type = "room_temperature"    -> cập nhật nhiệt độ phòng
    - metric_type = "device_state"        -> cập nhật trạng thái thiết bị (on/off, value)
    - metric khác                         -> chỉ lưu vào bảng telemetry
    """
    device = (
        db.query(Device)
        .filter(
            Device.device_id == payload.device_id,
            Device.api_key == payload.api_key,
            Device.is_active == 1,
        )
        .first()
    )
    if not device:
        raise HTTPException(status_code=401, detail="Device không hợp lệ")

    # Lưu bản ghi telemetry gốc
    telemetry = Telemetry(
        device_id=payload.device_id,
        ts=datetime.utcnow(),
        metric_type=payload.metric_type,
        value=payload.value,
        payload=payload.payload,
    )
    db.add(telemetry)

    # Chuẩn bị cập nhật trạng thái phòng / thiết bị cho dashboard
    room = None
    if device.room_id is not None:
        room = db.query(Room).filter(Room.id == device.room_id).first()
        if room and not room.status:
            status = RoomStatus(
                room_id=room.id,
                people_count=0,
                temperature=None,
            )
            db.add(status)
            db.flush()  # để room.status trỏ tới object vừa tạo
            room.status = status

    # Cập nhật giá trị tổng hợp
    if payload.metric_type == "people_count" and room and room.status:
        try:
            room.status.people_count = int(payload.value or 0)
        except (TypeError, ValueError):
            room.status.people_count = 0

    elif payload.metric_type == "room_temperature" and room and room.status:
        room.status.temperature = payload.value

    elif payload.metric_type == "device_state":
        # payload.payload có thể chứa is_on, value ...
        if payload.payload:
            if "is_on" in payload.payload:
                device.is_on = bool(payload.payload["is_on"])
            if "value" in payload.payload:
                try:
                    device.value = float(payload.payload["value"])
                except (TypeError, ValueError):
                    pass

    db.commit()
    return {"status": "ok"}


@router.get("/devices/{device_id}/telemetry", response_model=List[TelemetryOut])
def get_device_telemetry(
    device_id: str,
    limit: int = 300,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trả danh sách telemetry của 1 device (log dữ liệu thô).
    """
    # Kiểm tra device có tồn tại và thuộc về user hiện tại không
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device không tồn tại")

    if device.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem device này")

    # Giới hạn limit cho an toàn
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000

    rows = (
        db.query(Telemetry)
        .filter(Telemetry.device_id == device_id)
        .order_by(Telemetry.ts.desc())
        .limit(limit)
        .all()
    )

    return rows
