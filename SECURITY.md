# ShoeMatch AI — Security Policy & Controls Architecture

## Overview
ShoeMatch AI enforces enterprise-grade defense-in-depth security across authentication, authorization, API exposure, file validation, rate limiting, and database interactions.

---

## Security Control Specifications

### 1. Authentication & Session Security
- **Password Hashing**: Passwords are hashed using NIST-approved `PBKDF2-HMAC-SHA256` with 100,000 key-stretching iterations and a cryptographically generated 16-byte salt per user (`secrets.token_hex(16)`).
- **Session Tokens**: JWT tokens are signed using HMAC-SHA256 and enforce a 24-hour expiration (`exp`). Tokens are transmitted via `HttpOnly` cookies and `Bearer` authorization headers.
- **Enforced Password Change**: Users flagged with `must_change_password = 1` are restricted by backend authorization dependencies (`require_authenticated_user`) from accessing all system API routes until their password is password-changed via `/api/auth/change-password`.
- **Generic Login Errors**: Authentication failures return a standardized `401 Invalid username or password` message to prevent account enumeration attacks.

### 2. Role-Based Access Control (RBAC)
- **Role Hierarchy**: System enforces strict separation between `admin` and `employee` roles.
- **Server-Side Enforcement**: All administrative routes (`/api/admin/*`, `POST/PUT/DELETE /api/designs/*`, `/api/locations/*`, `/api/bulk-import/*`) are protected by the `require_admin_user` dependency. Any unauthorized request from an `employee` or unauthenticated user is rejected with `403 Admin privileges required`.

### 3. Image Upload & Content Validation
- **Magic-Byte Structure Verification**: File uploads are verified via `PIL.Image.open().verify()` to inspect true image headers and structure, rejecting executable scripts or malicious files disguised with image file extensions.
- **File Size Capping**: File uploads strictly enforce a 10MB maximum limit (`MAX_UPLOAD_SIZE_BYTES`), protecting against memory exhaustion denial-of-service attacks.
- **Filename Sanitization**: Uploaded filenames are stripped of path components (`Path(filename).name`) and sanitized to alphanumeric characters, eliminating path traversal risks (`../`).

### 4. Rate Limiting & Throttling
- **API Throttling**: Implemented using `slowapi` (`limits` backend):
  - `POST /api/auth/login`: Restricted to 10 requests per minute per IP to mitigate brute-force password attempts.
  - `POST /api/match`: Restricted to 20 requests per minute per IP to prevent compute resource abuse.
  - Rate limit violations return `429 Too Many Requests`.

### 5. Storage & Database Access Control
- **Parameterized SQL**: All database operations in `database.py`, `bulk_import.py`, and `ingestion.py` exclusively use SQLite parameter binding (`?` placeholders) to eliminate SQL injection vulnerabilities.
- **Static File Isolation**: Mounted static routes (`/catalog_images`, `/uploads`) use FastAPI `StaticFiles` with path canonicalization and directory listing disabled (`autoindex off`).

### 6. Environment & Secret Management
- **Secret Management**: JWT keys (`SECRET_KEY`), default seed passwords, and host options are loaded from environment variables (`.env`).
- **Repository Safety**: `.env` and local environment files are explicitly ignored in `.gitignore`.

---

## Infrastructure Security Notes (Production Deployment)

> [!NOTE]
> **TLS / HTTPS Termination**: While the application codebase enforces secure headers and cookie policies (`HttpOnly`), full Transport Layer Security (TLS/HTTPS) termination is handled at the Nginx reverse proxy level via Let's Encrypt / Certbot in production deployments.
