# Multi-account Check-in Control Panel Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a secure multi-account web control panel with invite-based enrollment, manual and scheduled check-in jobs, Feishu reporting, and Cloudflare-ready deployment.

**Architecture:** Keep the verified `freshman_checkin` package as the execution engine. Add a FastAPI modular monolith with SQLite-backed durable jobs and a serial worker, plus a React/Vite frontend deployed to Cloudflare Pages.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, SQLite, cryptography AESGCM, Argon2, React, TypeScript, Vite, systemd, Cloudflare Pages and Tunnel.

---

### Task 1: Secure backend foundation

**Files:**
- Create: `server/config.py`, `server/database.py`, `server/models.py`, `server/security.py`
- Create: `tests/test_security.py`, `tests/test_database.py`
- Modify: `requirements.txt`, `.env.example`, `.gitignore`

**Steps:**
1. Add failing tests for AES-256-GCM round trips, tamper rejection, Argon2 password verification, session hashing, and SQLite model creation.
2. Implement configuration with environment/file credential support and strict production validation.
3. Implement SQLAlchemy models for admins, sessions, accounts, invites, runs, settings, and audit events.
4. Run backend tests and dependency checks.

### Task 2: Authentication, accounts, and invitations API

**Files:**
- Create: `server/app.py`, `server/dependencies.py`, `server/schemas.py`, `server/rate_limit.py`
- Create: `server/routes/auth.py`, `server/routes/accounts.py`, `server/routes/invites.py`
- Create: `server/cli.py`
- Test: `tests/test_api.py`

**Steps:**
1. Test administrator login, HttpOnly session cookies, CSRF enforcement, authorization, and logout.
2. Test encrypted account create/update/delete and ensure APIs never return credentials.
3. Test single-use, expiring invitation links and invite enrollment.
4. Add CLI commands to initialize the database, create an administrator, and generate a master key.

### Task 3: Durable jobs, check-in worker, and Feishu

**Files:**
- Create: `server/checkin_runner.py`, `server/jobs.py`, `server/worker.py`, `server/scheduler.py`, `server/feishu.py`
- Create: `server/routes/runs.py`, `server/routes/settings.py`
- Test: `tests/test_jobs.py`, `tests/test_feishu.py`

**Steps:**
1. Test single-account, all-account, and failed-account job creation with duplicate-running protection.
2. Implement a serial worker that uses a fresh browser per attempt and retries automatic failures once after 10 seconds.
3. Implement the 21:05 scheduler entry point and idempotent daily enqueue behavior.
4. Implement signed Feishu cards, encrypted settings, test notification, and daily summary.

### Task 4: Refined Cloudflare Pages frontend

**Files:**
- Create: `frontend/package.json`, TypeScript/Vite configuration, and `frontend/src/**`
- Create: `frontend/public/_redirects`, `frontend/.env.example`

**Steps:**
1. Build login and invite-enrollment screens.
2. Build the “今晚” account panel with single-account and bulk actions.
3. Build account, run-history, and notification-settings views.
4. Use only final states; refresh once after manual submission and on focus, with a manual refresh control.
5. Run type checking, production build, and accessibility checks.

### Task 5: Server and Cloudflare deployment assets

**Files:**
- Create: `deploy/systemd/*.service`, `deploy/systemd/*.timer`
- Create: `deploy/cloudflared/README.md`, `deploy/install-server.sh`
- Modify: `README.md`

**Steps:**
1. Add API, worker, and daily scheduler systemd units with least-privilege settings.
2. Document reuse of an existing Tunnel and addition of a separate API hostname/port.
3. Document Cloudflare Pages build settings and exact API origin configuration.
4. Document backup, restore, secret rotation, and health checks.

### Task 6: Security audit and release verification

**Files:** All project files.

**Steps:**
1. Run Python unit tests, frontend type check/build, dependency audits, and secret scans.
2. Verify credentials never appear in API responses, logs, fixtures, or the Git diff.
3. Run the existing real status-only check from the integrated worker path without submitting.
4. Review the staged diff, commit in logical batches, push, and verify GitHub Actions.
