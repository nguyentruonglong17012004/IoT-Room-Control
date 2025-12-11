from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Device, User
from app.schemas import DeviceCreate, DeviceOut, DeviceCommandIn
from app.mqtt_publisher import publish_device_command
from app.security import generate_device_api_key

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("", response_model=DeviceOut)
def create_device(
    device_in: DeviceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tạo thiết bị mới và gán cho user hiện tại.
    """
    existing = (
        db.query(Device)
        .filter(Device.device_id == device_in.device_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Device ID đã tồn tại",
        )

    api_key = generate_device_api_key()
    device = Device(
        device_id=device_in.device_id,
        name=device_in.name,
        owner_id=current_user.id,
        api_key=api_key,
    )
    db.add(device)
    db.commit()
    db.refresh(device)
    return device


@router.get("", response_model=List[DeviceOut])
def list_devices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Liệt kê thiết bị thuộc về user hiện tại.
    """
    devices = (
        db.query(Device)
        .filter(Device.owner_id == current_user.id)
        .all()
    )
    return devices


@router.post("/{device_id}/commands")
def send_device_command(
    device_id: str,
    cmd: DeviceCommandIn,
    current_user: User = Depends(get_current_user),
):
    """
    Gửi lệnh xuống device qua MQTT.

    ***Lưu ý***
    - KHÔNG còn kiểm tra device trong DB nữa.
    - Cho phép dùng luôn các device_id mock như KD_LIGHT_1, MKT_FAN_1,...
    """
    command = {
        "device_id": device_id,
        "command_type": cmd.command_type,
        "payload": cmd.payload or {},
    }

    # publish ra MQTT (tùy bạn triển khai trong mqtt_publisher)
    publish_device_command(device_id, command)
    return {"status": "queued"}


@router.get("/{device_id}/telemetry")
def get_device_telemetry(
    device_id: str,
    limit: int = 200,
    current_user: User = Depends(get_current_user),
):
    """
    Trả về lịch sử bật/tắt (telemetry) của 1 thiết bị.

    HIỆN TẠI: dùng dữ liệu MOCK để demo UI lịch sử.
    - KHÔNG kiểm tra device trong DB nữa
    - Trả về tối đa 10 bản ghi, cách nhau 5 phút, luân phiên Bật/Tắt

    Sau này nếu bạn có bảng telemetry thật:
    - Chỉ cần thay thân hàm này bằng query DB.
    """
    now = datetime.utcnow()
    events: List[dict] = []

    # mock tối đa 10 bản ghi
    n = min(limit, 10)

    for i in range(n):
        ts = now - timedelta(minutes=5 * i)
        value = 1 if i % 2 == 0 else 0  # 1 = Bật, 0 = Tắt
        events.append(
            {
                "device_id": device_id,
                "metric_type": "state",
                "value": value,
                "ts": ts.isoformat() + "Z",
            }
        )

    # sort từ cũ -> mới cho dễ đọc
    events.reverse()
    return events
