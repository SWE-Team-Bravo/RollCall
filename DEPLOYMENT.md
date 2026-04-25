# RollCall Deployment Guide

This guide covers:
- local development setup
- required environment variables
- MongoDB connection options
- running with `uv`
- seeding initial users
- a basic production deployment pattern

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) installed
- MongoDB (local service, local `mongod`, or hosted MongoDB URI)

## 1) Configure Environment Variables

Create a `.env` file in the project root:

```env
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=rollcall
AUTH_COOKIE_KEY=replace-with-a-long-random-secret
```

Notes:
- `MONGODB_URI` can be local (`mongodb://localhost:27017/`) or hosted (Atlas).
- `MONGODB_DB` is the database name this app will use.
- `AUTH_COOKIE_KEY` should be a long random string in production.

`.env` is already gitignored; keep secrets out of version control.

## 2) Install Dependencies with uv

From the repo root:

```bash
uv sync
```

This creates/uses `.venv` and installs dependencies from project metadata/lockfile.

If you need dev tooling too (tests, lint, pre-commit), use:

```bash
uv sync --group dev
```

## 3) Start MongoDB

Choose one option below.

### Option A: Local MongoDB service

If MongoDB is installed as a system service, start it with your OS service manager.

### Option B: Run `mongod` manually

Example:

```bash
mongod --dbpath ./data/db --port 27017
```

Then keep:

```env
MONGODB_URI=mongodb://localhost:27017/
```

### Option C: Hosted MongoDB (Atlas)

Set:

```env
MONGODB_URI=mongodb+srv://<user>:<pass>@<cluster>/<optional>?retryWrites=true&w=majority
```

No local MongoDB process is needed in this case.

## 4) Run the App with uv

From the repo root:

```bash
uv run streamlit run Home.py
```

Optional explicit host/port (useful for remote access):

```bash
uv run streamlit run Home.py --server.address 0.0.0.0 --server.port 15084
```

## 5) Seed Initial Users

After MongoDB is running and `.env` is configured:

```bash
uv run python scripts/seed_users.py
```

This resets and seeds demo data, including user accounts.

You can log in with a seeded user's email and password.

Default demo password:
- `password`

Example seeded user emails:
- `admin1`
- `cadre1`
- `fc1`
- `cadet1`

## Local Development Workflow

1. `uv sync --group dev`
2. Start MongoDB (local or hosted URI)
3. `uv run python scripts/seed_users.py` (first time or when reseeding)
4. `uv run streamlit run Home.py`

Optional checks:

```bash
uv run pytest
uv run ruff check .
```

## Basic Production Deployment

The current `run.sh` is a simple Linux helper script and is not portable. For production, use a process manager (for example: systemd, supervisord, or container orchestration) and run Streamlit with `uv`.

Recommended baseline:
- dedicated Linux VM/container user
- MongoDB as managed service or separate secured instance
- `.env` stored securely (not in repo)
- reverse proxy (Nginx/Caddy) in front of Streamlit
- process manager restart policy and logs

### Example systemd service (basic)

Create `/etc/systemd/system/rollcall.service`:

```ini
[Unit]
Description=RollCall Streamlit App
After=network.target

[Service]
User=rollcall
WorkingDirectory=/opt/rollcall
EnvironmentFile=/opt/rollcall/.env
ExecStart=/usr/local/bin/uv run streamlit run Home.py --server.address 0.0.0.0 --server.port 15084
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable rollcall
sudo systemctl start rollcall
sudo systemctl status rollcall
```

If you self-host MongoDB on the same machine, run MongoDB as its own service and keep `MONGODB_URI` pointed to that service.

## Troubleshooting

- `Database unavailable` in app:
  - verify MongoDB is running
  - verify `MONGODB_URI` and `MONGODB_DB` in `.env`
- login fails for seeded users:
  - reseed using `uv run python scripts/seed_users.py`
  - ensure you are using a seeded user email and the correct password (`password` by default)
- Streamlit command not found:
  - use `uv run streamlit ...` instead of relying on global PATH
