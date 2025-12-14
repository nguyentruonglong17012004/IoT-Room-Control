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
    Date,
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
    date_of_birth = Column(Date, nullable=True)
    position = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)

    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Thông tin sức khỏe (giữ lại, không ảnh hưởng hệ mới)
    gender = Column(String, nullable=True)
    weight_kg = Column(Float, nullable=True)
    height_cm = Column(Float, nullable=True)

    # Phân quyền: "user" (mặc định) hoặc "admin"
    role = Column(String, nullable=False, default="user")

    devices = relationship("Device", back_populates="owner")

    attendance_records = relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Quan hệ 1-1 với Presence (trạng thái online)
    presence = relationship(
        "Presence",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )


class DeviceType(str, enum.Enum):
    LIGHT = "light"
    FAN = "fan"
    AC = "ac"


class Room(Base):
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
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    api_key = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Integer, default=1)

    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    device_type = Column(Enum(DeviceType), nullable=True)

    pos_x = Column(Float, nullable=True)
    pos_y = Column(Float, nullable=True)

    is_on = Column(Boolean, default=False)
    value = Column(Float, nullable=True)

    owner = relationship("User", back_populates="devices")
    telemetry = relationship("Telemetry", back_populates="device")
    room = relationship("Room", back_populates="devices")


class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String, ForeignKey("devices.device_id"), index=True)
    ts = Column(DateTime, default=datetime.utcnow, index=True)
    metric_type = Column(String, nullable=False)
    value = Column(Float, nullable=True)
    payload = Column(JSON, nullable=True)

    device = relationship("Device", back_populates="telemetry")


class RoomStatus(Base):
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
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    date = Column(Date, nullable=False, index=True)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="attendance_records")


class Presence(Base):
    """
    Trạng thái online của user để tính people_count trên dashboard.
    Lưu ý: room_id ở đây là số phòng (1..4) theo ROOMS mẫu, không ràng buộc FK,
    để bạn không cần phải seed bảng rooms trong DB.
    """
    __tablename__ = "presence"

    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True)
    room_id = Column(Integer, nullable=True)  # (1..4) theo ROOMS mẫu
    is_online = Column(Boolean, default=True)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="presence")
