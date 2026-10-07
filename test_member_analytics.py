import os
import sys
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.user import User
from app.services import analytics_service


class TestMemberAnalytics(unittest.TestCase):
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
        self.dave = User(id=4, username="dave", email="dave@example.com", password_hash="hash")
        self.db.add_all([
            self.alice,
            self.bob,
            self.carol,
            self.dave,
            Group(id=1, name="Shared", created_by=1),
            Group(id=2, name="Private", created_by=2),
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
            GroupMember(id=3, group_id=1, user_id=3),
            GroupMember(id=4, group_id=2, user_id=2),
            GroupMember(id=5, group_id=2, user_id=4),
            Expense(id=1, title="Equal dinner", amount=900, group_id=1, paid_by=1, created_at=datetime(2026, 1, 5)),
            Expense(id=2, title="Custom taxi", amount=600, group_id=1, paid_by=2, created_at=datetime(2026, 2, 5)),
            Expense(id=3, title="Private expense", amount=1000, group_id=2, paid_by=2, created_at=datetime(2026, 2, 5)),
            ExpenseSplit(id=1, expense_id=2, user_id=1, amount=100),
            ExpenseSplit(id=2, expense_id=2, user_id=2, amount=200),
            ExpenseSplit(id=3, expense_id=2, user_id=3, amount=300),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_member_totals_use_payers_and_split_amounts(self):
        result = analytics_service.get_member_analysis(self.alice, self.db)
        members = {member["user_id"]: member for member in result["members"]}

        self.assertEqual(members[1]["paid"], 900.0)
        self.assertEqual(members[1]["owes"], 400.0)
        self.assertEqual(members[1]["net"], 500.0)
        self.assertEqual(members[2]["paid"], 600.0)
        self.assertEqual(members[2]["owes"], 500.0)
        self.assertEqual(members[2]["net"], 100.0)
        self.assertEqual(members[3]["paid"], 0.0)
        self.assertEqual(members[3]["owes"], 600.0)
        self.assertEqual(members[3]["net"], -600.0)

        self.assertEqual(result["highest_payer"]["user_id"], 1)
        self.assertEqual(result["highest_debtor"]["user_id"], 3)

    def test_private_group_is_not_exposed_and_group_filter_is_authorized(self):
        result = analytics_service.get_member_analysis(self.alice, self.db)
        self.assertNotIn(4, {member["user_id"] for member in result["members"]})
        self.assertEqual(
            analytics_service.get_member_analysis(self.alice, self.db, group_id=1)["members"],
            result["members"],
        )
        with self.assertRaises(Exception):
            analytics_service.get_member_analysis(self.alice, self.db, group_id=2)

    def test_empty_state(self):
        user = User(id=5, username="erin", email="erin@example.com", password_hash="hash")
        self.db.add(user)
        self.db.commit()

        self.assertEqual(analytics_service.get_member_analysis(user, self.db), {
            "members": [],
            "most_active_member": None,
            "highest_payer": None,
            "highest_debtor": None,
        })


if __name__ == "__main__":
    unittest.main()