# UCATify

A Streamlit study app for the **UCAT** (University Clinical Aptitude Test),
covering the four current subtests:

- **Verbal Reasoning (VR)**
- **Decision Making (DM)**
- **Quantitative Reasoning (QR)**
- **Situational Judgement (SJT)**

> Built for the current (2025+) UCAT format, which no longer includes Abstract
> Reasoning. Cognitive subtests (VR, DM, QR) are reported on a 300–900 scale;
> the SJT is reported in Bands 1–4.

## Features

- **📊 Dashboard** — indicative scaled scores per subtest (and SJT band), a
  cognitive total out of 2700, accuracy by subtest, an activity trend, question
  coverage, and an exam countdown.
- **📝 Practice Questions** — timed, filterable quizzes (by subtest / difficulty)
  with instant explanations. Every answer is logged for analytics.
- **⏱️ Mock Exam** — full or single-subtest timed mocks paced at the real UCAT
  per-question rate, with a live countdown, auto-grading, per-subtest scaled
  scores, and an answer review. Mock answers feed your analytics too.
- **🃏 Flashcards** — spaced repetition (SM-2) that resurfaces weaker cards sooner.
- **🗓️ Study Scheduler** — task list with due dates, statuses, and a one-click
  plan generator.
- **📚 Strategy & Skills** — technique notes and high-yield tips for each subtest.
- **🤖 AI Tutor** — chat with Claude for worked examples and exam strategy
  (requires `ANTHROPIC_API_KEY`).
- **⚙️ Manage** — add your own questions, flashcards, topics, and set the exam date.
- **👤 Accounts** — each student signs in with their own username/password.
  Practice attempts, flashcard progress, study tasks, chat history, and exam
  date are all tracked per account, so sharing a deployment doesn't mix up
  anyone's stats. The question/flashcard/topic content bank itself is shared
  across accounts.

The app ships with starter content across every subtest so it's useful immediately.

> The estimated scores are an indicative guide derived from your practice
> accuracy only — they are not official UCAT scores.

## Run locally

```bash
cd ucat
pip install -r requirements.txt
streamlit run app.py
```

With no configuration it uses a local SQLite file (`ucat.db`).

## Configuration

Set these as environment variables or in `.streamlit/secrets.toml`:

| Key | Purpose |
| --- | --- |
| `DATABASE_URL` | Neon / PostgreSQL connection string. Falls back to SQLite if unset. |
| `ANTHROPIC_API_KEY` | Enables the AI Tutor. |
| `APP_PASSWORD` | Optional shared password gate in front of individual account sign-in. |

Example `secrets.toml`:

```toml
DATABASE_URL = "postgresql://user:pass@ep-xxx.neon.tech/ucat"
ANTHROPIC_API_KEY = "sk-ant-..."
APP_PASSWORD = "study-hard"
```
