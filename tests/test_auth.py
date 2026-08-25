import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import unittest
from fastapi.testclient import TestClient

from backend.main import app
from backend import database as db
from backend import auth

class TestAuthAndRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        db.init_db()
        cls.client = TestClient(app)

    def test_01_default_users_seeded(self):
        users = auth.list_users()
        usernames = [u["username"] for u in users]
        self.assertIn("admin", usernames)
        self.assertIn("employee", usernames)

    def test_02_password_hashing(self):
        pwd = "testpassword123"
        h = auth.hash_password(pwd)
        self.assertTrue(h.startswith(("$2a$", "$2b$", "$2y$")))
        self.assertTrue(auth.verify_password(pwd, h))
        self.assertFalse(auth.verify_password("wrongpassword", h))

    def test_03_token_generation_and_verification(self):
        token = auth.create_token(99, "testuser", "employee")
        payload = auth.verify_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["user_id"], 99)
        self.assertEqual(payload["username"], "testuser")
        self.assertEqual(payload["role"], "employee")

    def test_04_login_endpoint_success(self):
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertEqual(data["user"]["role"], "admin")

        res_alias = self.client.post("/api/login", json={"username": "employee", "password": "emp123"})
        self.assertEqual(res_alias.status_code, 200)
        data_alias = res_alias.json()
        self.assertIn("token", data_alias)
        self.assertEqual(data_alias["user"]["role"], "employee")

    def test_05_login_endpoint_invalid(self):
        res = self.client.post("/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)

    def test_06_me_endpoint(self):
        login_res = self.client.post("/api/auth/login", json={"username": "employee", "password": "emp123"})
        self.assertEqual(login_res.status_code, 200)
        token = login_res.json()["token"]
        
        me_res = self.client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res.status_code, 200)
        data = me_res.json()
        self.assertTrue(data["authenticated"])
        self.assertEqual(data["user"]["username"], "employee")
        self.assertEqual(data["user"]["role"], "employee")

        me_alias = self.client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_alias.status_code, 200)
        data_alias = me_alias.json()
        self.assertTrue(data_alias["authenticated"])

if __name__ == "__main__":
    unittest.main()
