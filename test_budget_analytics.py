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
from app.schemas.analytics import BudgetUpsert
from app.services import analytics_service


class TestBudgetAnalytics(unittest.TestCase):
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
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def add_expense(self, expense_id, amount, month="2026-09"):
        self.db.add(Expense(
            id=expense_id,
            title=f"Expense {expense_id}",
            amount=amount,
            group_id=1,
            paid_by=1,
            created_at=datetime.strptime(f"{month}-10", "%Y-%m-%d"),
        ))
        self.db.commit()

    def set_budget(self, amount, month="2026-09", user=None):
        return analytics_service.upsert_budget(
            user or self.alice,
            self.db,
            BudgetUpsert(month=month, amount=amount),
        )

    def test_within_budget(self):
        self.add_expense(1, 12000)

        result = self.set_budget(20000)

        self.assertEqual(result["spent"], 12000.0)
        self.assertEqual(result["remaining"], 8000.0)
        self.assertEqual(result["percentage_used"], 60.0)
        self.assertEqual(result["status"], "within_budget")

    def test_near_limit_and_exceeded(self):
        self.add_expense(1, 18000)
        near_limit = self.set_budget(20000)
        self.assertEqual(near_limit["status"], "near_limit")
        self.assertEqual(near_limit["percentage_used"], 90.0)

        self.db.query(Expense).delete()
        self.db.commit()
        self.add_expense(2, 24000)
        exceeded = self.set_budget(20000)
        self.assertEqual(exceeded["remaining"], -4000.0)
        self.assertEqual(exceeded["percentage_used"], 120.0)
        self.assertEqual(exceeded["status"], "exceeded")

    def test_no_budget_and_zero_spending(self):
        no_budget = analytics_service.get_budget(self.alice, self.db, "2026-09")
        self.assertEqual(no_budget["status"], "not_set")
        self.assertIsNone(no_budget["budget"])
        self.assertIsNone(no_budget["remaining"])

        zero_spend = self.set_budget(20000)
        self.assertEqual(zero_spend["spent"], 0.0)
        self.assertEqual(zero_spend["remaining"], 20000.0)
        self.assertEqual(zero_spend["percentage_used"], 0.0)
        self.assertEqual(zero_spend["status"], "within_budget")

    def test_month_isolation_and_user_privacy(self):
        self.add_expense(1, 12000, "2026-09")
        self.add_expense(2, 9000, "2026-10")
        september = self.set_budget(20000, "2026-09")
        self.assertEqual(september["spent"], 12000.0)

        bob_budget = self.set_budget(5000, "2026-09", self.bob)
        self.assertEqual(bob_budget["budget"], 5000.0)
        alice_view = analytics_service.get_budget(self.alice, self.db, "2026-09")
        self.assertEqual(alice_view["budget"], 20000.0)

    def test_invalid_budget_input(self):
        with self.assertRaises(ValueError):
            BudgetUpsert(month="2026-13", amount=100)
        with self.assertRaises(ValueError):
            BudgetUpsert(month="2026-09", amount=0)


if __name__ == "__main__":
    unittest.main()