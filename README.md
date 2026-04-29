# RollCall

RollCall is a web-based ROTC attendance tracking application built for Air Force ROTC cadre and cadets. It streamlines event management, attendance submission, waiver workflows, and flight organization — replacing manual spreadsheets with a centralized, role-aware platform.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | [Streamlit](https://streamlit.io/) |
| Database | [MongoDB](https://www.mongodb.com/) |
| Auth | [streamlit-authenticator](https://github.com/mkhorasani/Streamlit-Authenticator) |
| Data | [Pandas](https://pandas.pydata.org/) |
| Scheduling | [APScheduler](https://apscheduler.readthedocs.io/) |
| Package Manager | [uv](https://docs.astral.sh/uv/) |
| Linting | [Ruff](https://docs.astral.sh/ruff/) |
| Testing | [Pytest](https://pytest.org/) + [Selenium](https://www.selenium.dev/) |

---

## Prerequisites

- Python 3.10+
- MongoDB running locally or a MongoDB Atlas URI
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed

---

## Quickstart

### 1. Clone the repository

```bash
git clone https://github.com/SWE-Team-Bravo/RollCall.git
cd RollCall
```

### 2. Install dependencies

```bash
uv sync
```

For development dependencies:

```bash
uv sync --group dev
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
MONGODB_URI=mongodb://localhost:27017/
MONGODB_DB=rollcall
AUTH_COOKIE_KEY=your_secret_key_here
EMAIL_ADDRESS=your_email@example.com
EMAIL_APP_PASSWORD=your_app_password
APP_BASE_URL=http://localhost:8501
```

| Variable | Description |
|---|---|
| `MONGODB_URI` | MongoDB connection string |
| `MONGODB_DB` | Database name |
| `AUTH_COOKIE_KEY` | Secret key for session cookies |
| `EMAIL_ADDRESS` | Email address for sending notifications |
| `EMAIL_APP_PASSWORD` | App password for the email account |
| `APP_BASE_URL` | Base URL of the deployed app |

### 4. Run the application

```bash
uv run streamlit run Home.py
```

The app will be available at `http://localhost:8501`.

---

## Features

| Feature | Description |
|---|---|
| **Authentication** | Role-based login with persistent cookie sessions |
| **Dashboard** | Attendance grid filtered by event, date, flight, and status |
| **Attendance Submission** | Cadre submit attendance per event with PT/LLAB tracking |
| **Event Management** | Create, edit, and delete PT and LLAB events with timezone support |
| **Cadet Management** | View and manage cadet roster, flights, and profiles |
| **Flight Management** | Organize cadets into flights with assigned commanders |
| **Waivers** | Cadets submit absence waivers; cadre review and approve |
| **Waiver Review** | Cadre review pending waivers with approve/deny workflow |
| **At-Risk Cadets** | Automated report flagging cadets exceeding absence thresholds |
| **Event Code Generator** | Generate and manage check-in codes for events |
| **Flight Commander View** | Live check-in view for flight commanders during events |
| **Modify Attendance** | Commanders adjust attendance records after submission |
| **User Management** | Admins manage user accounts and role assignments |
| **Account Settings** | Users update their own profile and password |
| **Audit Log** | Track all significant actions across the system |
| **Email Templates** | Configure automated email notifications |

---

## Roles

| Role | Access |
|---|---|
| `admin` | Full access to all pages including user management |
| `cadre` | Event management, attendance, waivers, cadet management |
| `flight_commander` | Live check-in view, attendance submission, waiver review |
| `cadet` | Attendance submission, waiver requests, personal attendance view |

---

## Running Tests

```bash
uv run pytest
```

---

## Deployment

Deployment instructions are documented in `DEPLOYMENT.md`.

---


## Credits

| Role | Name |
|---|---|
| Product Owner | Charlie ([@cgale2](https://github.com/cgale2)) |
| Backend Developer | Brent ([@Sqble](https://github.com/Sqble)) |
| Developer | Huseyin ([@hsimsek1](https://github.com/hsimsek1)) |
| Developer | Tati ([@tetkacheva](https://github.com/tetkacheva)) |
| Developer | Elijah ([@elijahseif](https://github.com/elijahseif)) |
| Developer | Koussay ([@koussay0](https://github.com/koussay0)) |
| Developer & Logo Designer | Priyadharsan ([@PriyadharsanJayaseelan](https://github.com/PriyadharsanJayaseelan)) |
| Developer | TJ ([@Monster0506](https://github.com/Monster0506)) |


## Contributing

1. Branch off `main` — `git checkout -b feature/your-feature`
2. Make your changes
3. Run `uv run ruff check .` before committing
4. Open a pull request referencing the issue number