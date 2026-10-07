import csv
import io
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
from app.services import analytics_service


class TestAnalyticsExport(unittest.TestCase):
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
            Group(id=2, name="Private", created_by=2),
            GroupMember(id=1, group_id=1, user_id=1),
            GroupMember(id=2, group_id=1, user_id=2),
            GroupMember(id=3, group_id=2, user_id=2),
            Expense(id=1, title='Hotel, "Goa"', amount=2200, category="Travel", group_id=1, paid_by=1, created_at=datetime(2026, 9, 10)),
            Expense(id=2, title="Dinner", amount=600, category="Food", group_id=1, paid_by=2, created_at=datetime(2026, 9, 11)),
            Expense(id=3, title="Private", amount=9000, category="Food", group_id=2, paid_by=2, created_at=datetime(2026, 9, 11)),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        for table in reversed(Base.metadata.sorted_tables):
            self.db.execute(table.delete())
        self.db.commit()

    def test_filtered_expense_csv_is_escaped_and_scoped(self):
        content = analytics_service.export_csv(
            self.alice,
            self.db,
            "expenses",
            month="2026-09",
            category="Travel",
        )
        rows = list(csv.reader(io.StringIO(content)))

        self.assertEqual(rows[0], ["Expense ID", "Description", "Amount", "Category", "Date", "Payer", "Group", "Created At"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][1], 'Hotel, "Goa"')
        self.assertNotIn("Private", content)

    def test_empty_expense_csv_keeps_headers(self):
        content = analytics_service.export_csv(self.alice, self.db, "expenses", month="2025-09")
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "Expense ID")

    def test_summary_category_and_monthly_reports(self):
        summary = analytics_service.export_csv(self.alice, self.db, "summary", month="2026-09")
        category = analytics_service.export_csv(self.alice, self.db, "category", month="2026-09")
        monthly = analytics_service.export_csv(self.alice, self.db, "monthly", date_range="this-year")

        self.assertIn("Total Expenses,2800.0", summary)
        self.assertIn("Travel,2200.0", category)
        self.assertIn("2026-09", monthly)

    def test_unsupported_report_is_rejected(self):
        with self.assertRaises(Exception):
            analytics_service.export_csv(self.alice, self.db, "pdf")


if __name__ == "__main__":
    unittest.main()