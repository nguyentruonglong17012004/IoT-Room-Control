from datetime import datetime
from typing import List, Optional, AsyncGenerator
import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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

    telemetry = Telemetry(
        device_id=payload.device_id,
        ts=datetime.utcnow(),
        metric_type=payload.metric_type,
        value=payload.value,
        payload=payload.payload,
    )
    db.add(telemetry)

    room = None
    if device.room_id is not None:
        room = db.query(Room).filter(Room.id == device.room_id).first()
        if room and not room.status:
            status = RoomStatus(room_id=room.id, people_count=0, temperature=None)
            db.add(status)
            db.flush()
            room.status = status

    if payload.metric_type == "people_count" and room and room.status:
        try:
            room.status.people_count = int(payload.value or 0)
        except (TypeError, ValueError):
            room.status.people_count = 0

    elif payload.metric_type == "room_temperature" and room and room.status:
        room.status.temperature = payload.value

    elif payload.metric_type == "device_state":
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
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device không tồn tại")

    if device.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem device này")

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


@router.get("/devices/{device_id}/telemetry/stream")
async def stream_device_telemetry(
    device_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    SSE stream: đẩy event mới theo thời gian thực (poll DB mỗi 1s).
    Frontend dùng EventSource để subscribe.
    """
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device không tồn tại")

    if device.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem device này")

    async def gen() -> AsyncGenerator[bytes, None]:
        last_ts: Optional[datetime] = None
        while True:
            q = db.query(Telemetry).filter(Telemetry.device_id == device_id)
            if last_ts:
                q = q.filter(Telemetry.ts > last_ts)
            rows = q.order_by(Telemetry.ts.asc()).limit(50).all()

            for r in rows:
                last_ts = r.ts
                payload = {
                    "ts": r.ts.isoformat() + "Z",
                    "metric_type": r.metric_type,
                    "value": r.value,
                    "payload": r.payload,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")

            await asyncio.sleep(1)

    return StreamingResponse(gen(), media_type="text/event-stream")
