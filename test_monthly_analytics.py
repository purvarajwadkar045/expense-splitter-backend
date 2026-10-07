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


class TestMonthlyAnalytics(unittest.TestCase):
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
            Group(id=1, name="Shared", created_by=1),
            Group(id=2, name="Private", created_by=2),
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

    def test_empty_state(self):
        result = analytics_service.get_monthly_analysis(self.alice, self.db)

        self.assertEqual(result, {
            "months": [],
            "peak_month": None,
            "lowest_month": None,
            "average_monthly_spending": 0.0,
        })

    def test_same_month_is_aggregated(self):
        self.db.add_all([
            Expense(id=1, title="Dinner", amount=100, group_id=1, paid_by=1, created_at=datetime(2026, 1, 5)),
            Expense(id=2, title="Taxi", amount=50, group_id=1, paid_by=2, created_at=datetime(2026, 1, 20)),
        ])
        self.db.commit()

        result = analytics_service.get_monthly_analysis(self.alice, self.db)

        self.assertEqual(result["months"], [{
            "month": "2026-01",
            "total": 150.0,
            "expense_count": 2,
            "change_percentage": None,
        }])
        self.assertEqual(result["average_monthly_spending"], 150.0)

    def test_month_over_month_changes_and_gap(self):
        self.db.add_all([
            Expense(id=1, title="January", amount=100, group_id=1, paid_by=1, created_at=datetime(2026, 1, 5)),
            Expense(id=2, title="February", amount=150, group_id=1, paid_by=1, created_at=datetime(2026, 2, 5)),
            Expense(id=3, title="March", amount=75, group_id=1, paid_by=1, created_at=datetime(2026, 3, 5)),
        ])
        self.db.commit()

        result = analytics_service.get_monthly_analysis(self.alice, self.db)

        self.assertEqual([month["change_percentage"] for month in result["months"]], [None, 50.0, -50.0])
        self.assertEqual(result["peak_month"], {"month": "2026-02", "total": 150.0})
        self.assertEqual(result["lowest_month"], {"month": "2026-03", "total": 75.0})
        self.assertEqual(result["average_monthly_spending"], 108.33)

    def test_gap_has_no_unsafe_comparison_and_users_are_isolated(self):
        self.db.add_all([
            Expense(id=1, title="January", amount=100, group_id=1, paid_by=1, created_at=datetime(2026, 1, 5)),
            Expense(id=2, title="March", amount=200, group_id=1, paid_by=1, created_at=datetime(2026, 3, 5)),
            Expense(id=3, title="Bob expense", amount=900, group_id=2, paid_by=2, created_at=datetime(2026, 1, 5)),
        ])
        self.db.commit()

        alice_result = analytics_service.get_monthly_analysis(self.alice, self.db)
        bob_result = analytics_service.get_monthly_analysis(self.bob, self.db)

        self.assertEqual([month["total"] for month in alice_result["months"]], [100.0, 200.0])
        self.assertEqual(alice_result["months"][1]["change_percentage"], None)
        self.assertEqual([month["total"] for month in bob_result["months"]], [1000.0, 200.0])


if __name__ == "__main__":
    unittest.main()