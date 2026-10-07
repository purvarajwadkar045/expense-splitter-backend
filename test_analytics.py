import os
import sys
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.settlement import Settlement
from app.models.user import User
from app.services import analytics_service


class TestAnalyticsSummary(unittest.TestCase):
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
            Expense(id=1, title="Dinner", amount=100, group_id=1, paid_by=1),
            Expense(id=2, title="Taxi", amount=40, group_id=1, paid_by=2),
            Expense(id=3, title="Private", amount=900, group_id=2, paid_by=2),
            Settlement(id=1, group_id=1, payer_id=2, receiver_id=1, amount=25),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_summary_is_scoped_and_calculated(self):
        summary = analytics_service.get_summary(self.alice, self.db)

        self.assertEqual(summary["total_groups"], 1)
        self.assertEqual(summary["total_transactions"], 2)
        self.assertEqual(summary["total_expenses"], 140.0)
        self.assertEqual(summary["average_expense"], 70.0)
        self.assertEqual(summary["highest_expense"], 100.0)
        self.assertEqual(summary["lowest_expense"], 40.0)
        self.assertEqual(summary["total_settlements"], 25.0)
        self.assertEqual(summary["my_spending"], 100.0)
        self.assertEqual(summary["i_am_owed"], 5.0)

    def test_summary_is_zero_without_groups(self):
        user = User(id=3, username="carol", email="carol@example.com", password_hash="hash")
        summary = analytics_service.get_summary(user, self.db)

        self.assertEqual(summary["total_groups"], 0)
        self.assertEqual(summary["total_transactions"], 0)
        self.assertEqual(summary["total_expenses"], 0.0)
        self.assertEqual(summary["total_settlements"], 0.0)
        self.assertEqual(summary["pending_balance"], 0.0)


if __name__ == "__main__":
    unittest.main()