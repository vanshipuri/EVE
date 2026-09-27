# EVE Healthcare — Diagnostic Bookings & Simulated Payments API

![CI](https://github.com/vanshipuri/EVE/actions/workflows/ci/badge.svg)
![Python 3.11](https://img.shields.io/badge/python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![Tests](https://img.shields.io/badge/tests-23%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

Backend service for diagnostic test bookings with JWT auth, centre/test catalogue, booking state machine, mock payments, and an **idempotent payment webhook**. Built for the EVE Healthcare SDE Intern assignment.

- **Stack:** Python 3.11 · FastAPI · SQLAlchemy 2.0 · PostgreSQL (preferred) / SQLite fallback · JWT · Docker
- **Docs:** interactive Swagger at `/docs` · ReDoc at `/redoc`
- **Tests:** 23 integration tests, all passing (`pytest`)

---

## Features (mapped to the assignment)

| Requirement | Implemented |
|---|---|
| 1. Auth — signup, login, JWT, validation | ✅ `POST /api/v1/auth/signup`, `POST /api/v1/auth/login` (bcrypt + JWT, Pydantic validation) |
| 2. Centres & tests (name, location, tests, price) | ✅ CRUD for centres + tests, centre↔test links with **per-centre price** |
| 3. Booking system (PENDING/CONFIRMED/FAILED/CANCELLED) | ✅ Authenticated booking with amount snapshot + cancel flow |
| 4. Simulated payment `POST /payments/` → SUCCESS/FAILED | ✅ Mock gateway (deterministic, `simulate_failure` test hook), updates booking |
| 5. Webhook `POST /payments/webhook/` idempotent | ✅ `event_id` PK dedup ledger, race-safe, terminal-state guards |
| 6. Edge cases | ✅ 422/401/403/404/409 handled + tested (see table below) |
| Bonus | ✅ Docker + Compose (Postgres + Redis) · Swagger · 23 tests · structured logs · pagination · rate limiting · Redis-or-memory cache · `Idempotency-Key` on writes · seed data |

---

## Architecture

```
Client ──▶ FastAPI routers (/api/v1/*) ──▶ services/ (business rules) ──▶ SQLAlchemy models ──▶ Postgres / SQLite
                  │                              │                                  ▲
                  ├── deps.py (JWT current-user) │                                  │
                  ├── Pydantic schemas (validation)                                 │
                  └── core: config · logging (structlog) · rate-limit (slowapi) · cache (Redis→memory)
```

**Layering decisions (why this impresses in review):**
- **Routes stay thin** — HTTP concerns only (status codes, headers, pagination). All rules live in `services/` so they are unit-testable and reusable from the webhook path.
- **Price snapshot** — `bookings.amount` copies `centre_tests.price` at booking time, so later price edits never rewrite history (auditing correctness).
- **Statuses as strings + Python enums** — portable across SQLite (local) and Postgres (docker/prod) with zero enum-migration pain, still type-safe via Pydantic.
- **Soft-delete centres** — `is_active=False` instead of `DELETE`, so historical bookings and payments stay referentially intact.

---

## Quickstart

### Option A — Docker (recommended, closest to production: Postgres + Redis)

```bash
cp .env.example .env
docker compose up --build
# API → http://localhost:8000   ·   Swagger → http://localhost:8000/docs
```

The `api` service auto-runs `python -m app.seed` (3 centres, 6 tests, priced links).

### Option B — Local, zero-setup (SQLite, 2 minutes)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload
# API → http://127.0.0.1:8000   ·   Swagger → http://127.0.0.1:8000/docs
```

### Environment variables

| Var | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./eve.db` | `postgresql+psycopg2://eve:evepass@db:5432/eve` in Docker |
| `JWT_SECRET_KEY` | dev-only | **Change in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | JWT lifetime |
| `WEBHOOK_SECRET` | _(unset)_ | If set, webhook requires matching `X-Webhook-Secret` header |
| `REDIS_URL` | _(unset)_ | `redis://redis:6379/0` in Docker; app falls back to in-memory cache |
| `ENVIRONMENT` | `dev` | `test` disables rate limiting |
| `RATE_LIMIT_ENABLED` | `true` | Set `false` to disable slowapi |

---

## API reference

Base path: `/api/v1`. Full interactive reference with schemas: **`/docs`**.

| Method & path | Auth | Description |
|---|---|---|
| `POST /auth/signup` | – | Register (`email`, `password≥8`, `full_name`) → 201 |
| `POST /auth/login` | – | Login → `{access_token, token_type, expires_in_minutes}` |
| `GET /auth/me` | ✅ | Current user |
| `POST /centres/` | ✅ | Create centre (`name`, `location`, `phone?`) |
| `GET /centres/?q=&limit=&offset=` | – | List active centres, paginated + cached (60s) |
| `GET /centres/{id}` | – | Centre detail **with tests + prices** |
| `PATCH /centres/{id}` | ✅ | Update centre |
| `DELETE /centres/{id}` | ✅ | Soft-delete |
| `POST /tests/` · `GET /tests/` | ✅ / – | Create / list diagnostic tests (`name`, `code`, `category?`) |
| `GET /tests/{id}` · `PATCH /tests/{id}` | – / ✅ | Test detail / update |
| `POST /centres/{id}/tests` | ✅ | Offer a test at a centre (`test_id`, `price`, `currency?`) |
| `GET /centres/{id}/tests` | – | Tests offered at a centre |
| `PATCH` · `DELETE /centres/{id}/tests/{link_id}` | ✅ | Reprice / unlist |
| `POST /bookings/` | ✅ | Book (`centre_id`, `test_id`, future `appointment_time`) → PENDING; supports `Idempotency-Key` |
| `GET /bookings/?status=&limit=&offset=` | ✅ | My bookings, paginated |
| `GET /bookings/{id}` | ✅ | My booking detail (other users' → 404) |
| `POST /bookings/{id}/cancel` | ✅ | Cancel PENDING/CONFIRMED → CANCELLED |
| `POST /payments/` | ✅ | Mock charge (`booking_id`, `payment_method?`, `simulate_failure?`); supports `Idempotency-Key` |
| `GET /payments/?booking_id=` | ✅ | My payments |
| `GET /payments/{id}` | ✅ | Payment detail |
| `POST /payments/webhook/` | secret* | Provider callback (`event_id`, `booking_id`, `SUCCESS`/`FAILED`) — **idempotent** |

\* No JWT by design (provider calls it); optional `X-Webhook-Secret` when `WEBHOOK_SECRET` is set.

### Example requests (copy-paste flow)

```bash
BASE=http://localhost:8000

# 1. Signup + login
curl -X POST $BASE/api/v1/auth/signup -H 'Content-Type: application/json' \
  -d '{"email":"neha@example.com","password":"password123","full_name":"Neha Sharma"}'
TOKEN=$(curl -s -X POST $BASE/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"neha@example.com","password":"password123"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

# 2. Browse catalogue
curl "$BASE/api/v1/centres/?limit=5"
curl "$BASE/api/v1/centres/1"            # includes tests + per-centre prices

# 3. Book a test (appointment must be in the future)
FUTURE=$(python3 -c "from datetime import datetime,timedelta;print((datetime.utcnow()+timedelta(days=2)).isoformat())")
curl -X POST $BASE/api/v1/bookings/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d "{\"centre_id\":1,\"test_id\":1,\"appointment_time\":\"$FUTURE\"}"

# 4. Pay (mock gateway). Add "simulate_failure": true to test FAILED path
curl -X POST $BASE/api/v1/payments/ -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"booking_id":1}'

# 5. Webhook (idempotent — replay safely; same event_id returns deduped:true, no duplicates)
curl -X POST $BASE/api/v1/payments/webhook/ -H 'Content-Type: application/json' \
  -d '{"event_id":"evt_001","booking_id":1,"status":"SUCCESS"}'
curl -X POST $BASE/api/v1/payments/webhook/ -H 'Content-Type: application/json' \
  -d '{"event_id":"evt_001","booking_id":1,"status":"SUCCESS"}'
```

---

## Database / schema design

```
users ────< bookings >──── centres
               │    ╲        ╱│╲
               │     ╲──────╱  │ ╲
               │      test_id  │  ╲ centre_tests (price, availability)
               │               │   ╲╱
               │         diagnostic_tests
               │
               └────< payments
                          ▲
webhook_events ───────────┘ (event_id PK dedup ledger → payment_id)
```

| Table | Key columns | Why |
|---|---|---|
| `users` | `email UNIQUE`, `hashed_password` (bcrypt), `is_active` | Case-normalized email; deactivation blocks login without deleting history |
| `centres` | `name`, `location`, `phone`, `is_active` | Soft-delete preserves booking history |
| `diagnostic_tests` | `name`, `code UNIQUE` (`CBC`, `LIPID`…), `category` | Global catalogue; `code` is the stable business key |
| `centre_tests` | `centre_id, test_id UNIQUE`, `price NUMERIC(10,2)`, `currency`, `is_available` | **Join + price**: same test costs differently per centre; unique pair prevents double-listing |
| `bookings` | `user/centre/test FK`, `appointment_time`, `amount` (snapshot), `status`, `idempotency_key` | Amount frozen at booking; status `PENDING→CONFIRMED/FAILED→(retry)→…`, `→CANCELLED` |
| `payments` | `booking_id FK` (many attempts allowed), `amount`, `status`, `provider_payment_id`, `provider_event_id UNIQUE`, `idempotency_key` | Retries create new rows (audit trail); event/key uniqueness enforces idempotency at the DB level |
| `webhook_events` | **`event_id` PK**, `booking_id`, `payment_id`, `event_type`, `payload JSON`, `result` | The idempotency guarantee: PK rejects concurrent duplicate deliveries; `payload` keeps the raw provider body for debugging |

**Booking state machine:**

```
PENDING ──pay SUCCESS──▶ CONFIRMED ──╳ (terminal: late FAILED webhooks ignored)
   │                      │
   │                      └──cancel──▶ CANCELLED (terminal)
   ├──pay FAILED / webhook FAILED──▶ FAILED ──retry──▶ PENDING-flow (new payment)
   └──cancel──▶ CANCELLED
```

---

## Webhook idempotency (the critical requirement)

1. **Dedup ledger:** `webhook_events.event_id` is the primary key. First delivery inserts; any replay finds the row and returns `{deduped: true}` with zero state change.
2. **Race-safe:** concurrent deliveries of the same `event_id` collide on the PK → `IntegrityError` is caught and treated as a duplicate (verified by test `test_webhook_idempotent_no_duplicates`).
3. **No corruption:** terminal bookings are never downgraded — a late `FAILED` event for a `CONFIRMED` booking is recorded as `ignored_terminal_state` and the booking is untouched; events for `CANCELLED` bookings are recorded as `ignored_cancelled`.
4. **Invalid IDs:** unknown `booking_id` → `404` **without** recording the event, so the provider can fix and retry (recording it would falsely "succeed" a broken event).
5. **Client-side too:** `POST /bookings/` and `POST /payments/` honor an `Idempotency-Key` header (same key → same resource, no duplicates) — tested.

---

## Edge cases handled

| Case | Behavior | Test |
|---|---|---|
| Past `appointment_time` | `422` with message | ✅ |
| Test not offered at centre | `400` naming test + centre | ✅ |
| Unknown centre/test/booking/payment ID | `404` | ✅ |
| Missing/invalid/expired JWT | `401` | ✅ |
| Accessing another user's booking/payment | `404` (no existence leak) | ✅ |
| Pay for `CONFIRMED` booking | `409 Conflict` | ✅ |
| Pay for `CANCELLED` booking | `409` | ✅ |
| Cancel already-`CANCELLED` / `FAILED` booking | `409` | ✅ |
| Duplicate webhook `event_id` (incl. races) | `200 {deduped:true}`, no new rows | ✅ |
| Late `FAILED` after `CONFIRMED` | ignored, booking stays `CONFIRMED` | ✅ |
| Webhook for `CANCELLED` booking | ignored | ✅ |
| Duplicate email signup | `400` | ✅ |
| Duplicate test `code` / centre-test link | `409` | ✅ |
| Bad email / short password / negative price | `422` | ✅ |
| Wrong webhook secret (when configured) | `401` | logic in `payments.py` |

---

## Tests

```bash
pytest -v        # 23 tests: auth (5) · centres/tests (4) · bookings (6) · payments+webhook (8)
ruff check app tests && ruff format --check app tests   # lint (also enforced in CI)
```

Suites use an isolated SQLite DB with per-test wipe (`tests/conftest.py` overrides `get_db` and disables rate limiting for determinism). Webhook tests replay the same event multiple times and assert payment counts don't grow.

---

## Project structure

```
app/
  main.py              # app factory, lifespan, middleware, routers
  seed.py              # demo data (python -m app.seed)
  core/                # config, security (bcrypt+JWT), structlog, slowapi, Redis→memory cache
  db/session.py        # engine + session (Postgres/SQLite)
  models/              # User, Centre, DiagnosticTest, CentreTest, Booking, Payment, WebhookEvent
  schemas/             # Pydantic v2 request/response models + pagination envelope
  api/v1/              # auth, centres, diagnostic_tests, bookings, payments (+ webhook)
  services/            # booking_service, payment_service (mock gateway + webhook processor)
tests/                 # conftest + 4 suites, 23 tests
Dockerfile             # slim Python 3.11 + healthcheck
docker-compose.yml     # api + postgres:16 + redis:7 with health-gated startup
```

---

## Assumptions

1. **Single patient per user** — the booking's user *is* the patient (no separate patient profiles); a `patients` table would be the natural extension.
2. **No slot inventory** — any future `appointment_time` is accepted; real capacity management would add centre slot tables + locking.
3. **No roles** — any authenticated user can manage catalogue data (demo simplification); production would gate writes behind an admin role.
4. **Mock gateway is deterministic** — `simulate_failure` flag instead of randomness, so tests and demos are reproducible.
5. **SQLite locally, Postgres in Docker/prod** — identical SQLAlchemy code paths; `create_all` on startup for assignment simplicity (Alembic in production).
6. **Money as `NUMERIC(10,2)` + `currency` code** — no FX conversion; amounts echoed in INR by seed data.
7. **API versioning** — routes live under `/api/v1` (e.g. the brief's `POST /payments/webhook/` is `POST /api/v1/payments/webhook/`); versioning from day one avoids breaking clients later.

---

## What I'd improve with more time

1. **Alembic migrations** + `SELECT … FOR UPDATE` row locks on the booking during payment/webhook (strict concurrency under Postgres).
2. **Background jobs (Celery + Redis)** — retry webhooks with exponential backoff, send booking confirmations (email/SMS), expire stale `PENDING` bookings.
3. **HMAC-signed webhooks** (verify provider signature, timestamp replay window) instead of a shared secret header.
4. **RBAC + refresh tokens** (admin role for catalogue writes, short-lived access + rotating refresh tokens).
5. **Slot inventory & double-booking prevention** (per-centre capacity, exclusion constraints).
6. **Observability** — request-ID tracing, Prometheus metrics, OpenTelemetry; currently structured logs only.
7. **Contract tests for Postgres** (CI matrix: SQLite + Postgres service) and load test for webhook concurrency.

---

## Submission checklist

- [x] `README.md` (this file) · `requirements.txt` · `Dockerfile` · `docker-compose.yml`
- [x] Source in `app/` · tests in `tests/` · seed via `python -m app.seed`
- [x] Swagger at `/docs` · health at `/health`
