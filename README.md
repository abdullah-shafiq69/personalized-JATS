# JATS — Job Application Tracking System

> Automatically classifies your job application emails using AI and stores them in MongoDB in real time.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![MongoDB](https://img.shields.io/badge/MongoDB-8.x-green)
![Groq](https://img.shields.io/badge/Groq-llama--3.1--8b-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

**Repository:** [github.com/abdullah-shafiq69/personalized-JATS](https://github.com/abdullah-shafiq69/personalized-JATS)

---

## Table of contents

- [What it does](#what-it-does)
- [Features](#features)
- [Architecture](#architecture)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Usage](#usage)
- [How classification works](#how-classification-works)
- [Rate limits](#rate-limits)
- [MongoDB schema](#mongodb-schema)
- [Querying the database](#querying-the-database)
- [Environment variables](#environment-variables)
- [Known limitations](#known-limitations)
- [Contributing](#contributing)

---

## What it does

JATS connects to your Gmail inbox, finds job-related emails using 18 keyword searches, and uses **Groq's LLaMA 3.1 8B** to classify each one. Results are stored in **MongoDB** with zero duplicates. It runs in two modes:

- **Backfill** — processes your entire existing inbox in one shot
- **Live listener** — watches for new emails via IMAP IDLE and classifies them the moment they arrive, 24/7

---

## Features

- Real-time email detection via **IMAP IDLE** — no polling, instant response
- **Single-email classification** — one LLM call per email eliminates context bleed and hallucinations
- **Rate-limit safe** — batches 10 requests per 61 seconds to stay within Groq free tier TPM limits
- **Deduplication** — `message_id` unique index silently blocks double-processing on reruns or restarts
- **Encoding resilient** — handles UTF-8, latin-1, unknown-8bit, and malformed headers gracefully
- **Auto-reconnect** — listener recovers from dropped IMAP connections automatically
- **Shared pipeline** — backfill and listener share identical classification and storage logic
- **Exponential backoff** — transient API errors are retried with 1s → 2s → 4s delays

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Gmail Inbox                          │
└───────────────────────────┬─────────────────────────────────┘
                            │
              IMAP IDLE (real-time push)
                            │
          ┌─────────────────▼──────────────────┐
          │           listener.py              │
          │      (runs forever, 24/7)          │
          └─────────────────┬──────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │           backfill.py              │
          │         (run once only)            │
          └─────────────────┬──────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │            pipeline.py             │
          │  • filter already-seen emails      │
          │  • batch 10 emails / 61s           │
          │  • classify each individually      │
          └─────────────────┬──────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │      Groq API (AsyncGroq)          │
          │   llama-3.1-8b-instant             │
          │   • 1 email per call               │
          │   • returns JSON object            │
          └─────────────────┬──────────────────┘
                            │
          ┌─────────────────▼──────────────────┐
          │     MongoDB (jobtracker.emails)    │
          │   • unique index on message_id     │
          │   • stores all classified emails   │
          └────────────────────────────────────┘
```

### Why single-email classification?

The original design batched 20 emails into one prompt. This caused the model to lose track of which email it was classifying, bleeding context between emails and producing hallucinations — wrong companies, wrong statuses, educational newsletters classified as interviews.

Switching to one email per call fixes this entirely. Each call has a focused, unambiguous context. The batch strategy (10 req / 61s) keeps it within Groq's free TPM limit without sacrificing speed.

---

## Project structure

```
personalized-JATS/
├── backfill.py            ← run once to process all existing emails
├── backfill_csv_json.py   ← backfill variant that exports to CSV + JSON
├── listener.py            ← runs forever via IMAP IDLE
├── pipeline.py            ← shared: classify + store logic
├── db.py                  ← MongoDB connection, index, insert, dedup
├── testing.py             ← testing + experimentation scripts
├── .gitignore
├── requirements.txt
└── README.md
```

> **Note:** `.env` is gitignored and must be created manually — see [Setup](#setup).

---

## Prerequisites

- Python **3.11+**
- MongoDB Community Server **8.x** running locally
- Gmail account with **App Password** enabled (requires 2FA)
- Groq API key — free tier at [console.groq.com](https://console.groq.com)

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/abdullah-shafiq69/personalized-JATS.git
cd personalized-JATS
```

### 2. Create and activate virtual environment

```bash
python -m venv venv
source venv/Scripts/activate      # Windows Git Bash
# or
venv\Scripts\activate.bat         # Windows CMD
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

Create a `.env` file in the project root:

```env
GMAIL_USER=you@gmail.com
GMAIL_PASS=your_gmail_app_password
GROQ_KEY=your_groq_api_key
MONGO_URI=mongodb://localhost:27017
MONGO_DB=jobtracker
```

> **Getting a Gmail App Password:**
> Google Account → Security → 2-Step Verification → App Passwords.
> Generate one for "Mail" and paste it as `GMAIL_PASS`.
> Never use your real Gmail password here.

### 5. Start MongoDB

Open a terminal and run — keep it open the entire time:

```cmd
mongod --dbpath "D:\Data\db"
```

Wait until you see:
```
waiting for connections on port 27017
```

> If `mongod` is not in PATH, use the full path:
> `& "C:\Program Files\MongoDB\Server\8.2\bin\mongod.exe" --dbpath "D:\Data\db"`

### 6. Create the database

Open **MongoDB Compass** → connect to `mongodb://localhost:27017`:
- Click `+` next to Databases
- Database name: `jobtracker`
- Collection name: `emails`
- Hit Create Database

---

## Usage

### Backfill — process all existing emails (run once)

```bash
python backfill.py
```

Searches your inbox using 18 job-related keyword patterns, fetches all matching emails, classifies them one by one, and stores results in MongoDB. Already-stored emails are automatically skipped so it is safe to rerun.

To also export results to CSV and JSON:

```bash
python backfill_csv_json.py
```

Sample output:
```
BODY "your application"                       → 42 found
BODY "unfortunately"                          → 38 found
...
Total unique candidates: 813

========================================
Total emails     : 813
Batch size       : 10
Total batches    : 82
Wait between     : 61s
ETA              : ~83.0 min
========================================

Batch 1/82 — classifying 10 emails...
  Waiting 61s...
...
Pipeline done.

========================================
Total in DB      : 813
Rejected         : 312
Interviews       : 28
Pending          : 44
Not a job        : 401
========================================
```

### Listener — watch for new emails forever

```bash
python listener.py
```

Connects to Gmail via IMAP IDLE. The moment a new email lands in your inbox it is fetched, classified, and stored in MongoDB. Automatically reconnects if the connection drops.

Sample output:
```
=== Listener started ===
Listener ready. Watching from UID 9823...
IDLE event: * 9824 EXISTS
New emails detected: 1
  Classifying 1 emails in 1 batches...
  Batch 1/1 — 1 requests...
  Pipeline done. 1 emails processed.
```

---

## How classification works

Each email is sent individually to `llama-3.1-8b-instant` with a two-step prompt.

**Step 1** — Is this a real job application email? Filters out LinkedIn digests, newsletters, promotional emails, job alert notifications, and educational content.

**Step 2** — If it is a job email, extract company, position, and status.

The model returns a single JSON object:

```json
{
  "company": "Google",
  "position": "Data Analyst",
  "status": "rejected"
}
```

| Status | Meaning |
|---|---|
| `rejected` | Application was declined |
| `interview` | Interview invite received |
| `pending` | Application under review |
| `acknowledgement` | Application received confirmation |
| `not_job` | Not a job email |
| `error` | Classification failed after all retries |

---

## Rate limits

Using Groq free tier with `llama-3.1-8b-instant`:

| Limit | Value |
|---|---|
| Requests per minute (RPM) | 30 |
| Requests per day (RPD) | 14,400 |
| Tokens per minute (TPM) | 6,000 |
| Tokens per day (TPD) | 500,000 |

JATS uses 10 emails per batch with a 61-second wait between batches. At ~400 tokens per request this stays comfortably within the TPM limit. If you hit the daily TPD limit (500K tokens ≈ ~1,250 requests), wait for reset at **00:00 UTC** (05:00 PKT).

Check your current usage: [console.groq.com/settings/limits](https://console.groq.com/settings/limits)

---

## MongoDB schema

Each document in the `emails` collection:

```json
{
  "_id": "ObjectId(...)",
  "message_id": "<RFC2822 Message-ID header>",
  "subject": "Your application to Data Analyst at Acme Corp",
  "sender": "recruiting@acme.com",
  "company": "Acme Corp",
  "position": "Data Analyst",
  "status": "rejected"
}
```

The `message_id` field has a **unique index** — duplicate inserts are silently ignored.

---

## Querying the database

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
emails = client["jobtracker"]["emails"]

# summary counts
for status in ["rejected", "interview", "pending", "acknowledgement", "not_job"]:
    print(f"{status}: {emails.count_documents({'status': status})}")

# all interviews
for doc in emails.find({"status": "interview"}):
    print(doc["company"], "—", doc["position"])

# rejections from a specific company
for doc in emails.find({"status": "rejected", "company": "Google"}):
    print(doc["subject"])

# most recent 10 emails
for doc in emails.find().sort("_id", -1).limit(10):
    print(doc["subject"], "→", doc["status"])
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GMAIL_USER` | Yes | Your Gmail address |
| `GMAIL_PASS` | Yes | Gmail App Password (not your login password) |
| `GROQ_KEY` | Yes | Groq API key from console.groq.com |
| `MONGO_URI` | Yes | MongoDB connection string |
| `MONGO_DB` | Yes | MongoDB database name |

---

## Known limitations

- **Groq free tier TPD** — 500K tokens per day limits you to ~1,250 emails per day. Upgrade to Dev tier for higher limits.
- **Gmail App Password required** — standard OAuth is not supported; IMAP must be enabled in Gmail settings.
- **Local MongoDB** — you must manually start `mongod` before running any script. Consider installing as a Windows service for convenience.
- **IMAP IDLE timeout** — Gmail drops IDLE connections after 10 minutes. The listener re-IDLEs every 9 minutes to avoid this.
- **English emails only** — the classifier prompt is in English and works best with English-language emails.

---

## Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

### Ideas for contributions

- FastAPI layer to query results via REST
- Docker + docker-compose setup
- Support for Outlook / other IMAP providers
- Frontend dashboard to visualize application stats
- Export to Google Sheets

---

## License

MIT — do whatever you want with it.
