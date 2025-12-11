from datetime import datetime, date
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, EmailStr

from app.models import DeviceType


# ==== USER / AUTH ====


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

    # Hồ sơ nhân viên
    date_of_birth: Optional[date] = None  # Ngày sinh
    position: Optional[str] = None        # Chức vụ
    start_date: Optional[date] = None     # Ngày bắt đầu làm việc

    # Thông tin sức khỏe (giữ lại cho tương thích, có thể bỏ qua ở UI)
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None

    role: str = "user"


class UserCreate(BaseModel):
    """
    Payload dùng khi người dùng đăng ký tài khoản.

    Lưu ý:
    - start_date KHÔNG gửi từ client; backend sẽ tự set = ngày đăng ký.
    """

    email: EmailStr
    password: str
    full_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    position: Optional[str] = None

    # Giữ để tương thích, UI hiện tại không dùng
    gender: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None


class UserOut(UserBase):
    """
    Thông tin user trả về cho frontend (ví dụ /auth/me).
    """

    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ==== DEVICE ====


class DeviceCreate(BaseModel):
    """
    Dùng khi tạo thiết bị mới và gán cho phòng.
    """

    device_id: str
    name: Optional[str] = None
    room_id: Optional[int] = None
    device_type: DeviceType
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None


class DeviceOut(BaseModel):
    """
    Thông tin thiết bị trả ra cho frontend.
    """

    id: int
    device_id: str
    name: Optional[str]
    device_type: Optional[DeviceType] = None
    room_id: Optional[int] = None
    is_on: Optional[bool] = False
    value: Optional[float] = None
    api_key: str  # để bạn cấu hình cho thiết bị vật lý
    pos_x: Optional[float] = None
    pos_y: Optional[float] = None

    class Config:
        from_attributes = True


class DeviceCommandIn(BaseModel):
    """
    Lệnh điều khiển gửi từ web xuống thiết bị qua backend.
    Ví dụ:
    - command_type = "toggle", payload = {}
    - command_type = "set_temperature", payload = {"value": 24}
    """

    command_type: str
    payload: Optional[Dict[str, Any]] = None


# ==== TELEMETRY ====


class TelemetryIn(BaseModel):
    """
    Payload thiết bị gửi lên khi báo dữ liệu/ trạng thái.
    """

    device_id: str = Field(..., min_length=1)
    api_key: str = Field(..., min_length=1)
    metric_type: str = Field(
        ...,
        description=(
            "Loại metric, ví dụ: 'people_count', "
            "'room_temperature', 'device_state', ..."
        ),
    )
    value: Optional[float] = Field(
        default=None,
        description=(
            "Giá trị chính, tuỳ metric_type: "
            "nhiệt độ, số người, trạng thái thiết bị (0/1), v.v."
        ),
    )
    payload: Optional[Dict[str, Any]] = None


class TelemetryOut(BaseModel):
    ts: datetime
    metric_type: Optional[str]
    value: Optional[float]
    payload: Optional[dict]

    class Config:
        from_attributes = True


# ==== ROOMS / DASHBOARD ====


class RoomStatus(BaseModel):
    room_id: int
    people_count: int
    temperature: Optional[float] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class Room(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: Optional[RoomStatus] = None
    devices: List[DeviceOut] = []

    class Config:
        from_attributes = True


class RoomStatusResponse(BaseModel):
    """
    Response cho API kiểu: GET /rooms/{room_id}/status
    """

    room: Room


# ==== ATTENDANCE (check-in / check-out) ====


class AttendanceOut(BaseModel):
    """
    Một bản ghi chấm công cho 1 ngày.
    """

    date: date
    check_in: Optional[datetime] = None
    check_out: Optional[datetime] = None

    class Config:
        from_attributes = True


class AttendanceHistory(BaseModel):
    """
    Trả về danh sách các ngày chấm công của user.
    """

    items: List[AttendanceOut]
