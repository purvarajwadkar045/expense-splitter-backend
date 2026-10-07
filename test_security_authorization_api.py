import os
import sys
import unittest
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.config import settings
from app.core.security import hash_password
from app.db.database import Base
from app.dependencies.db import get_db
from app.main import app
from app.models.budget import Budget
from app.models.expense_split import ExpenseSplit
from app.models.user import User


class TestSecurityAuthorizationAPI(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        db = self.SessionLocal()
        self.alice = User(
            username="alice",
            email="alice@example.com",
            password_hash=hash_password("alice-password"),
            is_verified=True,
        )
        self.bob = User(
            username="bob",
            email="bob@example.com",
            password_hash=hash_password("bob-password"),
            is_verified=True,
        )
        self.carol = User(
            username="carol",
            email="carol@example.com",
            password_hash=hash_password("carol-password"),
            is_verified=True,
        )
        db.add_all([self.alice, self.bob, self.carol])
        db.commit()
        self.alice_id, self.bob_id, self.carol_id = self.alice.id, self.bob.id, self.carol.id
        self.alice_email, self.carol_email = self.alice.email, self.carol.email
        self.carol_username = self.carol.username
        db.close()

        def override_get_db():
            request_db = self.SessionLocal()
            try:
                yield request_db
            finally:
                request_db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.alice_token = self._login("alice@example.com", "alice-password")
        self.bob_token = self._login("bob@example.com", "bob-password")
        self.carol_token = self._login("carol@example.com", "carol-password")
        self.alice_headers = {"Authorization": f"Bearer {self.alice_token}"}
        self.bob_headers = {"Authorization": f"Bearer {self.bob_token}"}
        self.carol_headers = {"Authorization": f"Bearer {self.carol_token}"}

    def tearDown(self):
        self.client.close()
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=self.engine)
        self.engine.dispose()

    def _login(self, email, password):
        response = self.client.post("/auth/login", json={"email": email, "password": password})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["access_token"]

    def _create_group_with_members(self):
        response = self.client.post(
            "/groups",
            headers=self.alice_headers,
            json={"name": "Alice private group", "description": "QA isolation fixture"},
        )
        self.assertEqual(response.status_code, 200, response.text)
        group_id = response.json()["id"]
        self.assertEqual(
            [group["id"] for group in self.client.get("/groups", headers=self.alice_headers).json()],
            [group_id],
        )
        response = self.client.post(
            f"/groups/{group_id}/members",
            headers=self.alice_headers,
            json={"email": self.carol_email},
        )
        self.assertEqual(response.status_code, 200, response.text)
        group = self.client.get(f"/groups/{group_id}", headers=self.alice_headers)
        self.assertEqual(group.status_code, 200, group.text)
        self.assertIn("carol", group.json()["members"])
        return group_id

    def _create_expense(self, group_id, paid_by=None):
        payer_id = paid_by or self.alice_id
        splits = [
            {"user_id": self.alice_id, "amount": 50},
            {"user_id": self.carol_id, "amount": 50},
        ]
        response = self.client.post(
            f"/groups/{group_id}/expenses",
            headers=self.alice_headers,
            json={
                "title": "QA private dinner",
                "amount": 100,
                "category": "Food",
                "paid_by": payer_id,
                "splits": splits,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        expense_id = response.json()["id"]
        fresh_expenses = self.client.get(
            f"/groups/{group_id}/expenses", headers=self.alice_headers
        )
        self.assertEqual([item["id"] for item in fresh_expenses.json()], [expense_id])
        return expense_id

    def _fresh_session(self):
        return self.SessionLocal()

    def test_protected_routes_reject_missing_invalid_and_expired_tokens(self):
        protected_requests = [
            ("GET", "/users/me"),
            ("PUT", "/users/me", {"username": "intruder"}),
            ("GET", "/notifications"),
            ("GET", "/dashboard"),
            ("GET", "/groups"),
            ("POST", "/groups", {"name": "Unauthenticated"}),
            ("GET", "/groups/1"),
            ("GET", "/groups/1/expenses"),
            ("POST", "/groups/1/expenses", {"title": "unauth", "amount": 1}),
            ("GET", "/groups/1/balances"),
            ("GET", "/groups/1/settlements"),
            ("POST", "/groups/1/settlements", {"payer_id": 1, "receiver_id": 2, "amount": 1}),
            ("GET", "/groups/1/activity"),
            ("GET", "/groups/1/simplify"),
            ("GET", "/analytics/budget"),
            ("GET", "/analytics/summary"),
            ("GET", "/analytics/categories"),
            ("GET", "/analytics/monthly"),
            ("GET", "/analytics/members"),
            ("GET", "/analytics/groups"),
            ("GET", "/analytics/insights"),
            ("GET", "/analytics/heatmap"),
            ("GET", "/analytics/top-expenses"),
            ("GET", "/analytics/export"),
            ("PUT", "/analytics/budget", {"month": "2026-10", "amount": 10}),
            ("POST", "/auth/logout"),
        ]
        expired_token = jwt.encode(
            {"sub": "alice@example.com", "exp": datetime.utcnow() - timedelta(minutes=1)},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        wrong_signature_token = jwt.encode(
            {"sub": "alice@example.com", "exp": datetime.utcnow() + timedelta(minutes=5)},
            "incorrect-signing-secret",
            algorithm=settings.ALGORITHM,
        )

        for request_data in protected_requests:
            method, path, *payload = request_data
            kwargs = {"json": payload[0]} if payload else {}
            with self.subTest(method=method, path=path, token="missing"):
                self.assertEqual(self.client.request(method, path, **kwargs).status_code, 401)
            with self.subTest(method=method, path=path, token="invalid"):
                response = self.client.request(
                    method,
                    path,
                    headers={"Authorization": "Bearer invalid.token"},
                    **kwargs,
                )
                self.assertEqual(response.status_code, 401)
            with self.subTest(method=method, path=path, token="expired"):
                response = self.client.request(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {expired_token}"},
                    **kwargs,
                )
                self.assertEqual(response.status_code, 401)
            with self.subTest(method=method, path=path, token="wrong-signature"):
                response = self.client.request(
                    method,
                    path,
                    headers={"Authorization": f"Bearer {wrong_signature_token}"},
                    **kwargs,
                )
                self.assertEqual(response.status_code, 401)

    def test_logout_revokes_existing_tokens_and_fresh_login_succeeds(self):
        profile = self.client.get("/users/me", headers=self.alice_headers)
        self.assertEqual(profile.status_code, 200, profile.text)

        logout = self.client.post("/auth/logout", headers=self.alice_headers)
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertEqual(self.client.get("/users/me", headers=self.alice_headers).status_code, 401)

        new_token = self._login("alice@example.com", "alice-password")
        response = self.client.get("/users/me", headers={"Authorization": f"Bearer {new_token}"})
        self.assertEqual(response.status_code, 200, response.text)

    def test_user_isolation_and_authorized_group_data_persistence(self):
        group_id = self._create_group_with_members()
        expense_id = self._create_expense(group_id)

        response = self.client.put(
            "/analytics/budget",
            headers=self.alice_headers,
            json={"month": "2026-10", "amount": 500},
        )
        self.assertEqual(response.status_code, 200, response.text)
        stored_budget = self.client.get("/analytics/budget?month=2026-10", headers=self.alice_headers)
        self.assertEqual(stored_budget.status_code, 200, stored_budget.text)
        self.assertEqual(stored_budget.json()["budget"], 500)
        response = self.client.post(
            f"/groups/{group_id}/settlements",
            headers=self.alice_headers,
            json={"payer_id": self.carol_id, "receiver_id": self.alice_id, "amount": 10},
        )
        self.assertEqual(response.status_code, 200, response.text)
        settlement_id = response.json()["id"]
        for amount in (0, -1):
            invalid_settlement = self.client.post(
                f"/groups/{group_id}/settlements",
                headers=self.alice_headers,
                json={"payer_id": self.carol_id, "receiver_id": self.alice_id, "amount": amount},
            )
            self.assertEqual(invalid_settlement.status_code, 400, invalid_settlement.text)
        stored_settlements = self.client.get(
            f"/groups/{group_id}/settlements", headers=self.alice_headers
        )
        self.assertEqual([item["id"] for item in stored_settlements.json()], [settlement_id])

        self.assertEqual(self.client.get("/groups", headers=self.bob_headers).json(), [])
        for path in (
            f"/groups/{group_id}",
            f"/groups/{group_id}/expenses",
            f"/groups/{group_id}/balances",
            f"/groups/{group_id}/settlements",
        ):
            response = self.client.get(path, headers=self.bob_headers)
            self.assertIn(response.status_code, (403, 404), (path, response.text))

        budget = self.client.get("/analytics/budget?month=2026-10", headers=self.bob_headers)
        self.assertEqual(budget.status_code, 200, budget.text)
        self.assertIsNone(budget.json()["budget"])
        self.assertEqual(budget.json()["spent"], 0)

        for path in (
            f"/analytics/summary?group_id={group_id}",
            f"/analytics/categories?group_id={group_id}",
            f"/analytics/monthly?group_id={group_id}",
            f"/analytics/members?group_id={group_id}",
            f"/analytics/groups?group_id={group_id}",
            f"/analytics/insights?group_id={group_id}",
            f"/analytics/heatmap?group_id={group_id}",
            f"/analytics/top-expenses?group_id={group_id}",
            f"/analytics/export?group_id={group_id}",
        ):
            response = self.client.get(path, headers=self.bob_headers)
            self.assertEqual(response.status_code, 403, (path, response.text))
        for path in (
            "/analytics/summary",
            "/analytics/categories",
            "/analytics/monthly",
            "/analytics/members",
            "/analytics/groups",
            "/analytics/insights",
            "/analytics/heatmap",
            "/analytics/top-expenses",
        ):
            response = self.client.get(path, headers=self.bob_headers)
            self.assertEqual(response.status_code, 200, (path, response.text))
            self.assertNotIn("Alice private group", response.text)
            self.assertNotIn("QA private dinner", response.text)
        export = self.client.get("/analytics/export", headers=self.bob_headers)
        self.assertEqual(export.status_code, 200, export.text)
        self.assertNotIn("QA private dinner", export.text)

        self.assertEqual(self.client.put(
            f"/expenses/{expense_id}",
            headers=self.bob_headers,
            json={"title": "stolen update"},
        ).status_code, 403)
        self.assertEqual(self.client.delete(
            f"/expenses/{expense_id}", headers=self.bob_headers
        ).status_code, 403)
        self.assertEqual(self.client.post(
            f"/groups/{group_id}/settlements",
            headers=self.bob_headers,
            json={"payer_id": self.bob_id, "receiver_id": self.alice_id, "amount": 10},
        ).status_code, 403)
        self.assertEqual(self.client.post(
            f"/groups/{group_id}/settlements",
            headers=self.alice_headers,
            json={"payer_id": self.alice_id, "receiver_id": self.bob_id, "amount": 10},
        ).status_code, 403)
        self.assertEqual(self.client.put(
            f"/expenses/{expense_id}",
            headers=self.carol_headers,
            json={"title": "non-payer update"},
        ).status_code, 403)
        self.assertEqual(self.client.delete(
            f"/expenses/{expense_id}", headers=self.carol_headers
        ).status_code, 403)
        for method, path, kwargs in (
            ("PUT", f"/groups/{group_id}", {"json": {"name": "not the owner"}}),
            ("DELETE", f"/groups/{group_id}", {}),
            ("POST", f"/groups/{group_id}/members", {"json": {"email": "bob@example.com"}}),
        ):
            response = self.client.request(method, path, headers=self.carol_headers, **kwargs)
            self.assertEqual(response.status_code, 403, response.text)

        bob_budget_update = self.client.put(
            "/analytics/budget",
            headers=self.bob_headers,
            json={"month": "2026-10", "amount": 900},
        )
        self.assertEqual(bob_budget_update.status_code, 200, bob_budget_update.text)
        alice_budget = self.client.get("/analytics/budget?month=2026-10", headers=self.alice_headers)
        bob_budget = self.client.get("/analytics/budget?month=2026-10", headers=self.bob_headers)
        self.assertEqual(alice_budget.json()["budget"], 500)
        self.assertEqual(bob_budget.json()["budget"], 900)

        fresh_db = self._fresh_session()
        try:
            self.assertEqual(fresh_db.query(ExpenseSplit).filter_by(expense_id=expense_id).count(), 2)
            self.assertEqual(fresh_db.query(Budget).filter_by(user_id=self.alice_id).one().amount, 500)
        finally:
            fresh_db.close()

        alice_groups = self.client.get("/groups", headers=self.alice_headers).json()
        self.assertEqual([group["id"] for group in alice_groups], [group_id])
        expenses = self.client.get(f"/groups/{group_id}/expenses", headers=self.alice_headers)
        self.assertEqual(expenses.status_code, 200, expenses.text)
        self.assertEqual([item["id"] for item in expenses.json()], [expense_id])
        balances = self.client.get(f"/groups/{group_id}/balances", headers=self.alice_headers)
        self.assertEqual(balances.status_code, 200, balances.text)
        self.assertTrue(balances.json())
        settlements = self.client.get(f"/groups/{group_id}/settlements", headers=self.alice_headers)
        self.assertEqual(settlements.status_code, 200, settlements.text)
        self.assertEqual([item["id"] for item in settlements.json()], [settlement_id])

        update = self.client.put(
            f"/expenses/{expense_id}",
            headers=self.alice_headers,
            json={"title": "QA updated dinner", "amount": 120},
        )
        self.assertEqual(update.status_code, 200, update.text)
        refreshed = self.client.get(f"/groups/{group_id}/expenses", headers=self.alice_headers)
        self.assertEqual(refreshed.json()[0]["title"], "QA updated dinner")
        self.assertEqual(refreshed.json()[0]["amount"], 120)
        balances_after_update = self.client.get(
            f"/groups/{group_id}/balances", headers=self.alice_headers
        ).json()

        relogin_token = self._login("alice@example.com", "alice-password")
        relogin_headers = {"Authorization": f"Bearer {relogin_token}"}
        self.assertEqual(self.client.get("/groups", headers=relogin_headers).json()[0]["id"], group_id)
        self.assertEqual(
            self.client.get(f"/groups/{group_id}/expenses", headers=relogin_headers).json()[0]["title"],
            "QA updated dinner",
        )
        self.assertEqual(
            [item["id"] for item in self.client.get(
                f"/groups/{group_id}/settlements", headers=relogin_headers
            ).json()],
            [settlement_id],
        )
        self.assertEqual(
            self.client.get("/analytics/budget?month=2026-10", headers=relogin_headers).json()["budget"],
            500,
        )
        self.assertEqual(
            self.client.get(f"/groups/{group_id}/balances", headers=relogin_headers).json(),
            balances_after_update,
        )
        fresh_db = self._fresh_session()
        try:
            self.assertEqual(fresh_db.query(ExpenseSplit).filter_by(expense_id=expense_id).count(), 2)
            self.assertEqual(fresh_db.query(Budget).filter_by(user_id=self.alice_id).one().amount, 500)
        finally:
            fresh_db.close()

        deleted = self.client.delete(f"/expenses/{expense_id}", headers=relogin_headers)
        self.assertEqual(deleted.status_code, 200, deleted.text)
        self.assertEqual(self.client.get(
            f"/groups/{group_id}/expenses", headers=relogin_headers
        ).json(), [])
        fresh_db = self._fresh_session()
        try:
            self.assertIsNone(fresh_db.query(ExpenseSplit).filter_by(expense_id=expense_id).first())
        finally:
            fresh_db.close()

    def test_removed_group_member_cannot_mutate_old_expense(self):
        group_id = self._create_group_with_members()
        expense_id = self._create_expense(group_id, paid_by=self.carol_id)

        removed = self.client.request(
            "DELETE",
            f"/groups/{group_id}/members",
            headers=self.alice_headers,
            json={"username": self.carol_username},
        )
        self.assertEqual(removed.status_code, 200, removed.text)
        group = self.client.get(f"/groups/{group_id}", headers=self.alice_headers)
        self.assertNotIn("carol", group.json()["members"])

        for method, path, kwargs in (
            ("PUT", f"/expenses/{expense_id}", {"json": {"title": "unauthorized"}}),
            ("DELETE", f"/expenses/{expense_id}", {}),
        ):
            response = self.client.request(method, path, headers=self.carol_headers, **kwargs)
            self.assertEqual(response.status_code, 403, response.text)

        fresh_db = self._fresh_session()
        try:
            self.assertEqual(fresh_db.query(ExpenseSplit).filter_by(expense_id=expense_id).count(), 2)
        finally:
            fresh_db.close()

    def test_invalid_expense_budget_and_filter_requests_are_rejected(self):
        group_id = self._create_group_with_members()
        base_payload = {"title": "Invalid amount", "category": "Food"}
        for amount in (-1, 0):
            payload = {**base_payload, "amount": amount}
            response = self.client.post(
                f"/groups/{group_id}/expenses", headers=self.alice_headers, json=payload
            )
            self.assertEqual(response.status_code, 400, response.text)

        response = self.client.post(
            f"/groups/{group_id}/expenses",
            headers=self.alice_headers,
            json={"title": "Bad category", "amount": 1, "category": "Crypto"},
        )
        self.assertEqual(response.status_code, 422, response.text)

        for payload in (
            {"title": "Bad payer", "amount": 1, "paid_by": self.bob_id},
            {"title": "Bad participant", "amount": 1, "participants": [self.bob_id]},
            {
                "title": "Bad split total",
                "amount": 100,
                "splits": [{"user_id": self.alice_id, "amount": 99}],
            },
            {
                "title": "Negative split",
                "amount": 100,
                "splits": [{"user_id": self.alice_id, "amount": -1}],
            },
            {"title": "Missing split amount", "amount": 100, "splits": [{"user_id": self.alice_id}]},
            {"amount": 1},
        ):
            response = self.client.post(
                f"/groups/{group_id}/expenses", headers=self.alice_headers, json=payload
            )
            self.assertIn(response.status_code, (400, 422), response.text)

        self.assertEqual(self.client.post(
            "/groups/99999/expenses",
            headers=self.alice_headers,
            json={"title": "Missing group", "amount": 10},
        ).status_code, 404)

        for payload in (
            {"month": "2026-10", "amount": 0},
            {"month": "2026-13", "amount": 100},
            {"month": "2026-1", "amount": 100},
            {"month": "October 2026", "amount": 100},
        ):
            response = self.client.put("/analytics/budget", headers=self.alice_headers, json=payload)
            self.assertEqual(response.status_code, 422, response.text)

        response = self.client.get(
            f"/groups/{group_id}/expenses?min_amount=100&max_amount=10",
            headers=self.alice_headers,
        )
        self.assertEqual(response.status_code, 400, response.text)
        for amount_filter in ("min_amount=NaN", "max_amount=Infinity"):
            response = self.client.get(
                f"/groups/{group_id}/expenses?{amount_filter}",
                headers=self.alice_headers,
            )
            self.assertEqual(response.status_code, 400, response.text)
        response = self.client.get(
            f"/groups/{group_id}/expenses?start_date=not-a-date",
            headers=self.alice_headers,
        )
        self.assertEqual(response.status_code, 422, response.text)
        invalid_filter_requests = (
            f"/groups/{group_id}/expenses?date_range=not-a-range",
            "/analytics/summary?date_range=not-a-range",
            "/analytics/monthly?month=2026-1",
            "/analytics/summary?min_amount=NaN",
            "/analytics/summary?max_amount=Infinity",
        )
        for path in invalid_filter_requests:
            response = self.client.get(path, headers=self.alice_headers)
            self.assertEqual(response.status_code, 400, (path, response.text))
        response = self.client.post(
            f"/groups/{group_id}/expenses",
            content='{"title":"Non-finite amount","amount":Infinity}',
            headers={**self.alice_headers, "Content-Type": "application/json"},
        )
        self.assertIn(response.status_code, (400, 422), response.text)

        existing_id = self._create_expense(group_id)
        failed_update = self.client.put(
            f"/expenses/{existing_id}",
            headers=self.alice_headers,
            json={"amount": 150, "splits": [{"user_id": self.alice_id, "amount": 10}]},
        )
        self.assertEqual(failed_update.status_code, 400, failed_update.text)
        fresh_expense = self.client.get(
            f"/groups/{group_id}/expenses", headers=self.alice_headers
        ).json()[0]
        self.assertEqual(fresh_expense["amount"], 100)
        fresh_db = self._fresh_session()
        try:
            self.assertEqual(fresh_db.query(ExpenseSplit).filter_by(expense_id=existing_id).count(), 2)
        finally:
            fresh_db.close()


if __name__ == "__main__":
    unittest.main()