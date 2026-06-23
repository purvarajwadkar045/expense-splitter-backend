import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

EMAIL=os.getenv("EMAIL")
EMAIL_PASSWORD=os.getenv("EMAIL_PASSWORD")

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
        print("Email sending failed")    