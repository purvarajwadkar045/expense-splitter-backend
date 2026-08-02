import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger("app")

EMAIL = settings.EMAIL
EMAIL_PASSWORD = settings.EMAIL_PASSWORD

def send_otp_email(to_email:str,otp:str):
    subject="your OTP code"
    body=f"""
    your OTP is:{otp}
    It will expire in 5 minutes"""

    msg=MIMEMultipart()
    msg["From"]=EMAIL
    msg["To"]=to_email
    msg["Subject"]=subject

    msg.attach(MIMEText(body,"plain"))
    try:
        server=smtplib.SMTP("smtp.gmail.com",587)
        server.starttls()
        server.login(EMAIL,EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        logger.error("Email sending failed", exc_info=True)