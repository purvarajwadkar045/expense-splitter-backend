from pydantic import BaseModel,EmailStr


class OTPVerify(BaseModel):
    email:EmailStr
    otp:str

class OTPResend(BaseModel):
    email:EmailStr    

class ForgotPasswordRequest(BaseModel):
    email:EmailStr
        