from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException,status
from app.models.user import User
from app.core.security import hash_password,verify_password,create_access_token
from app.schemas.user import UserCreate,UserLogin
from app.utils.email import send_otp_email
from app.models.otp import OTP
from app.utils.otp import generate_otp,get_otp_expiry

COOLDOWN_SECONDS=60

def create_user(db:Session,user:UserCreate):
    existing_user=db.query(User).filter(User.email==user.email).first()
    if existing_user :
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail= "User with this email exists"       
        )
    hashed_pw=hash_password(user.password)
    new_user=User(
        email=user.email,
        password=hashed_pw
    )
    try:
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return new_user
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong"
        )

def login_user(db:Session,user:UserLogin):
    existing_user=db.query(User).filter(User.email==user.email).first()
    if not existing_user :
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    if not verify_password(user.password,existing_user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    access_token=create_access_token({
        "user_id":existing_user.id,
        "email":existing_user.email
    })
    return {
        "access_token":access_token,
        "token_type":"bearer"
    }

def send_otp(db: Session, email: str, background_tasks):
    user=db.query(User).filter(User.email==email).first()
    if not user:
        raise HTTPException(status_code=404,detail="User not found")
    
    otp=generate_otp()
    expiry=get_otp_expiry()
    otp_entry=OTP(
        email=email,
        otp_code=otp,
        expiry_time=expiry
    )

    db.add(otp_entry)
    db.commit()

    background_tasks.add_task(send_otp_email, email, otp)
    return {"message":"OTP sent to email"}

def verify_otp(db,email:str,otp:str):
    otp_record=(
        db.query(OTP).filter(OTP.email==email).order_by(OTP.id.desc()).first()
    )
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OTP not found"
        )
    
    if datetime.now(timezone.utc).replace(tzinfo=None) > otp_record.expiry_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired"
        )
    user=db.query(User).filter(User.email==email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    user.is_verified=True
    db.delete(otp_record)
    db.commit()
    return {"message": "User verified successfully"}

def resend_otp(db: Session, email: str, background_tasks):
    user=db.query(User).filter(User.email==email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    latest_otp=(
        db.query(OTP).filter(OTP.email==email).order_by(OTP.id.desc()).first()
    )
    if latest_otp:
        time_diff=datetime.now(timezone.utc).replace(tzinfo=None)-latest_otp.created_at
        if time_diff<timedelta(seconds=COOLDOWN_SECONDS):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting OTP again"
            )
        
        db.delete(latest_otp)

    new_otp=generate_otp()
    expiry=get_otp_expiry()
    otp_entry=OTP(
        email=email,
        otp_code=new_otp,
        expiry_time=expiry,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    db.add(otp_entry)
    db.commit()
    background_tasks.add_task(send_otp_email, email, new_otp)
    return {"message": "OTP resent successfully"}

def forgot_password(db: Session, email: str, background_tasks):
    # Do NOT reveal if user exists
    user = db.query(User).filter(User.email == email).first()

    otp_code = generate_otp()
    expiry = get_otp_expiry()

    existing_otp = (
        db.query(OTP)
        .filter(OTP.email == email, OTP.purpose == "reset_password")
        .first()
    )

    if existing_otp:
        # Update existing OTP
        existing_otp.otp_code = otp_code
        existing_otp.expiry_time = expiry
        existing_otp.is_verified = False
        existing_otp.created_at = datetime.now(timezone.utc).replace(tzinfo=None)
    else:
        # Create new OTP
        otp_entry = OTP(
            email=email,
            otp_code=otp_code,
            expiry_time=expiry,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            purpose="reset_password",
            is_verified=False
        )
        db.add(otp_entry)

    db.commit()

    # Send email only if user exists
    if user:
        background_tasks.add_task(send_otp_email, email, otp_code)

    return {"message": "If the email exists, OTP has been sent"}