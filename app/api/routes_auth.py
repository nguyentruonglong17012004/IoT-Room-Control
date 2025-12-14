# app/api/routes_auth.py
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User, Attendance, Presence
from app.schemas import (
    UserCreate,
    UserOut,
    Token,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.security import (
    hash_password,
    authenticate_user,
    create_access_token,
    create_password_reset_token,
    send_password_reset_email,
    get_user_by_email,
    verify_password_reset_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# ================== HELPER: ATTENDANCE (CHECK-IN / CHECK-OUT) ==================

def _register_check_in(db: Session, user: User) -> None:
    """
    - Nếu hôm nay chưa có -> tạo mới check_in = now
    - Nếu đã có mà check_in đang None -> set check_in = now
    - Nếu đã có check_in rồi -> không làm gì
    """
    today = date.today()
    record = (
        db.query(Attendance)
        .filter(Attendance.user_id == user.id, Attendance.date == today)
        .first()
    )
    now = datetime.now()  # giữ logic của bạn: giờ local

    if not record:
        record = Attendance(
            user_id=user.id,
            date=today,
            check_in=now,
            check_out=None,
        )
        db.add(record)
    else:
        if record.check_in is None:
            record.check_in = now

    db.commit()


def _register_check_out(db: Session, user: User) -> None:
    """
    - Nếu hôm nay chưa có -> tạo mới check_out = now
    - Nếu đã có -> cập nhật check_out = now
    """
    today = date.today()
    record = (
        db.query(Attendance)
        .filter(Attendance.user_id == user.id, Attendance.date == today)
        .first()
    )
    now = datetime.now()  # giữ logic của bạn: giờ local

    if not record:
        record = Attendance(
            user_id=user.id,
            date=today,
            check_in=None,
            check_out=now,
        )
        db.add(record)
    else:
        record.check_out = now

    db.commit()


# ================== HELPER: PRESENCE (ONLINE/OFFLINE) ==================

def _set_online(db: Session, user: User, room_id: int | None = 1) -> None:
    now = datetime.utcnow()
    row = db.query(Presence).filter(Presence.user_id == user.id).first()
    if not row:
        row = Presence(user_id=user.id, room_id=room_id, is_online=True, last_seen=now)
        db.add(row)
    else:
        row.room_id = room_id
        row.is_online = True
        row.last_seen = now
    db.commit()


def _set_offline(db: Session, user: User) -> None:
    now = datetime.utcnow()
    row = db.query(Presence).filter(Presence.user_id == user.id).first()
    if row:
        row.is_online = False
        row.last_seen = now
        db.commit()


# ================== REGISTER ==================

@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được đăng ký",
        )

    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        date_of_birth=user_in.date_of_birth,
        position=user_in.position,
        start_date=date.today(),
        gender=user_in.gender,
        weight_kg=user_in.weight_kg,
        height_cm=user_in.height_cm,
        role="user",
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# ================== LOGIN ==================

@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
        )

    _register_check_in(db, user)

    # online (mặc định room_id=1 theo ROOMS mẫu)
    _set_online(db, user, room_id=1)

    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)


# ================== ME ==================

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ================== LOGOUT ==================

@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _register_check_out(db, current_user)
    _set_offline(db, current_user)
    return {"message": "Đã ghi nhận check-out."}


# ================== FORGOT / RESET PASSWORD ==================

@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, payload.email)

    if user:
        reset_token = create_password_reset_token(user.id)
        try:
            send_password_reset_email(user.email, reset_token)
        except Exception as e:
            print("Lỗi gửi email reset mật khẩu:", e)

    return {"message": "Nếu email tồn tại trong hệ thống, đường dẫn đặt lại mật khẩu đã được gửi."}


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    user_id = verify_password_reset_token(data.token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.",
        )

    user: User | None = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User không tồn tại.",
        )

    user.hashed_password = hash_password(data.new_password)
    db.commit()
    return {"message": "Mật khẩu đã được thay đổi thành công."}
