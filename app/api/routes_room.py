# app/api/routes_room.py

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User, Attendance

router = APIRouter(prefix="/rooms", tags=["rooms"])

# =========================
# DỮ LIỆU MẪU 4 PHÒNG
# MỖI PHÒNG: 2 ĐÈN TRẦN, 1 QUẠT
# =========================


ROOMS = [
    {
        "id": 1,
        "name": "Phòng Kinh Doanh",
        "description": "Sales Office",
        "status": {
            "people_count": 5,  # sẽ bị ghi đè bởi logic attendance
            "temperature": 24.0,
        },
        "devices": [
            # 2 đèn trần
            {
                "id": 1,
                "device_id": "KD_LIGHT_1",
                "name": "Đèn trần 1",
                "device_type": "LIGHT",
                "pos_x": 1,
                "pos_y": 1,
                "is_on": True,
                "value": 1,
            },
            {
                "id": 2,
                "device_id": "KD_LIGHT_2",
                "name": "Đèn trần 2",
                "device_type": "LIGHT",
                "pos_x": 2,
                "pos_y": 1,
                "is_on": True,
                "value": 1,
            },
            # 1 quạt
            {
                "id": 3,
                "device_id": "KD_FAN_1",
                "name": "Quạt trần",
                "device_type": "FAN",
                "pos_x": 1,
                "pos_y": 2,
                "is_on": False,
                "value": 1,  # cấp gió
            },
        ],
    },
    {
        "id": 2,
        "name": "Phòng Marketing",
        "description": "Marketing Office",
        "status": {
            "people_count": 3,
            "temperature": 25.0,
        },
        "devices": [
            {
                "id": 4,
                "device_id": "MKT_LIGHT_1",
                "name": "Đèn trần 1",
                "device_type": "LIGHT",
                "pos_x": 1,
                "pos_y": 1,
                "is_on": True,
                "value": 1,
            },
            {
                "id": 5,
                "device_id": "MKT_LIGHT_2",
                "name": "Đèn trần 2",
                "device_type": "LIGHT",
                "pos_x": 2,
                "pos_y": 1,
                "is_on": False,
                "value": 0,
            },
            {
                "id": 6,
                "device_id": "MKT_FAN_1",
                "name": "Quạt treo tường",
                "device_type": "FAN",
                "pos_x": 1,
                "pos_y": 2,
                "is_on": True,
                "value": 2,
            },
        ],
    },
    {
        "id": 3,
        "name": "Phòng Kế Toán",
        "description": "Accounting Office",
        "status": {
            "people_count": 2,
            "temperature": 23.0,
        },
        "devices": [
            {
                "id": 7,
                "device_id": "KT_LIGHT_1",
                "name": "Đèn trần 1",
                "device_type": "LIGHT",
                "pos_x": 1,
                "pos_y": 1,
                "is_on": True,
                "value": 1,
            },
            {
                "id": 8,
                "device_id": "KT_LIGHT_2",
                "name": "Đèn trần 2",
                "device_type": "LIGHT",
                "pos_x": 2,
                "pos_y": 1,
                "is_on": False,
                "value": 0,
            },
            {
                "id": 9,
                "device_id": "KT_FAN_1",
                "name": "Quạt đứng",
                "device_type": "FAN",
                "pos_x": 1,
                "pos_y": 2,
                "is_on": True,
                "value": 1,
            },
        ],
    },
    {
        "id": 4,
        "name": "Phòng Nhân Sự",
        "description": "HR Office",
        "status": {
            "people_count": 1,
            "temperature": 24.0,
        },
        "devices": [
            {
                "id": 10,
                "device_id": "HR_LIGHT_1",
                "name": "Đèn trần 1",
                "device_type": "LIGHT",
                "pos_x": 1,
                "pos_y": 1,
                "is_on": True,
                "value": 1,
            },
            {
                "id": 11,
                "device_id": "HR_LIGHT_2",
                "name": "Đèn trần 2",
                "device_type": "LIGHT",
                "pos_x": 2,
                "pos_y": 1,
                "is_on": False,
                "value": 0,
            },
            {
                "id": 12,
                "device_id": "HR_FAN_1",
                "name": "Quạt trần",
                "device_type": "FAN",
                "pos_x": 1,
                "pos_y": 2,
                "is_on": False,
                "value": 1,
            },
        ],
    },
]


def _find_room(room_id: int):
    for r in ROOMS:
        if r["id"] == room_id:
            return r
    return None


def map_position_to_room_id(position: str | None) -> int | None:
    """
    Map chức vụ (position) sang id phòng.
    Bạn có thể chỉnh lại logic này tùy cách đặt tên chức vụ.
    """
    if not position:
        return None
    p = position.strip().lower()

    if "kinh doanh" in p:
        return 1  # Phòng Kinh Doanh
    if "marketing" in p:
        return 2  # Phòng Marketing
    if "kế toán" in p or "ke toan" in p:
        return 3  # Phòng Kế Toán
    if "nhân sự" in p or "nhan su" in p:
        return 4  # Phòng Nhân Sự

    return None


@router.get("", summary="Danh sách phòng")
def list_rooms(current_user: User = Depends(get_current_user)):
    """
    Trả về danh sách các phòng cho dropdown.
    """
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "description": r.get("description"),
        }
        for r in ROOMS
    ]


@router.get("/{room_id}/status", summary="Trạng thái chi tiết của 1 phòng")
def get_room_status(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Frontend đang gọi GET /rooms/{room_id}/status
    và mong đợi response dạng { "room": { ... } }.

    Tại đây ta cập nhật people_count dựa trên Attendance:
    - Attendance.date = hôm nay
    - check_in != None
    - check_out == None
    - user.position map vào đúng room_id
    """
    room = _find_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    today = date.today()

    # lấy toàn bộ bản ghi hôm nay đang "có mặt"
    rows = (
        db.query(Attendance, User)
        .join(User, Attendance.user_id == User.id)
        .filter(
            Attendance.date == today,
            Attendance.check_in.isnot(None),
            Attendance.check_out.is_(None),
        )
        .all()
    )

    people_count = 0
    for att, user in rows:
        r_id = map_position_to_room_id(user.position)
        if r_id == room_id:
            people_count += 1

    # ghi đè people_count vào status của phòng
    room["status"]["people_count"] = people_count

    return {"room": room}
