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
from app.services.expense_service import get_group_expenses


class TestAnalyzerExpenseHistory(unittest.TestCase):
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
            Expense(id=1, title="Train", amount=500, category="Travel", group_id=1, paid_by=1, created_at=datetime(2026, 9, 10)),
            Expense(id=2, title="Dinner", amount=800, category="Food", group_id=1, paid_by=2, created_at=datetime(2026, 9, 11)),
            Expense(id=3, title="Train", amount=900, category="Travel", group_id=1, paid_by=1, created_at=datetime(2026, 10, 1)),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_filtered_history_matches_analyzer_filters(self):
        rows = get_group_expenses(
            group_id=1,
            current_user=self.alice,
            db=self.db,
            date_range="this-year",
            search="train",
            category="travel",
            member_id=1,
            min_amount=500,
            max_amount=500,
            limit=10,
        )

        self.assertEqual([row["id"] for row in rows], [1])

    def test_filtered_history_rejects_invalid_amount_bounds(self):
        with self.assertRaises(Exception):
            get_group_expenses(
                group_id=1,
                current_user=self.alice,
                db=self.db,
                min_amount=1000,
                max_amount=500,
                limit=10,
            )


if __name__ == "__main__":
    unittest.main()