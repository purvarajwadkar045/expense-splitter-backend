import sys
import os
import unittest
from datetime import datetime
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
from app.services import dashboard_service

class TestDashboardService(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create an in-memory SQLite database for testing
        cls.engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        Base.metadata.create_all(bind=cls.engine)

    def setUp(self):
        self.db = self.SessionLocal()
        # Seed basic users
        self.user1 = User(id=1, username="alice", email="alice@example.com", password_hash="hash")
        self.user2 = User(id=2, username="bob", email="bob@example.com", password_hash="hash")
        self.user3 = User(id=3, username="charlie", email="charlie@example.com", password_hash="hash")
        self.db.add_all([self.user1, self.user2, self.user3])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        meta = Base.metadata
        for table in reversed(meta.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_dashboard_no_groups(self):
        """Should return zero values when the user is in no groups"""
        stats = dashboard_service.get_dashboard_data(self.user1, self.db)
        self.assertEqual(stats["user_id"], 1)
        self.assertEqual(stats["username"], "alice")
        self.assertEqual(stats["total_groups"], 0)
        self.assertEqual(stats["total_expenses_paid"], 0.0)
        self.assertEqual(stats["total_you_owe"], 0.0)
        self.assertEqual(stats["total_owed_to_you"], 0.0)
        self.assertEqual(stats["net_balance"], 0.0)

    def test_dashboard_with_groups_no_expenses(self):
        """Should return zero/correct values when user is in groups but there are no expenses/settlements"""
        group = Group(id=1, name="Trip", created_by=1)
        member1 = GroupMember(id=1, group_id=1, user_id=1)
        self.db.add_all([group, member1])
        self.db.commit()

        stats = dashboard_service.get_dashboard_data(self.user1, self.db)
        self.assertEqual(stats["total_groups"], 1)
        self.assertEqual(stats["total_expenses_paid"], 0.0)
        self.assertEqual(stats["total_you_owe"], 0.0)
        self.assertEqual(stats["total_owed_to_you"], 0.0)
        self.assertEqual(stats["net_balance"], 0.0)

    def test_dashboard_equal_splits(self):
        """Should correctly compute dashboard stats under equal split fallback"""
        # Alice and Bob in Group 1
        group = Group(id=1, name="Flat", created_by=1)
        member1 = GroupMember(id=1, group_id=1, user_id=1)
        member2 = GroupMember(id=2, group_id=1, user_id=2)
        
        # Expense paid by Alice (100.0, equal split fallback, so Alice paid 100, owes 50; Bob paid 0, owes 50)
        exp = Expense(id=1, title="Internet", amount=100.0, group_id=1, paid_by=1)
        
        self.db.add_all([group, member1, member2, exp])
        self.db.commit()

        stats1 = dashboard_service.get_dashboard_data(self.user1, self.db)
        self.assertEqual(stats1["total_groups"], 1)
        self.assertEqual(stats1["total_expenses_paid"], 100.0)
        self.assertEqual(stats1["total_you_owe"], 0.0)
        self.assertEqual(stats1["total_owed_to_you"], 50.0)
        self.assertEqual(stats1["net_balance"], 50.0)

        stats2 = dashboard_service.get_dashboard_data(self.user2, self.db)
        self.assertEqual(stats2["total_groups"], 1)
        self.assertEqual(stats2["total_expenses_paid"], 0.0)
        self.assertEqual(stats2["total_you_owe"], 50.0)
        self.assertEqual(stats2["total_owed_to_you"], 0.0)
        self.assertEqual(stats2["net_balance"], -50.0)

    def test_dashboard_custom_splits(self):
        """Should correctly compute dashboard stats when custom splits exist"""
        # Alice, Bob, Charlie in Group 1
        group = Group(id=1, name="Dinner", created_by=1)
        member1 = GroupMember(id=1, group_id=1, user_id=1)
        member2 = GroupMember(id=2, group_id=1, user_id=2)
        member3 = GroupMember(id=3, group_id=1, user_id=3)

        # Alice paid $90
        exp = Expense(id=1, title="Food", amount=90.0, group_id=1, paid_by=1)
        # Custom splits: Alice owes $20, Bob owes $30, Charlie owes $40
        split1 = ExpenseSplit(id=1, expense_id=1, user_id=1, amount=20.0)
        split2 = ExpenseSplit(id=2, expense_id=1, user_id=2, amount=30.0)
        split3 = ExpenseSplit(id=3, expense_id=1, user_id=3, amount=40.0)

        self.db.add_all([group, member1, member2, member3, exp, split1, split2, split3])
        self.db.commit()

        # Alice paid 90, owes 20 -> balance +70
        stats1 = dashboard_service.get_dashboard_data(self.user1, self.db)
        self.assertEqual(stats1["total_expenses_paid"], 90.0)
        self.assertEqual(stats1["total_you_owe"], 0.0)
        self.assertEqual(stats1["total_owed_to_you"], 70.0)
        self.assertEqual(stats1["net_balance"], 70.0)

        # Bob paid 0, owes 30 -> balance -30
        stats2 = dashboard_service.get_dashboard_data(self.user2, self.db)
        self.assertEqual(stats2["total_expenses_paid"], 0.0)
        self.assertEqual(stats2["total_you_owe"], 30.0)
        self.assertEqual(stats2["total_owed_to_you"], 0.0)
        self.assertEqual(stats2["net_balance"], -30.0)

    def test_dashboard_with_settlements(self):
        """Should correctly offset balances after settlements are recorded"""
        # Alice and Bob in Group 1
        group = Group(id=1, name="Trip", created_by=1)
        member1 = GroupMember(id=1, group_id=1, user_id=1)
        member2 = GroupMember(id=2, group_id=1, user_id=2)
        
        # Alice paid 100.0, split equally -> Alice net +50, Bob net -50
        exp = Expense(id=1, title="Cab", amount=100.0, group_id=1, paid_by=1)
        
        # Bob pays Alice 30.0 as settlement -> Bob paid 30, Alice owes 30.
        # Alice: group_paid = 100, group_owes = 50 + 30 = 80 -> Net = +20.
        # Bob: group_paid = 30, group_owes = 50 -> Net = -20.
        settlement = Settlement(id=1, group_id=1, payer_id=2, receiver_id=1, amount=30.0)

        self.db.add_all([group, member1, member2, exp, settlement])
        self.db.commit()

        stats1 = dashboard_service.get_dashboard_data(self.user1, self.db)
        self.assertEqual(stats1["total_expenses_paid"], 100.0)
        self.assertEqual(stats1["total_you_owe"], 0.0)
        self.assertEqual(stats1["total_owed_to_you"], 20.0)
        self.assertEqual(stats1["net_balance"], 20.0)

        stats2 = dashboard_service.get_dashboard_data(self.user2, self.db)
        self.assertEqual(stats2["total_expenses_paid"], 0.0)
        self.assertEqual(stats2["total_you_owe"], 20.0)
        self.assertEqual(stats2["total_owed_to_you"], 0.0)
        self.assertEqual(stats2["net_balance"], -20.0)

if __name__ == "__main__":
    unittest.main()
