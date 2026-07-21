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
from app.models.notification import Notification

from app.services import group_service, expense_service, settlement_service, notification_service
from app.schemas.group import GroupCreate
from app.schemas.expense import ExpenseCreate, ExpenseUpdate
from app.schemas.settlement import SettlementCreate


class TestNotificationSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed test users
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

    def test_create_notification_directly(self):
        """Should directly write notification into database"""
        notif = notification_service.create_notification(
            self.db,
            user_id=1,
            title="Test Title",
            message="Test Message"
        )
        self.assertIsNotNone(notif.id)
        self.assertEqual(notif.user_id, 1)
        self.assertEqual(notif.title, "Test Title")
        self.assertEqual(notif.message, "Test Message")
        self.assertFalse(notif.is_read)

    def test_added_to_group_notification(self):
        """Should automatically generate notification when added to a group"""
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)

        # Purva (user1) adds Rahul (user2)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        # Rahul should have a notification
        notifs = self.db.query(Notification).filter(Notification.user_id == 2).all()
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].title, "Added to Group")
        self.assertEqual(notifs[0].message, "You have been added to the group 'Goa Trip' by Purva.")

    def test_expense_added_notification(self):
        """Should automatically notify other group members when an expense is added"""
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)
        group_service.add_member(group.id, "amit@example.com", self.user1, self.db)

        # Purva (user1) adds expense
        exp_data = ExpenseCreate(title="Dinner", amount=1200.0)
        expense_service.create_expense(group.id, exp_data, self.user1, self.db)

        # Rahul (user2) and Amit (user3) should have a notification, but not Purva
        purva_notifs = self.db.query(Notification).filter(Notification.user_id == 1).all()
        rahul_notifs = self.db.query(Notification).filter(Notification.user_id == 2).all()
        amit_notifs = self.db.query(Notification).filter(Notification.user_id == 3).all()

        self.assertEqual(len(purva_notifs), 0)
        # Rahul has "Added to Group" and "Expense Added"
        self.assertEqual(len(rahul_notifs), 2)
        # Verify expense added notif
        exp_notif = next(n for n in rahul_notifs if n.title == "Expense Added")
        self.assertEqual(exp_notif.message, "Purva added a new expense in Goa Trip.")

        self.assertEqual(len(amit_notifs), 2)

    def test_expense_updated_and_deleted_notifications(self):
        """Should notify other members on update and delete"""
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        exp_data = ExpenseCreate(title="Dinner", amount=1200.0)
        exp = expense_service.create_expense(group.id, exp_data, self.user1, self.db)

        # Update
        update_data = ExpenseUpdate(title="Fancy Dinner", amount=1500.0)
        expense_service.update_expense(exp.id, update_data, self.user1, self.db)

        # Delete
        expense_service.delete_expense(exp.id, self.user1, self.db)

        rahul_notifs = self.db.query(Notification).filter(Notification.user_id == 2).all()
        # Should have Added to Group, Expense Added, Expense Updated, Expense Deleted
        self.assertEqual(len(rahul_notifs), 4)

        up_notif = next(n for n in rahul_notifs if n.title == "Expense Updated")
        self.assertEqual(up_notif.message, "Purva updated the expense 'Fancy Dinner' in Goa Trip.")

        del_notif = next(n for n in rahul_notifs if n.title == "Expense Deleted")
        self.assertEqual(del_notif.message, "Purva deleted the expense 'Fancy Dinner' in Goa Trip.")

    def test_settlement_completed_notification(self):
        """Should notify receiver when a settlement is completed"""
        group_data = GroupCreate(name="Goa Trip")
        group = group_service.create_group(group_data, self.user1, self.db)
        group_service.add_member(group.id, "rahul@example.com", self.user1, self.db)

        # Purva records settlement that Rahul paid Purva 500
        settle_data = SettlementCreate(payer_id=2, receiver_id=1, amount=500.0)
        settlement_service.create_settlement(group.id, settle_data, self.user1, self.db)

        # Rahul (payer) should have a notification since Purva (receiver) was the active user
        rahul_notifs = self.db.query(Notification).filter(Notification.user_id == 2).all()
        # Added to Group, Settlement Completed
        self.assertEqual(len(rahul_notifs), 2)
        settle_notif = next(n for n in rahul_notifs if n.title == "Settlement Completed")
        self.assertEqual(settle_notif.message, "Your settlement of ₹500 to Purva has been recorded.")

    def test_get_user_notifications_pagination(self):
        """Should retrieve paginated notifications list ordered by newest first"""
        for i in range(12):
            notification_service.create_notification(self.db, user_id=1, title="Test", message=f"Message {i}")

        res1 = notification_service.get_user_notifications(self.db, self.user1, page=1, limit=10)
        self.assertEqual(len(res1), 10)
        self.assertEqual(res1[0].message, "Message 11")

        res2 = notification_service.get_user_notifications(self.db, self.user1, page=2, limit=10)
        self.assertEqual(len(res2), 2)
        self.assertEqual(res2[0].message, "Message 1")

    def test_mark_as_read_checks(self):
        """Should mark notification as read and validate permissions"""
        notif = notification_service.create_notification(self.db, user_id=1, title="Test", message="Msg")

        # Mark read successfully
        updated = notification_service.mark_as_read(self.db, self.user1, notif.id)
        self.assertTrue(updated.is_read)

        # 404 for non-existent notif
        with self.assertRaises(HTTPException) as context:
            notification_service.mark_as_read(self.db, self.user1, 999)
        self.assertEqual(context.exception.status_code, 404)

        # 403 for other user trying to mark as read
        notif2 = notification_service.create_notification(self.db, user_id=1, title="Test", message="Msg")
        with self.assertRaises(HTTPException) as context:
            notification_service.mark_as_read(self.db, self.user2, notif2.id)
        self.assertEqual(context.exception.status_code, 403)

    def test_mark_all_as_read(self):
        """Should mark all user's notifications as read"""
        notification_service.create_notification(self.db, user_id=1, title="T1", message="M1")
        notification_service.create_notification(self.db, user_id=1, title="T2", message="M2")
        notification_service.create_notification(self.db, user_id=2, title="T3", message="M3") # other user

        notification_service.mark_all_as_read(self.db, self.user1)

        user1_unread = self.db.query(Notification).filter(Notification.user_id == 1, Notification.is_read == False).count()
        user2_unread = self.db.query(Notification).filter(Notification.user_id == 2, Notification.is_read == False).count()

        self.assertEqual(user1_unread, 0)
        self.assertEqual(user2_unread, 1)

    def test_delete_notification_checks(self):
        """Should successfully delete a notification and check ownership"""
        notif = notification_service.create_notification(self.db, user_id=1, title="T1", message="M1")

        # 403 when user2 tries to delete
        with self.assertRaises(HTTPException) as context:
            notification_service.delete_notification(self.db, self.user2, notif.id)
        self.assertEqual(context.exception.status_code, 403)

        # Success when user1 deletes
        res = notification_service.delete_notification(self.db, self.user1, notif.id)
        self.assertEqual(res["message"], "Notification deleted successfully")
        self.assertIsNone(self.db.query(Notification).filter(Notification.id == notif.id).first())


if __name__ == "__main__":
    unittest.main()
