import sys
import os
import unittest
from datetime import datetime
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
from app.models.activity import Activity

from app.services import group_service, expense_service, settlement_service, activity_service
from app.schemas.group import GroupCreate
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.settlement import SettlementCreate


class TestActivityTimeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed basic users
        self.user1 = User(id=1, username="Purva", email="purva@example.com", password_hash="hash")
        self.user2 = User(id=2, username="Rahul", email="rahul@example.com", password_hash="hash")
        self.user3 = User(id=3, username="Amit", email="amit@example.com", password_hash="hash")
        self.user4 = User(id=4, username="Stranger", email="stranger@example.com", password_hash="hash")

        self.db.add_all([self.user1, self.user2, self.user3, self.user4])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_log_activity_directly(self):
        """Should directly write activity log into database"""
        # Create a dummy group
        group = Group(id=1, name="Direct Test", created_by=1)
        self.db.add(group)
        self.db.commit()

        act = activity_service.log_activity(
            self.db,
            group_id=1,
            user_id=1,
            activity_type="GROUP_CREATED",
            message="Purva created group 'Direct Test'"
        )

        self.assertIsNotNone(act.id)
        self.assertEqual(act.activity_type, "GROUP_CREATED")
        self.assertEqual(act.message, "Purva created group 'Direct Test'")
        self.assertEqual(act.user_id, 1)
        self.assertEqual(act.group_id, 1)

    def test_group_creation_activity(self):
        """Should automatically log GROUP_CREATED activity on group creation"""
        group_data = GroupCreate(name="Goa Trip", description="Fun Trip")
        group = group_service.create_group(group_data, self.user1, self.db)

        # Check activity logs
        acts = self.db.query(Activity).filter(Activity.group_id == group.id).all()
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0].activity_type, "GROUP_CREATED")
        self.assertEqual(acts[0].message, "Purva created group 'Goa Trip'")

    def test_member_addition_activity(self):
        """Should automatically log MEMBER_ADDED activity when a member is added"""
        # Set up group
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)

        # Add Rahul (user_id=2)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        acts = self.db.query(Activity).filter(Activity.group_id == group.id).all()
        # Should have 2 activities now: GROUP_CREATED and MEMBER_ADDED
        self.assertEqual(len(acts), 2)
        self.assertEqual(acts[1].activity_type, "MEMBER_ADDED")
        self.assertEqual(acts[1].message, "Purva added Rahul to the group")

    def test_expense_creation_activity(self):
        """Should automatically log EXPENSE_CREATED activity when an expense is added"""
        # Set up group and members
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        # Add expense of ₹1200
        exp_data = ExpenseCreate(title="Dinner", amount=1200.0, description="Yummy dinner")
        expense_service.create_expense(group.id, exp_data, self.user1, self.db)

        acts = self.db.query(Activity).filter(Activity.group_id == group.id).all()
        self.assertEqual(len(acts), 3)
        self.assertEqual(acts[2].activity_type, "EXPENSE_CREATED")
        self.assertEqual(acts[2].message, "Purva added an expense 'Dinner' of ₹1200")

    def test_expense_update_and_delete_activities(self):
        """Should automatically log EXPENSE_UPDATED and EXPENSE_DELETED activities"""
        # Set up group
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        
        # Add expense
        exp_data = ExpenseCreate(title="Dinner", amount=1200.0)
        exp = expense_service.create_expense(group.id, exp_data, self.user1, self.db)

        # Update expense to ₹1500
        update_data = ExpenseUpdate(title="Fancy Dinner", amount=1500.0)
        expense_service.update_expense(exp.id, update_data, self.user1, self.db)

        # Delete expense
        expense_service.delete_expense(exp.id, self.user1, self.db)

        acts = self.db.query(Activity).filter(Activity.group_id == group.id).all()
        # Logged: GROUP_CREATED, EXPENSE_CREATED, EXPENSE_UPDATED, EXPENSE_DELETED
        self.assertEqual(len(acts), 4)
        self.assertEqual(acts[2].activity_type, "EXPENSE_UPDATED")
        self.assertEqual(acts[2].message, "Purva updated the expense 'Fancy Dinner' to ₹1500")
        self.assertEqual(acts[3].activity_type, "EXPENSE_DELETED")
        self.assertEqual(acts[3].message, "Purva deleted the expense 'Fancy Dinner'")

    def test_settlement_creation_activity(self):
        """Should automatically log SETTLEMENT_CREATED activity when settlement is recorded"""
        # Set up group and members
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        # Create settlement: Rahul paid Purva ₹500
        settle_data = SettlementCreate(payer_id=2, receiver_id=1, amount=500.0)
        settlement_service.create_settlement(group.id, settle_data, self.user1, self.db)

        acts = self.db.query(Activity).filter(Activity.group_id == group.id).all()
        # GROUP_CREATED, MEMBER_ADDED, SETTLEMENT_CREATED
        self.assertEqual(len(acts), 3)
        self.assertEqual(acts[2].activity_type, "SETTLEMENT_CREATED")
        self.assertEqual(acts[2].message, "Rahul paid Purva ₹500")

    def test_get_group_activities_checks(self):
        """Should properly validate permissions and group existence on query"""
        # Verify 404 for non-existent group
        with self.assertRaises(HTTPException) as context:
            activity_service.get_group_activities(999, self.user1, self.db)
        self.assertEqual(context.exception.status_code, 404)

        # Verify 403 for non-member
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)

        # user4 is not in the group
        with self.assertRaises(HTTPException) as context:
            activity_service.get_group_activities(group.id, self.user4, self.db)
        self.assertEqual(context.exception.status_code, 403)

    def test_get_group_activities_pagination(self):
        """Should paginate activities correctly ordered by newest first"""
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)

        # Add 12 activities
        for i in range(12):
            activity_service.log_activity(
                self.db,
                group_id=group.id,
                user_id=1,
                activity_type="EXPENSE_CREATED",
                message=f"Purva added expense {i}"
            )

        # Total activities = 1 (GROUP_CREATED) + 12 (EXPENSE_CREATED) = 13
        # Page 1, limit 10
        res1 = activity_service.get_group_activities(group.id, self.user1, self.db, page=1, limit=10)
        self.assertEqual(len(res1), 10)
        # Verify ordering (newest first)
        self.assertEqual(res1[0]["message"], "Purva added expense 11")
        self.assertEqual(res1[9]["message"], "Purva added expense 2")

        # Page 2, limit 10
        res2 = activity_service.get_group_activities(group.id, self.user1, self.db, page=2, limit=10)
        self.assertEqual(len(res2), 3)
        self.assertEqual(res2[0]["message"], "Purva added expense 1")
        self.assertEqual(res2[1]["message"], "Purva added expense 0")
        self.assertEqual(res2[2]["message"], "Purva created group 'Goa Trip'")


if __name__ == "__main__":
    unittest.main()
