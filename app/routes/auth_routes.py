from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse, MessageResponse
from app.schemas.otp import ForgotPasswordRequest, ResetPasswordRequest, OTPVerify, OTPResend
from app.services.auth_services import register_user, login_user
from app.dependencies.db import get_db
from app.models.user import User
from app.models.otp import OTP, UserOTP
from app.utils.otp import generate_otp, get_otp_expiry
from app.utils.email import send_otp_email
from app.core.security import hash_password, verify_password

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

    # Invalidate previous verification OTPs for this email if any
    db.query(UserOTP).filter(
        UserOTP.email == user.email,
        UserOTP.is_used == False,
        UserOTP.purpose == "email_verification"
    ).update({UserOTP.is_used: True})

    # Generate registration OTP valid for 10 minutes
    otp = generate_otp()
    expiry = get_otp_expiry(minutes=10)
    hashed = hash_password(otp)

    otp_record = UserOTP(
        email=user.email,
        hashed_otp=hashed,
        expiry_time=expiry,
        purpose="email_verification"
    )
    db.add(otp_record)
    db.commit()

    send_otp_email(user.email, otp)

    return new_user


@router.post(
    "/verify-otp",
    response_model=MessageResponse
)
def verify_otp(
    request: OTPVerify,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email is already verified"}

    otp_record = db.query(UserOTP).filter(
        UserOTP.email == request.email,
        UserOTP.is_used == False,
        UserOTP.purpose == "email_verification",
        UserOTP.expiry_time > datetime.utcnow()
    ).order_by(UserOTP.created_at.desc()).first()

    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    if otp_record.attempts >= 5:
        raise HTTPException(
            status_code=400,
            detail="Too many failed attempts. Please request a new OTP."
        )

    if not verify_password(request.otp, otp_record.hashed_otp):
        otp_record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code")

    otp_record.is_used = True
    user.is_verified = True
    db.commit()

    return {"message": "Email verified successfully"}


@router.post(
    "/resend-otp",
    response_model=MessageResponse
)
def resend_otp(
    request: OTPResend,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"message": "Email is already verified"}

    # Enforce 60-second cooldown on resending
    last_otp = db.query(UserOTP).filter(
        UserOTP.email == request.email,
        UserOTP.purpose == "email_verification"
    ).order_by(UserOTP.created_at.desc()).first()

    if last_otp:
        elapsed = datetime.utcnow() - last_otp.created_at
        if elapsed.total_seconds() < 60:
            remaining = int(60 - elapsed.total_seconds())
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining} seconds before requesting a new code."
            )

    # Invalidate old verification OTPs
    db.query(UserOTP).filter(
        UserOTP.email == request.email,
        UserOTP.is_used == False,
        UserOTP.purpose == "email_verification"
    ).update({UserOTP.is_used: True})

    otp = generate_otp()
    expiry = get_otp_expiry(minutes=10)
    hashed = hash_password(otp)

    new_otp = UserOTP(
        email=request.email,
        hashed_otp=hashed,
        expiry_time=expiry,
        purpose="email_verification"
    )
    db.add(new_otp)
    db.commit()

    send_otp_email(request.email, otp)

    return {"message": "Verification code sent successfully"}


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
