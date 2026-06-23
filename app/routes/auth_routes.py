from fastapi import Depends, APIRouter, BackgroundTasks, status
from sqlalchemy.orm import Session
from app.dependencies.db import get_db
from app.schemas.otp import OTPVerify,OTPResend
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, MessageResponse
from app.services import auth_services

router=APIRouter(
    prefix="/auth",
    tags=["Authentication"]

)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user:UserCreate,db:Session=Depends(get_db)):
    new_user=auth_services.create_user(db,user)
    return new_user

@router.post("/login", response_model=TokenResponse)
def login(user:UserLogin,db:Session=Depends(get_db)):
    return auth_services.login_user(db,user)

@router.post("/send-otp", response_model=MessageResponse)
def send_otp(data:OTPResend, background_tasks:BackgroundTasks, db:Session=Depends(get_db)):
    return auth_services.send_otp(db, data.email, background_tasks)

@router.post("/verify-otp", response_model=MessageResponse)
def verify_otp(data:OTPVerify,db:Session=Depends(get_db)):
    return auth_services.verify_otp(db,data.email,data.otp)

@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(data:OTPResend, background_tasks:BackgroundTasks, db:Session=Depends(get_db)):
    return auth_services.resend_otp(db, data.email, background_tasks)