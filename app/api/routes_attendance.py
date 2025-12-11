# app/api/routes_attendance.py
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Attendance, User
from app.schemas import AttendanceOut, AttendanceHistory

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.get("/me/today", response_model=AttendanceOut)
def get_my_attendance_today(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy bản ghi chấm công hôm nay của user hiện tại.
    Nếu chưa có thì trả về date = hôm nay, check_in/check_out = None.
    """
    today = date.today()
    record = (
        db.query(Attendance)
        .filter(Attendance.user_id == current_user.id, Attendance.date == today)
        .first()
    )

    if not record:
        return AttendanceOut(date=today, check_in=None, check_out=None)

    return record


@router.get("/me", response_model=AttendanceHistory)
def get_my_attendance_history(
    days: int = 30,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lịch sử chấm công N ngày gần nhất (mặc định 30 ngày).
    Dùng sau này cho phần "Xem lịch sử chi tiết".
    """
    since = date.today() - timedelta(days=days - 1)

    items = (
        db.query(Attendance)
        .filter(
            Attendance.user_id == current_user.id,
            Attendance.date >= since,
        )
        .order_by(Attendance.date.desc())
        .all()
    )

    return AttendanceHistory(items=items)
