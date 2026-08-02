from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse, MessageResponse
from app.schemas.otp import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_services import register_user, login_user
from app.dependencies.db import get_db
from app.models.user import User
from app.models.otp import OTP
from app.utils.otp import generate_otp, get_otp_expiry
from app.utils.email import send_otp_email
from app.core.security import hash_password

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


@router.post(
    "/register",
    response_model=UserResponse
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):

    new_user = register_user(user, db)

    if new_user is None:
        raise HTTPException(
            status_code=400,
            detail="Email already exists"
        )

    return new_user


@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    return login_user(login_data, db)


@router.post(
    "/forgot-password",
    response_model=MessageResponse
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp = generate_otp()
    expiry = get_otp_expiry()
    
    otp_record = OTP(
        email=request.email,
        otp_code=otp,
        expiry_time=expiry,
        purpose="reset_password"
    )
    db.add(otp_record)
    db.commit()
    
    send_otp_email(request.email, otp)
    
    return {"message": "Verification code sent successfully"}


@router.post(
    "/reset-password",
    response_model=MessageResponse
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    otp_record = db.query(OTP).filter(
        OTP.email == request.email,
        OTP.otp_code == request.code,
        OTP.expiry_time > datetime.utcnow(),
        OTP.purpose == "reset_password"
    ).first()
    
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    user.password_hash = hash_password(request.new_password)
    db.query(OTP).filter(OTP.email == request.email).delete()
    db.commit()
    
    return {"message": "Password reset successful"}
