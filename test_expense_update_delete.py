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
from app.models.settlement import Settlement
from app.services import expense_service
from app.schemas.expense import ExpenseUpdate


class TestExpenseUpdateDelete(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed test data
        self.user1 = User(id=1, username="Creator", email="creator@example.com", password_hash="hash")
        self.user2 = User(id=2, username="Member", email="member@example.com", password_hash="hash")
        self.user3 = User(id=3, username="NonMember", email="nonmember@example.com", password_hash="hash")

        self.group = Group(id=1, name="Trip Group", created_by=1)

        self.member1 = GroupMember(id=1, group_id=1, user_id=1)
        self.member2 = GroupMember(id=2, group_id=1, user_id=2)

        self.db.add_all([
            self.user1, self.user2, self.user3,
            self.group,
            self.member1, self.member2
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_update_expense_success(self):
        """Should successfully update the expense and recreate splits correctly"""
        # Create an expense with no splits initially (fallback to all members: user1, user2)
        exp = Expense(id=10, title="Dinner", amount=100.0, group_id=1, paid_by=1)
        self.db.add(exp)
        self.db.commit()

        # Update with new amount and explicit participants (user1 and user2)
        update_data = ExpenseUpdate(
            title="Fancy Dinner",
            amount=150.0,
            participants=[1, 2]
        )

        updated_exp = expense_service.update_expense(
            expense_id=10,
            expense_data=update_data,
            current_user=self.user1,
            db=self.db
        )

        self.assertEqual(updated_exp.title, "Fancy Dinner")
        self.assertEqual(updated_exp.amount, 150.0)

        # Check that splits were created correctly
        splits = self.db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == 10).all()
        self.assertEqual(len(splits), 2)
        self.assertEqual(splits[0].amount, 75.0)
        self.assertEqual(splits[1].amount, 75.0)
        self.assertCountEqual([s.user_id for s in splits], [1, 2])

    def test_update_expense_not_found(self):
        """Should raise 404 when updating non-existent expense"""
        update_data = ExpenseUpdate(title="Non-existent")
        with self.assertRaises(HTTPException) as context:
            expense_service.update_expense(
                expense_id=999,
                expense_data=update_data,
                current_user=self.user1,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 404)

    def test_update_expense_permission_denied(self):
        """Should raise 403 when user is not the creator of the expense"""
        exp = Expense(id=10, title="Lunch", amount=50.0, group_id=1, paid_by=1)
        self.db.add(exp)
        self.db.commit()

        update_data = ExpenseUpdate(title="Forbidden Update")
        with self.assertRaises(HTTPException) as context:
            expense_service.update_expense(
                expense_id=10,
                expense_data=update_data,
                current_user=self.user2,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 403)

    def test_update_expense_invalid_amount(self):
        """Should raise 400 when updating amount to <= 0"""
        exp = Expense(id=10, title="Lunch", amount=50.0, group_id=1, paid_by=1)
        self.db.add(exp)
        self.db.commit()

        update_data = ExpenseUpdate(amount=-10.0)
        with self.assertRaises(HTTPException) as context:
            expense_service.update_expense(
                expense_id=10,
                expense_data=update_data,
                current_user=self.user1,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_update_expense_non_member_participant(self):
        """Should raise 400 when updating with a participant who is not in the group"""
        exp = Expense(id=10, title="Lunch", amount=50.0, group_id=1, paid_by=1)
        self.db.add(exp)
        self.db.commit()

        # user3 (NonMember) is not a member of the group
        update_data = ExpenseUpdate(participants=[1, 3])
        with self.assertRaises(HTTPException) as context:
            expense_service.update_expense(
                expense_id=10,
                expense_data=update_data,
                current_user=self.user1,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 400)

    def test_delete_expense_success(self):
        """Should successfully delete splits first, then delete the expense"""
        exp = Expense(id=10, title="Snacks", amount=20.0, group_id=1, paid_by=1)
        split = ExpenseSplit(expense_id=10, user_id=1, amount=20.0)
        self.db.add_all([exp, split])
        self.db.commit()

        # Verify splits and expense exist before deletion
        self.assertIsNotNone(self.db.query(Expense).filter(Expense.id == 10).first())
        self.assertEqual(self.db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == 10).count(), 1)

        # Delete
        expense_service.delete_expense(
            expense_id=10,
            current_user=self.user1,
            db=self.db
        )

        # Verify splits and expense are deleted
        self.assertIsNone(self.db.query(Expense).filter(Expense.id == 10).first())
        self.assertEqual(self.db.query(ExpenseSplit).filter(ExpenseSplit.expense_id == 10).count(), 0)

    def test_delete_expense_not_found(self):
        """Should raise 404 when deleting a non-existent expense"""
        with self.assertRaises(HTTPException) as context:
            expense_service.delete_expense(
                expense_id=999,
                current_user=self.user1,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 404)

    def test_delete_expense_permission_denied(self):
        """Should raise 403 when deleting an expense created by another user"""
        exp = Expense(id=10, title="Lunch", amount=50.0, group_id=1, paid_by=1)
        self.db.add(exp)
        self.db.commit()

        with self.assertRaises(HTTPException) as context:
            expense_service.delete_expense(
                expense_id=10,
                current_user=self.user2,
                db=self.db
            )
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
