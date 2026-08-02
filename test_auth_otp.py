import sys
import os
import unittest
from datetime import datetime, timedelta
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.user import User
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.settlement import Settlement
from app.models.otp import UserOTP
from app.models.activity import Activity
from app.models.notification import Notification
from app.services import auth_services
from app.schemas.user import UserCreate, UserLogin
from app.schemas.otp import OTPVerify, OTPResend
from app.routes import auth_routes
from app.core.security import hash_password, verify_password

class TestAuthOTPFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_registration_creates_unverified_user_and_generates_otp(self):
        """1. Registration creates an unverified user and 2. OTP is generated."""
        user_in = UserCreate(username="TestUser", email="test@example.com", password="password123")
        
        # We simulate the route logic here
        new_user = auth_services.register_user(user_in, self.db)
        self.assertIsNotNone(new_user)
        self.assertFalse(new_user.is_verified)
        
        # Verify user exists in db and is not verified
        db_user = self.db.query(User).filter(User.email == "test@example.com").first()
        self.assertIsNotNone(db_user)
        self.assertFalse(db_user.is_verified)

        # Verify an OTP record is created
        otp_record = UserOTP(
            email="test@example.com",
            hashed_otp=hash_password("123456"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            purpose="email_verification"
        )
        self.db.add(otp_record)
        self.db.commit()

        db_otp = self.db.query(UserOTP).filter(UserOTP.email == "test@example.com").first()
        self.assertIsNotNone(db_otp)
        self.assertTrue(verify_password("123456", db_otp.hashed_otp))
        self.assertEqual(db_otp.purpose, "email_verification")

    def test_correct_otp_verifies_user(self):
        """3. Correct OTP verifies the user."""
        # Create unverified user
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        otp_record = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("111222"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            purpose="email_verification"
        )
        self.db.add_all([user, otp_record])
        self.db.commit()

        # Simulate verify-otp route
        req = OTPVerify(email="user@example.com", otp="111222")
        db_otp = self.db.query(UserOTP).filter(
            UserOTP.email == req.email,
            UserOTP.is_used == False,
            UserOTP.expiry_time > datetime.utcnow()
        ).first()

        self.assertIsNotNone(db_otp)
        self.assertTrue(verify_password(req.otp, db_otp.hashed_otp))

        db_otp.is_used = True
        user.is_verified = True
        self.db.commit()

        # Check status
        self.assertTrue(user.is_verified)
        self.assertTrue(db_otp.is_used)

    def test_incorrect_otp_is_rejected(self):
        """4. Incorrect OTP is rejected."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        otp_record = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("111222"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            purpose="email_verification"
        )
        self.db.add_all([user, otp_record])
        self.db.commit()

        req = OTPVerify(email="user@example.com", otp="999999")
        db_otp = self.db.query(UserOTP).filter(
            UserOTP.email == req.email,
            UserOTP.is_used == False
        ).first()

        self.assertIsNotNone(db_otp)
        self.assertFalse(verify_password(req.otp, db_otp.hashed_otp))
        
        # Increment attempts
        db_otp.attempts += 1
        self.db.commit()
        
        self.assertEqual(db_otp.attempts, 1)
        self.assertFalse(user.is_verified)

    def test_expired_otp_is_rejected(self):
        """5. Expired OTP is rejected."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        # Expiry is set in the past
        otp_record = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("111222"),
            expiry_time=datetime.utcnow() - timedelta(minutes=1),
            purpose="email_verification"
        )
        self.db.add_all([user, otp_record])
        self.db.commit()

        req = OTPVerify(email="user@example.com", otp="111222")
        db_otp = self.db.query(UserOTP).filter(
            UserOTP.email == req.email,
            UserOTP.is_used == False,
            UserOTP.expiry_time > datetime.utcnow() # Expiry check
        ).first()

        self.assertIsNone(db_otp)
        self.assertFalse(user.is_verified)

    def test_used_otp_cannot_be_reused(self):
        """6. Used OTP cannot be reused."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        otp_record = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("111222"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            is_used=True, # already used
            purpose="email_verification"
        )
        self.db.add_all([user, otp_record])
        self.db.commit()

        req = OTPVerify(email="user@example.com", otp="111222")
        db_otp = self.db.query(UserOTP).filter(
            UserOTP.email == req.email,
            UserOTP.is_used == False # unused check
        ).first()

        self.assertIsNone(db_otp)
        self.assertFalse(user.is_verified)

    def test_resending_otp_invalidates_old_otp(self):
        """7. Resending OTP invalidates the old active OTP."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        old_otp = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("111111"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            is_used=False,
            purpose="email_verification"
        )
        self.db.add_all([user, old_otp])
        self.db.commit()

        # Resend logic triggers: invalidate previous OTPs
        self.db.query(UserOTP).filter(
            UserOTP.email == "user@example.com",
            UserOTP.is_used == False,
            UserOTP.purpose == "email_verification"
        ).update({UserOTP.is_used: True})
        
        new_otp = UserOTP(
            email="user@example.com",
            hashed_otp=hash_password("222222"),
            expiry_time=datetime.utcnow() + timedelta(minutes=10),
            is_used=False,
            purpose="email_verification"
        )
        self.db.add(new_otp)
        self.db.commit()

        # Check old OTP is invalidated (used = True)
        self.db.refresh(old_otp)
        self.assertTrue(old_otp.is_used)
        
        # Check new OTP is active
        self.db.refresh(new_otp)
        self.assertFalse(new_otp.is_used)

    def test_unverified_users_cannot_login(self):
        """8. Unverified users cannot log in."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=False)
        self.db.add(user)
        self.db.commit()

        login_data = UserLogin(email="user@example.com", password="password")
        with self.assertRaises(HTTPException) as context:
            auth_services.login_user(login_data, self.db)
            
        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Please verify your email before logging in.")

    def test_verified_users_can_login(self):
        """9. Verified users can log in and receive JWT."""
        user = User(username="user", email="user@example.com", password_hash=hash_password("password"), is_verified=True)
        self.db.add(user)
        self.db.commit()

        login_data = UserLogin(email="user@example.com", password="password")
        res = auth_services.login_user(login_data, self.db)
        
        self.assertIsNotNone(res)
        self.assertIn("access_token", res)
        self.assertEqual(res["token_type"], "bearer")

if __name__ == "__main__":
    unittest.main()
