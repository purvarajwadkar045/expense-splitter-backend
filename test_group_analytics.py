import os
import sys
import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.services import analytics_service


class TestGroupAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.alice = User(id=1, username="alice", email="alice@example.com", password_hash="hash")
        self.bob = User(id=2, username="bob", email="bob@example.com", password_hash="hash")
        self.carol = User(id=3, username="carol", email="carol@example.com", password_hash="hash")
        self.db.add_all([
            self.alice,
            self.bob,
            self.carol,
            Group(id=1, name="Goa Trip", created_by=1),
            Group(id=2, name="Bob Private", created_by=2),
            Group(id=3, name="Empty Group", created_by=1),
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
            GroupMember(id=3, group_id=1, user_id=3),
            GroupMember(id=4, group_id=2, user_id=2),
            GroupMember(id=5, group_id=2, user_id=3),
            GroupMember(id=6, group_id=3, user_id=1),
            Expense(id=1, title="Hotel", amount=2200, group_id=1, paid_by=1, created_at=datetime(2026, 1, 10)),
            Expense(id=2, title="Food", amount=600, group_id=1, paid_by=2, created_at=datetime(2026, 2, 10)),
            Expense(id=3, title="Travel", amount=1200, group_id=1, paid_by=1, created_at=datetime(2026, 3, 10)),
            Expense(id=4, title="Private", amount=9000, group_id=2, paid_by=2, created_at=datetime(2026, 1, 10)),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_group_totals_members_average_and_highest_expense(self):
        result = analytics_service.get_group_analysis(self.alice, self.db)
        groups = {group["group_id"]: group for group in result["groups"]}

        goa = groups[1]
        self.assertEqual(goa["total_expenses"], 4000.0)
        self.assertEqual(goa["member_count"], 3)
        self.assertEqual(goa["expense_count"], 3)
        self.assertEqual(goa["average_expense"], 1333.33)
        self.assertEqual(goa["highest_expense"], {
            "expense_id": 1,
            "description": "Hotel",
            "amount": 2200.0,
        })

        self.assertEqual(groups[3]["member_count"], 1)
        self.assertEqual(groups[3]["total_expenses"], 0.0)
        self.assertEqual(groups[3]["expense_count"], 0)
        self.assertEqual(groups[3]["average_expense"], 0.0)
        self.assertIsNone(groups[3]["highest_expense"])

    def test_group_filter_date_filter_and_privacy(self):
        result = analytics_service.get_group_analysis(
            self.alice,
            self.db,
            group_id=1,
            start_date=date(2026, 1, 1),
            end_date=date(2026, 2, 28),
        )
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(result["groups"][0]["total_expenses"], 2800.0)
        self.assertEqual(result["groups"][0]["expense_count"], 2)
        self.assertEqual(result["groups"][0]["average_expense"], 1400.0)

        with self.assertRaises(Exception):
            analytics_service.get_group_analysis(self.alice, self.db, group_id=2)

    def test_empty_user_state(self):
        user = User(id=4, username="erin", email="erin@example.com", password_hash="hash")
        self.db.add(user)
        self.db.commit()

        self.assertEqual(analytics_service.get_group_analysis(user, self.db), {"groups": []})


if __name__ == "__main__":
    unittest.main()