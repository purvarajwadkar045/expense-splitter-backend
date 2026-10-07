import os
import sys
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.budget import Budget
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.services import analytics_service


class TestInsightsAnalytics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        self.alice = User(id=1, username="alice", email="alice@example.com", password_hash="hash")
        self.bob = User(id=2, username="bob", email="bob@example.com", password_hash="hash")
        self.db.add_all([
            self.alice,
            self.bob,
            Group(id=1, name="Trip", created_by=1),
            Group(id=2, name="Bob Private", created_by=2),
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
            GroupMember(id=3, group_id=2, user_id=2),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def add_expense(self, expense_id, amount, category, title, month, group_id=1):
        self.db.add(Expense(
            id=expense_id,
            title=title,
            amount=amount,
            category=category,
            group_id=group_id,
            paid_by=1 if group_id == 1 else 2,
            created_at=datetime.strptime(f"{month}-10", "%Y-%m-%d"),
        ))

    def test_current_month_insights_and_budget(self):
        self.add_expense(1, 8000, "Food", "Dinner", "2026-09")
        self.add_expense(2, 5000, "Travel", "Flight", "2026-09")
        self.add_expense(3, 2000, "Shopping", "Bag", "2026-09")
        self.add_expense(4, 20000, "Food", "Previous dinner", "2026-08")
        self.db.add(Budget(user_id=1, budget_month="2026-09", amount=20000))
        self.db.commit()

        result = analytics_service.get_insights(self.alice, self.db, month="2026-09")

        self.assertEqual(result["total_spent"], 15000.0)
        self.assertEqual(result["average_expense"], 5000.0)
        self.assertEqual(result["expense_count"], 3)
        self.assertEqual(result["highest_expense"]["amount"], 8000.0)
        self.assertEqual(result["lowest_expense"]["amount"], 2000.0)
        self.assertEqual(result["top_category"]["category"], "Food")
        self.assertEqual(result["top_category"]["percentage"], 53.33)
        self.assertEqual(result["most_frequent_category"]["count"], 1)
        self.assertEqual(result["monthly_change"], {
            "current": 15000.0,
            "previous": 20000.0,
            "percentage": -25.0,
            "direction": "decrease",
        })
        self.assertEqual(result["budget"]["percentage_used"], 75.0)

    def test_increase_equal_and_zero_previous_month(self):
        self.add_expense(1, 24500, "Food", "Current", "2026-09")
        self.add_expense(2, 20000, "Food", "Previous", "2026-08")
        self.db.commit()
        increase = analytics_service.get_insights(self.alice, self.db, month="2026-09")
        self.assertEqual(increase["monthly_change"]["percentage"], 22.5)
        self.assertEqual(increase["monthly_change"]["direction"], "increase")

        self.add_expense(3, 4500, "Food", "Equal", "2026-10")
        self.db.commit()
        equal = analytics_service.get_insights(self.alice, self.db, month="2026-10")
        self.assertEqual(equal["monthly_change"]["percentage"], -81.63)

        zero_previous = analytics_service.get_insights(self.alice, self.db, month="2026-08")
        self.assertIsNone(zero_previous["monthly_change"]["percentage"])
        self.assertEqual(zero_previous["monthly_change"]["direction"], "increase")

    def test_empty_and_user_scoped_results(self):
        empty = analytics_service.get_insights(self.alice, self.db, month="2026-09")
        self.assertEqual(empty["total_spent"], 0.0)
        self.assertEqual(empty["expense_count"], 0)
        self.assertIsNone(empty["top_category"])
        self.assertIsNone(empty["top_group"])

        self.add_expense(1, 9000, "Shopping", "Private", "2026-09", group_id=2)
        self.db.commit()
        self.assertEqual(analytics_service.get_insights(self.alice, self.db, month="2026-09")["total_spent"], 0.0)


if __name__ == "__main__":
    unittest.main()