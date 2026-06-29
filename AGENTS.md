# Quick Study Builder

AI-powered study/learning web app for students and teachers. Two parts:

- **Backend** (`backend/`): Flask API, served at `http://localhost:3000` (dev: `python app.py`).
- **Frontend** (`frontend/`): static HTML/CSS/JS, no build step, served at `http://localhost:5500` (`python -m http.server 5500`).

The frontend hardcodes the backend URL to `http://localhost:3000` whenever it is opened on `localhost`/`127.0.0.1` (see `frontend/assets/js/api-config.js`), so always open the app via `http://localhost:5500`.

## Cursor Cloud specific instructions

### Services and how to run them

| Service | Command | Port |
|---|---|---|
| Backend (Flask, dev) | `cd backend && ./venv/bin/python app.py` | 3000 |
| Frontend (static) | `cd frontend && python3 -m http.server 5500` | 5500 |

Open `http://localhost:5500` in a browser. Health check: `curl http://localhost:3000/api/health`.

### Database (MySQL is required, and must be started each session)

- The committed `backend/.env` is configured for **MySQL** (`root` / `Eman@123`, database `quick_study_db`). MySQL 8 is installed in the snapshot but its service is **not** auto-started — run `sudo service mysql start` at the start of each session before launching the backend.
- **Gotcha:** the backend does *not* gracefully fall back to SQLite when `MYSQL_*` vars are set in `.env`. If MySQL is down, `python app.py` crashes on startup at `init_db()` with a `pymysql` connection-refused error. (SQLite is only used when `MYSQL_USER`/`MYSQL_DATABASE` are empty.)
- The schema is auto-created/migrated on backend startup (`init_db()`), and an admin user is synced from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `.env`.

### AI / Gemini

- The `GEMINI_API_KEY` committed in `backend/.env` is **invalid** (`/api/health` reports `geminiKey: error_401`). Modules that depend on Gemini (quiz, humanizer, summarizer, question generation, and the Gemini grammar path) will not work until a valid key is set in `backend/.env`.
- **Grammar check works offline** via `language-tool-python` (uses Java, which is installed). The first `/grammar/check` call downloads LanguageTool (~200 MB), so it is slow once, then fast.

### Auth

- New signups are auto-verified (`is_verified=1`); SMTP is optional, so account creation + login works without email configured.

### Lint / test / build

- No automated test suite, linter, or frontend build step exists in this repo. "Build" for the frontend is just serving the static files; the backend runs directly via `app.py` (dev) or `gunicorn app:app` (prod, see `render.yaml`).

### Heavy/optional deps

- The transcript module (`yt-dlp`, `youtube-transcript-api`) is enabled; Whisper is not installed but the module still loads. `ffmpeg` is installed.
