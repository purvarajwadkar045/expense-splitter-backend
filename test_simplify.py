import sys
import os
import unittest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.database import Base
from app.models.user import User
from app.models.group import Group
from app.models.group_member import GroupMember
from app.models.expense import Expense
from app.models.expense_split import ExpenseSplit
from app.services import simplify_service

class TestSimplifyService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed test data
        self.user1 = User(id=1, username="Rahul", email="rahul@example.com", password_hash="hash")
        self.user2 = User(id=2, username="Purva", email="purva@example.com", password_hash="hash")
        self.user3 = User(id=3, username="Amit", email="amit@example.com", password_hash="hash")
        self.user4 = User(id=4, username="UnauthorizedUser", email="unauth@example.com", password_hash="hash")

        self.group = Group(id=1, name="Rent Group", created_by=1)

        self.member1 = GroupMember(id=1, group_id=1, user_id=1)
        self.member2 = GroupMember(id=2, group_id=1, user_id=2)
        self.member3 = GroupMember(id=3, group_id=1, user_id=3)

        self.db.add_all([
            self.user1, self.user2, self.user3, self.user4,
            self.group,
            self.member1, self.member2, self.member3
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_simplify_debts_success(self):
        """Should simplify debts correctly matching the user's example"""
        # Expense 1: Purva (id=2) paid $500, Rahul (id=1) owes $500 (custom split)
        exp1 = Expense(id=1, title="Expense 1", amount=500.0, group_id=1, paid_by=2)
        split1 = ExpenseSplit(id=1, expense_id=1, user_id=1, amount=500.0)

        # Expense 2: Amit (id=3) paid $200, Purva (id=2) owes $200 (custom split)
        exp2 = Expense(id=2, title="Expense 2", amount=200.0, group_id=1, paid_by=3)
        split2 = ExpenseSplit(id=2, expense_id=2, user_id=2, amount=200.0)

        self.db.add_all([exp1, split1, exp2, split2])
        self.db.commit()

        # Simplify
        txs = simplify_service.simplify_debts(group_id=1, current_user=self.user1, db=self.db)

        # We expect:
        # 1. Rahul (id=1) -> Purva (id=2) amount 300
        # 2. Rahul (id=1) -> Amit (id=3) amount 200
        self.assertEqual(len(txs), 2)

        # Match txs by to_user_id
        txs_by_to = {t["to_user_id"]: t for t in txs}
        
        self.assertIn(2, txs_by_to)
        self.assertEqual(txs_by_to[2]["from_user_id"], 1)
        self.assertEqual(txs_by_to[2]["amount"], 300.0)

        self.assertIn(3, txs_by_to)
        self.assertEqual(txs_by_to[3]["from_user_id"], 1)
        self.assertEqual(txs_by_to[3]["amount"], 200.0)

    def test_simplify_debts_non_member(self):
        """Should raise 403 Forbidden when a non-member tries to access group simplification"""
        with self.assertRaises(HTTPException) as context:
            simplify_service.simplify_debts(group_id=1, current_user=self.user4, db=self.db)
        self.assertEqual(context.exception.status_code, 403)

    def test_simplify_debts_invalid_group(self):
        """Should raise 404 Not Found when group does not exist"""
        with self.assertRaises(HTTPException) as context:
            simplify_service.simplify_debts(group_id=999, current_user=self.user1, db=self.db)
        self.assertEqual(context.exception.status_code, 404)

if __name__ == "__main__":
    unittest.main()
