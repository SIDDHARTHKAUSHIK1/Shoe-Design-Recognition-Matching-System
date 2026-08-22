import requests
import json
import time

BASE_URL = "http://localhost:8000"

def run_baseline():
    print("==================================================")
    print("      SHOEMATCH AI SECURITY AUDIT BASELINE       ")
    print("==================================================")

    # 1. Login with Default Accounts
    print("\n--- 1. Testing Default Logins & must_change_password ---")
    admin_login = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "admin123"})
    print(f"Admin Login Status: {admin_login.status_code}")
    admin_token = None
    if admin_login.status_code == 200:
        admin_data = admin_login.json()
        admin_token = admin_data.get("token")
        user = admin_data.get("user", {})
        print(f"  User: {user.get('username')}, Role: {user.get('role')}, MustChangePwd: {user.get('must_change_password')}")
        
        # Test if must_change_password=1 user can access protected endpoints
        me_res = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"  GET /api/auth/me (with MustChangePwd=1): {me_res.status_code}")
        cat_res = requests.get(f"{BASE_URL}/api/designs", headers={"Authorization": f"Bearer {admin_token}"})
        print(f"  GET /api/designs (with MustChangePwd=1): {cat_res.status_code}")

    emp_login = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "employee", "password": "emp123"})
    print(f"Employee Login Status: {emp_login.status_code}")
    emp_token = emp_login.json().get("token") if emp_login.status_code == 200 else None

    # 2. Role-Based Access Control (RBAC)
    print("\n--- 2. Testing Employee Role on Admin-Only Routes ---")
    admin_routes = [
        ("GET", "/api/admin/users", None),
        ("POST", "/api/admin/users", {"username": "hacker", "password": "pwd", "role": "admin", "full_name": "Hack"}),
        ("DELETE", "/api/designs/SHOE-001", None),
        ("PUT", "/api/designs/SHOE-001", {"name": "Hacked Name"}),
        ("PUT", "/api/admin/designs/SHOE-001/status", {"is_active": 0}),
        ("POST", "/api/locations/slots/1/assign", {"design_id": "SHOE-001"}),
        ("POST", "/api/locations/shoe-matches", {"name": "Test Zone"}),
        ("POST", "/api/bulk-import/upload", None)
    ]

    for method, path, body in admin_routes:
        headers = {"Authorization": f"Bearer {emp_token}"} if emp_token else {}
        if method == "GET":
            res = requests.get(f"{BASE_URL}{path}", headers=headers)
        elif method == "POST":
            res = requests.post(f"{BASE_URL}{path}", json=body, headers=headers)
        elif method == "PUT":
            res = requests.put(f"{BASE_URL}{path}", json=body, headers=headers)
        elif method == "DELETE":
            res = requests.delete(f"{BASE_URL}{path}", headers=headers)
        
        status = res.status_code
        verdict = "PASS (403)" if status == 403 else f"FAIL ({status})"
        print(f"  [{method}] {path} -> Status: {status} ({verdict})")

    # 3. Unauthenticated Access Control on Data Mutation Routes
    print("\n--- 3. Testing Unauthenticated Access on Data Mutation Routes ---")
    unauth_routes = [
        ("DELETE", "/api/designs/SHOE-001"),
        ("PUT", "/api/designs/SHOE-001"),
        ("POST", "/api/locations/slots/1/assign")
    ]
    for method, path in unauth_routes:
        if method == "DELETE":
            res = requests.delete(f"{BASE_URL}{path}")
        elif method == "PUT":
            res = requests.put(f"{BASE_URL}{path}", json={"name": "No Auth"})
        elif method == "POST":
            res = requests.post(f"{BASE_URL}{path}", json={"design_id": "SHOE-001"})
        print(f"  [{method}] {path} (No Auth) -> Status: {res.status_code}")

    # 4. Malicious Image Upload / Magic Byte Validation
    print("\n--- 4. Testing Fake Image Upload (PHP Payload Disguised as .jpg) ---")
    fake_php = ("shell.jpg", b"<?php system($_GET['cmd']); ?>", "image/jpeg")
    match_res = requests.post(f"{BASE_URL}/api/match", files={"file": fake_php})
    print(f"  POST /api/match with PHP code disguised as JPG -> Status: {match_res.status_code}")
    if match_res.status_code == 200:
        print("  WARNING: Server executed matching pipeline on PHP payload!")

    # 5. Storage Access Control / Path Traversal
    print("\n--- 5. Testing Path Traversal on Static File Serving ---")
    traversal_paths = [
        "/catalog_images/../../backend/config.py",
        "/uploads/../../backend/auth.py",
        "/static/../../storage/catalog.db"
    ]
    for path in traversal_paths:
        res = requests.get(f"{BASE_URL}{path}")
        print(f"  GET {path} -> Status: {res.status_code}")

    # 6. Rate Limiting Throttling
    print("\n--- 6. Testing Rate Limiting (20 Rapid Failed Logins) ---")
    status_codes = []
    for _ in range(20):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "wrongpassword"})
        status_codes.append(r.status_code)
    has_429 = 429 in status_codes
    print(f"  Received Status Codes: {set(status_codes)}")
    print(f"  Rate Limiting Active: {'YES (PASS)' if has_429 else 'NO (FAIL)'}")

if __name__ == "__main__":
    run_baseline()
