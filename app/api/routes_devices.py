# app/api/routes_devices.py
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Literal, Optional

from app.api.deps import get_db, get_current_user
from app.models import Device, User, Telemetry

router = APIRouter(prefix="/devices", tags=["devices"])


class DeviceCommand(BaseModel):
    command_type: Literal["toggle"] = "toggle"
    payload: Optional[dict] = None


@router.post("/{device_id}/commands")
def send_device_command(
    device_id: str,
    cmd: DeviceCommand,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.device_id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found in DB")

    # mô phỏng: cho phép điều khiển đèn + quạt + AC đều toggle được
    if cmd.command_type != "toggle":
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ toggle")

    # Toggle DB ngay để UI đổi liền
    device.is_on = not bool(device.is_on)

    # giá trị hiển thị:
    # - LIGHT: 1/0
    # - FAN:   mô phỏng tốc độ 1/0 (bật=tốc 1)
    # - AC:    mô phỏng bật/tắt (value giữ nguyên nếu muốn)
    if device.device_type is None:
        device.value = 1.0 if device.is_on else 0.0
    else:
        if device.device_type.name in ("LIGHT", "FAN"):
            device.value = 1.0 if device.is_on else 0.0

    # log lịch sử (dashboard "Lịch sử" đang đọc telemetry theo device)
    db.add(
        Telemetry(
            device_id=device.device_id,
            ts=datetime.utcnow(),
            metric_type="device_state",
            value=1.0 if device.is_on else 0.0,
            payload={"is_on": bool(device.is_on), "source": "dashboard"},
        )
    )
    db.commit()

    return {"status": "ok", "new_state": bool(device.is_on)}
