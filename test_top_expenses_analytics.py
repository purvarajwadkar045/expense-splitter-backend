import os
import sys
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.services import analytics_service


class TestTopExpensesAnalytics(unittest.TestCase):
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

    def add_expense(self, expense_id, amount, title, category="Food", month="2026-09", group_id=1, day=10):
        self.db.add(Expense(
            id=expense_id,
            title=title,
            amount=amount,
            category=category,
            group_id=group_id,
            paid_by=1 if group_id == 1 else 2,
            created_at=datetime.strptime(f"{month}-{day:02d}", "%Y-%m-%d"),
        ))

    def test_sorted_limit_and_related_fields(self):
        for expense_id, amount in enumerate([1000, 5000, 2000, 8000], start=1):
            self.add_expense(expense_id, amount, f"Expense {expense_id}")
        self.db.commit()

        result = analytics_service.get_top_expenses(self.alice, self.db)

        self.assertEqual([item["amount"] for item in result["expenses"]], [8000.0, 5000.0, 2000.0, 1000.0])
        self.assertEqual(result["count"], 4)
        self.assertEqual(result["expenses"][0]["group"], {"group_id": 1, "name": "Trip"})
        self.assertEqual(result["expenses"][0]["payer"], {"user_id": 1, "name": "alice"})

    def test_limit_ties_filters_and_month(self):
        for expense_id in range(1, 13):
            self.add_expense(expense_id, 1000, f"Expense {expense_id}", category="Travel" if expense_id == 1 else "Food", day=expense_id if expense_id < 10 else 10)
        self.add_expense(20, 9000, "Old", month="2026-08")
        self.db.commit()

        limited = analytics_service.get_top_expenses(self.alice, self.db, limit=10)
        self.assertEqual(limited["count"], 10)
        self.assertEqual([item["expense_id"] for item in limited["expenses"]], [20, *range(12, 3, -1)])

        travel = analytics_service.get_top_expenses(self.alice, self.db, category="Travel")
        self.assertEqual([item["expense_id"] for item in travel["expenses"]], [1])

        september = analytics_service.get_top_expenses(self.alice, self.db, month="2026-09")
        self.assertNotIn(20, [item["expense_id"] for item in september["expenses"]])

    def test_empty_and_private_data_are_scoped(self):
        self.add_expense(1, 9000, "Private", group_id=2)
        self.db.commit()

        result = analytics_service.get_top_expenses(self.alice, self.db)
        self.assertEqual(result, {"expenses": [], "count": 0})

    def test_invalid_limit_and_group_access(self):
        with self.assertRaises(Exception):
            analytics_service.get_top_expenses(self.alice, self.db, limit=0)
        with self.assertRaises(Exception):
            analytics_service.get_top_expenses(self.alice, self.db, limit=51)
        with self.assertRaises(Exception):
            analytics_service.get_top_expenses(self.alice, self.db, group_id=2)


if __name__ == "__main__":
    unittest.main()