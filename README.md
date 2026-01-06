# Mentorship Portal

A lightweight mentorship portal inspired by PushFar, built with Flask and SQLite. It supports mentor/mentee registration, profile management, mentorship requests, acceptance flows, completion tracking, and threaded messaging within each mentorship.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:5000 in your browser.

## Features

- Join as a mentor or mentee, with secure password hashing
- Dashboard with community stats and your active mentorships
- Profile editing for bio, skills, and availability
- Mentees can create mentorship requests, mentors can accept/decline
- Mark mentorships as completed
- Threaded messaging within each mentorship

## Notes

The app uses SQLite by default (`mentorship.db`). To use another database, set `DATABASE_URL` and `SECRET_KEY` environment variables before running the server.
