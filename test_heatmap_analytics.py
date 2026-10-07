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


class TestHeatmapAnalytics(unittest.TestCase):
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

    def add_expense(self, expense_id, amount, timestamp, group_id=1):
        self.db.add(Expense(
            id=expense_id,
            title=f"Expense {expense_id}",
            amount=amount,
            group_id=group_id,
            paid_by=1 if group_id == 1 else 2,
            created_at=datetime.fromisoformat(timestamp),
        ))

    def test_day_and_time_bucket_aggregation(self):
        # 2026-09-07 is Monday; these cover Morning, Afternoon, Evening, Night.
        self.add_expense(1, 100, "2026-09-07T08:00:00")
        self.add_expense(2, 200, "2026-09-07T14:00:00")
        self.add_expense(3, 300, "2026-09-07T19:00:00")
        self.add_expense(4, 400, "2026-09-07T23:00:00")
        self.add_expense(5, 500, "2026-09-07T19:30:00")
        self.db.commit()

        result = analytics_service.get_heatmap(self.alice, self.db, month="2026-09")
        cells = {(cell["day"], cell["period"]): cell for cell in result["data"]}

        self.assertEqual(cells[("Monday", "Morning")]["amount"], 100.0)
        self.assertEqual(cells[("Monday", "Afternoon")]["amount"], 200.0)
        self.assertEqual(cells[("Monday", "Evening")]["amount"], 800.0)
        self.assertEqual(cells[("Monday", "Night")]["amount"], 400.0)
        self.assertEqual(cells[("Monday", "Evening")]["count"], 2)
        self.assertEqual(result["highest_period"], {
            "day": "Monday",
            "period": "Evening",
            "amount": 800.0,
            "count": 2,
        })
        self.assertEqual(result["highest_day"]["day"], "Monday")
        self.assertEqual(result["highest_time_period"]["period"], "Evening")

    def test_month_filter_empty_state_and_user_scope(self):
        self.add_expense(1, 100, "2026-08-07T08:00:00")
        self.add_expense(2, 900, "2026-09-07T08:00:00", group_id=2)
        self.db.commit()

        september = analytics_service.get_heatmap(self.alice, self.db, month="2026-09")
        self.assertIsNone(september["highest_period"])
        self.assertEqual(sum(cell["amount"] for cell in september["data"]), 0.0)

        empty = analytics_service.get_heatmap(self.alice, self.db, month="2026-10")
        self.assertEqual(len(empty["data"]), 28)
        self.assertTrue(all(cell["amount"] == 0.0 and cell["count"] == 0 for cell in empty["data"]))

    def test_no_groups_returns_safe_empty_grid(self):
        user = User(id=3, username="carol", email="carol@example.com", password_hash="hash")
        self.db.add(user)
        self.db.commit()

        result = analytics_service.get_heatmap(user, self.db)
        self.assertEqual(len(result["data"]), 28)
        self.assertIsNone(result["highest_day"])
        self.assertIsNone(result["highest_time_period"])
        self.assertIsNone(result["highest_period"])


if __name__ == "__main__":
    unittest.main()