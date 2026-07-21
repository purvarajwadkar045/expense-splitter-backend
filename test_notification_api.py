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
from app.models.activity import Activity
from app.models.notification import Notification
from app.routes.notification_routes import (
    get_notifications,
    read_all_notifications,
    read_notification,
    delete_notification
)

class TestNotificationAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create in-memory SQLite database
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        
        # Create users
        self.user1 = User(id=1, username="Purva", email="purva@example.com", password_hash="hash")
        self.user2 = User(id=2, username="Rahul", email="rahul@example.com", password_hash="hash")
        self.db.add_all([self.user1, self.user2])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_get_notifications_empty(self):
        res = get_notifications(page=1, limit=10, db=self.db, current_user=self.user1)
        self.assertEqual(res, [])

    def test_get_notifications_with_data_and_pagination(self):
        # Add notifications for user1
        n1 = Notification(id=1, user_id=1, title="Title 1", message="Msg 1")
        n2 = Notification(id=2, user_id=1, title="Title 2", message="Msg 2")
        n3 = Notification(id=3, user_id=2, title="Title 3", message="Msg 3")  # user2's notif
        self.db.add_all([n1, n2, n3])
        self.db.commit()

        # Get for user1
        data = get_notifications(page=1, limit=10, db=self.db, current_user=self.user1)
        self.assertEqual(len(data), 2)
        # Should be ordered by newest first (descending ID/created_at)
        self.assertEqual(data[0].id, 2)
        self.assertEqual(data[1].id, 1)

        # Pagination test
        data_pag = get_notifications(page=1, limit=1, db=self.db, current_user=self.user1)
        self.assertEqual(len(data_pag), 1)
        self.assertEqual(data_pag[0].id, 2)

    def test_mark_as_read(self):
        n1 = Notification(id=1, user_id=1, title="Title 1", message="Msg 1", is_read=False)
        self.db.add(n1)
        self.db.commit()

        # Mark read by owner
        updated = read_notification(notification_id=1, db=self.db, current_user=self.user1)
        self.assertTrue(updated.is_read)

        # Try to mark read by non-owner
        with self.assertRaises(HTTPException) as context:
            read_notification(notification_id=1, db=self.db, current_user=self.user2)
        self.assertEqual(context.exception.status_code, 403)

    def test_mark_all_read(self):
        n1 = Notification(id=1, user_id=1, title="Title 1", message="Msg 1", is_read=False)
        n2 = Notification(id=2, user_id=1, title="Title 2", message="Msg 2", is_read=False)
        n3 = Notification(id=3, user_id=2, title="Title 3", message="Msg 3", is_read=False)
        self.db.add_all([n1, n2, n3])
        self.db.commit()

        res = read_all_notifications(db=self.db, current_user=self.user1)
        self.assertEqual(res, {"message": "All notifications marked as read"})

        # Check DB
        self.db.refresh(n1)
        self.db.refresh(n2)
        self.db.refresh(n3)
        self.assertTrue(n1.is_read)
        self.assertTrue(n2.is_read)
        self.assertFalse(n3.is_read)

    def test_delete_notification(self):
        n1 = Notification(id=1, user_id=1, title="Title 1", message="Msg 1")
        self.db.add(n1)
        self.db.commit()

        # Delete by non-owner
        with self.assertRaises(HTTPException) as context:
            delete_notification(notification_id=1, db=self.db, current_user=self.user2)
        self.assertEqual(context.exception.status_code, 403)

        # Delete by owner
        res = delete_notification(notification_id=1, db=self.db, current_user=self.user1)
        self.assertEqual(res, {"message": "Notification deleted successfully"})

        # Verify not found
        self.assertIsNone(self.db.query(Notification).filter(Notification.id == 1).first())

if __name__ == "__main__":
    unittest.main()
