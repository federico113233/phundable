# Quick start for the team

This zip is the code only — two things were deliberately left out and you'll
need to add them locally before it runs:

## 1. Install the one dependency

```bash
cd phundable
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## 2. The Groq API key is already included

`server/.env` ships with a working key, so AI document drafting works out of
the box — nothing to configure. It's a shared team key: if several people
generate documents at the same time you may occasionally see a rate-limit
delay, but the app retries automatically and never hard-fails. Please don't
commit it anywhere public or use it outside this project.

## 3. Run it

```bash
.venv/bin/python server/server.py
```

Open **http://localhost:8010**.

- The onboarding form has three yellow "demo" buttons at the top that fill it
  with a sample charity in one click — useful for testing scores without
  typing 24 fields.
- `#/admin` shows the internal company-quote-request pipeline (already seeded
  with 8 demo requests). Not linked from the nav, not authenticated.

See `README.md` for everything else — architecture, scoring logic, how to
swap in real funder data, known limitations.
