# RollCall Deployment Guide

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) installed
- MongoDB (local service, local `mongod`, or hosted MongoDB URI)

## Configure Environment Variables

Create a `.env` file in the project root:

```env
MONGODB_URI=
MONGODB_DB=
AUTH_COOKIE_KEY=

EMAIL_ADDRESS=
EMAIL_APP_PASSWORD=

APP_BASE_URL=
```

Notes:
- `MONGODB_URI` can be local (`mongodb://localhost:27017/`) or hosted (Atlas).
- `MONGODB_DB` is the database name this app will use.
- `AUTH_COOKIE_KEY` should be a long random string in production.

## Install Dependencies with uv

From the repo root:

```bash
uv sync
```

This creates/uses `.venv` and installs dependencies from project metadata/lockfile.

If you need dev tooling too (tests, lint, pre-commit), use:

```bash
uv sync --group dev
```

## Start MongoDB

## Run the App with uv

From the repo root:

```bash
uv run streamlit run Home.py
```

Optional explicit host/port (useful for remote access):

```bash
uv run streamlit run Home.py --server.address 0.0.0.0 --server.port 15084
```

## Seed Initial Users

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

## Troubleshooting

- `Database unavailable` in app:
  - verify MongoDB is running
  - verify `MONGODB_URI` and `MONGODB_DB` in `.env`
- login fails for seeded users:
  - reseed using `uv run python scripts/seed_users.py`
  - ensure you are using a seeded user email and the correct password (`password` by default)
- Streamlit command not found:
  - use `uv run streamlit ...` instead of relying on global PATH
