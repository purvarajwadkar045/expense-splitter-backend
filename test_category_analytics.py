import os
import sys
import unittest

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.activity import Activity
from app.models.expense import Expense
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.notification import Notification
from app.models.user import User
from app.schemas.expense import ExpenseCreate
from app.services import analytics_service, expense_service


class TestCategoryAnalytics(unittest.TestCase):
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
            Group(id=2, name="Bob only", created_by=2),
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
            GroupMember(id=3, group_id=2, user_id=2),
            Expense(id=1, title="Dinner", amount=100, category="Food", group_id=1, paid_by=1),
            Expense(id=2, title="Taxi", amount=50, category="Travel", group_id=1, paid_by=2),
            Expense(id=3, title="Private", amount=900, category="Shopping", group_id=2, paid_by=2),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_category_analysis_is_scoped_and_aggregated(self):
        result = analytics_service.get_category_analysis(self.alice, self.db)

        self.assertEqual(result["total_spending"], 150.0)
        self.assertEqual(result["most_expensive_category"], "Food")
        self.assertEqual(result["categories"][0], {
            "category": "Food",
            "total_amount": 100.0,
            "percentage": 66.67,
        })
        self.assertAlmostEqual(
            sum(item["percentage"] for item in result["categories"]),
            100.0,
            places=1,
        )

    def test_category_analysis_empty_state(self):
        user = User(id=3, username="carol", email="carol@example.com", password_hash="hash")
        self.db.add(user)
        self.db.commit()

        self.assertEqual(analytics_service.get_category_analysis(user, self.db), {
            "total_spending": 0.0,
            "categories": [],
            "most_expensive_category": None,
        })

    def test_expense_creation_persists_category_and_defaults_other(self):
        created = expense_service.create_expense(
            1,
            ExpenseCreate(title="Lunch", amount=25, category="Food"),
            self.alice,
            self.db,
        )
        self.assertEqual(created.category, "Food")

        defaulted = ExpenseCreate(title="Unknown", amount=10)
        self.assertEqual(defaulted.category, "Other")

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(ValidationError):
            ExpenseCreate(title="Invalid", amount=10, category="Gaming")


if __name__ == "__main__":
    unittest.main()