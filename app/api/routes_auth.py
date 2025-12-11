# app/api/routes_auth.py
from datetime import datetime, date

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import User, Attendance
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
    Ghi nhận thời gian check-in cho user:
    - Mỗi ngày một dòng trên bảng Attendance.
    - Nếu hôm nay chưa có bản ghi -> tạo mới với check_in = now.
    - Nếu đã có mà check_in vẫn None -> cập nhật check_in = now.
    """
    today = date.today()
    record = (
        db.query(Attendance)
        .filter(Attendance.user_id == user.id, Attendance.date == today)
        .first()
    )
    # DÙNG GIỜ LOCAL THAY VÌ UTC
    now = datetime.now()

    if not record:
        record = Attendance(
            user_id=user.id,
            date=today,
            check_in=now,
            check_out=None,
        )
        db.add(record)
    else:
            record.check_in = now

    db.commit()


def _register_check_out(db: Session, user: User) -> None:
    """
    Ghi nhận thời gian check-out cho user:
    - Nếu hôm nay chưa có bản ghi -> tạo mới với check_out = now.
    - Nếu đã có -> cập nhật check_out = now.
    """
    today = date.today()
    record = (
        db.query(Attendance)
        .filter(Attendance.user_id == user.id, Attendance.date == today)
        .first()
    )
    # DÙNG GIỜ LOCAL THAY VÌ UTC
    now = datetime.now()

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

# ================== REGISTER ==================


@router.post("/register", response_model=UserOut)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Đăng ký tài khoản mới.

    Frontend gửi JSON:
    {
      "email": "...",
      "password": "...",
      "full_name": "...",
      "date_of_birth": "YYYY-MM-DD",
      "position": "Chức vụ"
    }

    start_date sẽ được tự động set = ngày đăng ký (date.today()).
    """
    # Kiểm tra trùng email
    existing = get_user_by_email(db, user_in.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được đăng ký",
        )

    # Tạo user mới, role mặc định = "user"
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        full_name=user_in.full_name,
        date_of_birth=user_in.date_of_birth,
        position=user_in.position,
        start_date=date.today(),
        # các field cũ giữ lại cho tương thích
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
    """
    Đăng nhập bằng email + password.
    - Frontend gửi form: username=email, password=...
    """
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
        )

    # Ghi nhận check-in cho ngày hiện tại
    _register_check_in(db, user)

    access_token = create_access_token({"sub": str(user.id)})
    return Token(access_token=access_token)


# ================== ME (THÔNG TIN TÀI KHOẢN) ==================


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    """
    Trả về thông tin tài khoản hiện tại (dùng cho tab 'Tài khoản').
    """
    return current_user


# ================== LOGOUT (CHECK-OUT) ==================


@router.post("/logout")
def logout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Đăng xuất:
    - Ghi nhận thời gian check-out cho ngày hiện tại.
    - Frontend sau đó tự xoá token ở localStorage.
    """
    _register_check_out(db, current_user)
    return {"message": "Đã ghi nhận check-out."}


# ================== FORGOT / RESET PASSWORD ==================


@router.post("/forgot-password")
def forgot_password(
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Nhận email, nếu tồn tại thì gửi mail reset (nếu cấu hình SMTP).
    Không tiết lộ email có tồn tại hay không.
    """
    user = get_user_by_email(db, payload.email)

    if user:
        reset_token = create_password_reset_token(user.id)
        try:
            send_password_reset_email(user.email, reset_token)
        except Exception as e:
            # Có thể log ra thay vì print
            print("Lỗi gửi email reset mật khẩu:", e)

    return {
        "message": "Nếu email tồn tại trong hệ thống, đường dẫn đặt lại mật khẩu đã được gửi."
    }


@router.post("/reset-password")
def reset_password(
    data: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """
    Đặt lại mật khẩu bằng token.
    """
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
