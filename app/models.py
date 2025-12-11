from datetime import datetime
import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Float,
    Boolean,
    Enum,
    Date,          # thêm Date
)
from sqlalchemy.types import JSON
from sqlalchemy.orm import relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=True)

    # Thông tin hồ sơ nhân viên
    date_of_birth = Column(Date, nullable=True)  # Ngày sinh
    position = Column(String, nullable=True)     # Chức vụ trong công ty
    start_date = Column(Date, nullable=True)     # Ngày bắt đầu làm việc

    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Thông tin sức khỏe (giữ lại, không ảnh hưởng hệ mới)
    gender = Column(String, nullable=True)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)

    # Phân quyền: "user" (mặc định) hoặc "admin"
    role = Column(String, nullable=False, default="user")

    # Quan hệ 1-n với Device
    devices = relationship("Device", back_populates="owner")

    # Quan hệ 1-n với Attendance (lịch sử check-in / check-out)
    attendance_records = relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class DeviceType(str, enum.Enum):
    LIGHT = "light"
    FAN = "fan"
    AC = "ac"


class Room(Base):
    """
    Phòng/vị trí vật lý (phòng họp, lớp học, phòng lab, ...)
    """

    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    description = Column(String, nullable=True)

    devices = relationship(
        "Device",
        back_populates="room",
        cascade="all, delete-orphan",
    )
    status = relationship(
        "RoomStatus",
        back_populates="room",
        uselist=False,
        cascade="all, delete-orphan",
    )


class Device(Base):
    """
    Thiết bị IoT: đèn / quạt / điều hòa ...
    """

    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)

    # Thuộc phòng nào (có thể để null nếu chưa gán phòng)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)

    # Loại thiết bị: đèn / quạt / điều hoà
    device_type = Column(Enum(DeviceType), nullable=True)

    # Vị trí trên sơ đồ phòng (tuỳ chọn, dùng cho UI)
    pos_x = Column(Float, nullable=True)
    pos_y = Column(Float, nullable=True)

    # Trạng thái hiện tại / setpoint
    is_on = Column(Boolean, default=False)
    value = Column(Float, nullable=True)  # nhiệt độ AC, tốc độ quạt, v.v.

    owner = relationship("User", back_populates="devices")
    telemetry = relationship("Telemetry", back_populates="device")
    room = relationship("Room", back_populates="devices")


class Telemetry(Base):
    """
    Dữ liệu đo được từ thiết bị:
    - people_count
    - room_temperature
    - device_state
    - hoặc bất cứ metric nào khác
    """

    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    metric_type = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    payload = Column(JSON, nullable=True)

    device = relationship("Device", back_populates="telemetry")


class RoomStatus(Base):
    """
    Trạng thái tổng quát của phòng (dùng cho dashboard):
    - số người hiện tại
    - nhiệt độ phòng
    """

    __tablename__ = "room_status"

    room_id = Column(Integer, ForeignKey("rooms.id"), primary_key=True)
    people_count = Column(Integer, default=0)
    temperature = Column(Float, nullable=True)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    room = relationship("Room", back_populates="status")


class Attendance(Base):
    """
    Lịch sử chấm công:
    - Mỗi dòng = 1 ngày làm việc của một user
    - check_in: thời điểm đầu tiên đăng nhập trong ngày
    - check_out: thời điểm đăng xuất cuối cùng trong ngày
    """

    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="attendance_records")
