import sys
import os
from datetime import datetime, timedelta
import unittest
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
from app.models.otp import OTP
from app.services import expense_service

class TestExpenseFiltering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed test data
        self.user1 = User(id=1, username="alice", email="alice@example.com", password_hash="hash")
        self.user2 = User(id=2, username="bob", email="bob@example.com", password_hash="hash")
        self.user3 = User(id=3, username="charlie", email="charlie@example.com", password_hash="hash")
        
        self.group = Group(id=1, name="Goa Trip", created_by=1)
        
        self.member1 = GroupMember(id=1, group_id=1, user_id=1)
        self.member2 = GroupMember(id=2, group_id=1, user_id=2)
        
        # We explicitly set created_at for testing dates
        self.exp1 = Expense(
            id=1,
            title="Dinner",
            amount=100.0,
            description="First expense",
            group_id=1,
            paid_by=1,
            created_at=datetime(2026, 7, 10, 12, 0)
        )
        self.exp2 = Expense(
            id=2,
            title="Taxi",
            amount=20.0,
            description="Second expense",
            group_id=1,
            paid_by=2,
            created_at=datetime(2026, 7, 11, 12, 0)
        )
        self.exp3 = Expense(
            id=3,
            title="Groceries",
            amount=150.0,
            description="Third expense",
            group_id=1,
            paid_by=1,
            created_at=datetime(2026, 7, 12, 12, 0)
        )
        
        self.db.add_all([
            self.user1, self.user2, self.user3,
            self.group,
            self.member1, self.member2,
            self.exp1, self.exp2, self.exp3
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        # Clear tables
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_no_filters(self):
        """Should return all group expenses, ordered by newest first (created_at desc)"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db
        )
        self.assertEqual(len(res), 3)
        self.assertEqual(res[0]["id"], 3)  # exp3 is newest
        self.assertEqual(res[1]["id"], 2)
        self.assertEqual(res[2]["id"], 1)

    def test_filter_by_user_id(self):
        """Should filter by paid_by user_id"""
        # Alice (user_id=1) paid for exp1 and exp3
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            user_id=1
        )
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["id"], 3)
        self.assertEqual(res[1]["id"], 1)

        # Bob (user_id=2) paid for exp2
        res2 = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            user_id=2
        )
        self.assertEqual(len(res2), 1)
        self.assertEqual(res2[0]["id"], 2)

    def test_filter_by_start_date(self):
        """Should return expenses created on or after start_date"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            start_date=datetime(2026, 7, 11, 0, 0)
        )
        # Should return exp2 (July 11) and exp3 (July 12)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["id"], 3)
        self.assertEqual(res[1]["id"], 2)

    def test_filter_by_end_date(self):
        """Should return expenses created on or before end_date"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            end_date=datetime(2026, 7, 11, 23, 59)
        )
        # Should return exp2 (July 11) and exp1 (July 10)
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]["id"], 2)
        self.assertEqual(res[1]["id"], 1)

    def test_filter_combined(self):
        """Should apply multiple filters together"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            user_id=1,
            start_date=datetime(2026, 7, 11, 0, 0),
            end_date=datetime(2026, 7, 12, 23, 59)
        )
        # Should return only exp3 (paid by 1, between July 11 and 12)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 3)

    def test_non_member_access(self):
        """Should raise 403 Forbidden for user3 who is not a member of group 1"""
        with self.assertRaises(HTTPException) as context:
            expense_service.get_group_expenses(
                group_id=1,
                current_user=self.user3,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 403)

    def test_non_existent_group(self):
        """Should raise 404 Not Found for non-existent group ID"""
        with self.assertRaises(HTTPException) as context:
            expense_service.get_group_expenses(
                group_id=999,
                current_user=self.user1,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 404)

    def test_default_pagination(self):
        """Should return all 3 expenses because limit defaults to 10"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db
        )
        self.assertEqual(len(res), 3)

    def test_pagination_offset_limit(self):
        """Should return second newest expense when page=2, limit=1"""
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            page=2,
            limit=1
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 2)  # exp2 (id=2) is the 2nd newest

    def test_pagination_invalid_page(self):
        """Should raise 400 Bad Request if page <= 0"""
        with self.assertRaises(HTTPException) as context:
            expense_service.get_group_expenses(
                group_id=1,
                current_user=self.user1,
                db=self.db,
                page=0
            )
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Page must be greater than 0", context.exception.detail)

    def test_pagination_invalid_limit(self):
        """Should raise 400 Bad Request if limit <= 0"""
        with self.assertRaises(HTTPException) as context:
            expense_service.get_group_expenses(
                group_id=1,
                current_user=self.user1,
                db=self.db,
                limit=-5
            )
        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("Limit must be greater than 0", context.exception.detail)

    def test_pagination_with_filters(self):
        """Filters and pagination should work together"""
        # User 1 has exp3 (newest, id=3) and exp1 (older, id=1).
        # With page=2, limit=1, it should return exp1 (id=1).
        res = expense_service.get_group_expenses(
            group_id=1,
            current_user=self.user1,
            db=self.db,
            user_id=1,
            page=2,
            limit=1
        )
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], 1)

if __name__ == "__main__":
    unittest.main()
