import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re, os, json, csv, asyncio
from dotenv import load_dotenv
from groq import AsyncGroq

load_dotenv()

username = os.getenv("GMAIL_USER")
password = os.getenv("GMAIL_PASS")

client = AsyncGroq(api_key=os.getenv("GROQ_KEY"))

# ── connect ──────────────────────────────────────────────
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(username, password)
imap.select("INBOX")

searches = [
    'BODY "your application"',
    'BODY "we regret"',
    'BODY "unfortunately"',
    'BODY "move forward with other"',
    'BODY "not selected"',
    'BODY "pleased to inform"',
    'BODY "invite you to interview"',
    'BODY "next steps"',
    'BODY "we reviewed your"',
    'BODY "thank you for applying"',
    'BODY "other candidates"',
    'BODY "keep your resume on file"',
    'SUBJECT "application"',
    'SUBJECT "interview"',
    'SUBJECT "your application"',
    'SUBJECT "next steps"',
    'SUBJECT "unfortunately"',
    'SUBJECT "offer"',
]

job_ids = set()
for query in searches:
    status, messages = imap.search(None, query)
    if status == "OK" and messages[0]:
        ids = messages[0].split()
        job_ids.update(ids)
        print(f"{query[:45]:<45} → {len(ids)} found")

print(f"\nTotal unique candidates: {len(job_ids)}")

# ── extract body ──────────────────────────────────────────
def extract_body(msg):
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
            elif ct == "text/html":
                html = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                body = BeautifulSoup(html, "html.parser").get_text(separator=" ")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    return " ".join(body.split())[:500]

def decode_field(value):
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(enc or "utf-8", errors="ignore"))
            except (LookupError, TypeError):
                # unknown-8bit or other garbage encoding — decode as latin-1
                decoded.append(part.decode("latin-1", errors="ignore"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)
# ── fetch emails ──────────────────────────────────────────
job_ids = list(job_ids)
print(f"Fetching {len(job_ids)} emails...")

job_emails = []
for i, eid in enumerate(job_ids):
    try:
        status, data = imap.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        subject = decode_field(msg["subject"])
        sender = decode_field(msg["from"])
        body    = extract_body(msg)

        if len(body) < 50:
            continue

        job_emails.append({
            "id"     : eid,
            "subject": subject,
            "sender" : sender,
            "body"   : body
        })

        if i % 50 == 0:
            print(f"Fetched {i}/{len(job_ids)}...")

    except Exception as e:
        print(f"Failed on email {eid}: {e}")
        continue

print(f"Successfully fetched: {len(job_emails)} emails")

imap.logout()
# ── classify ──────────────────────────────────────────────
BATCH_SIZE   = 10       # requests per batch
WAIT_SECONDS = 61       # 1 min + 1s buffer for TPM window to reset
MAX_RETRIES  = 3        # retries for non-rate-limit errors only


def parse_json_object(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    start = raw.find("{")
    end   = raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")
    return json.loads(raw[start:end])


async def classify_single(e, model="llama-3.1-8b-instant"):
    """Classify one email. Retries on transient errors only — 429s never happen with batch strategy."""
    prompt = f"""You are a job application email classifier.

STEP 1 — Is this a job application email?
A real job email is a direct response to a job application: rejection, interview invite, or status update from a recruiter or hiring manager.

NOT a job email:
- LinkedIn marketing, newsletters, "Jobs you might like"
- Promotional emails, product offers
- Job alert digests ("New jobs matching your search")
- Generic "we're hiring" blasts you didn't apply to
- Indeed/LinkedIn notifications that aren't a response to your application
- Long educational emails, courses, tutorials

STEP 2 — If it IS a job email, extract:
- company: company name. Infer from sender domain if needed. Use "Unknown" if unclear
- position: exact job title applied to. Use "Unknown" if unclear
- status: exactly one of "rejected", "pending", "interview", "acknowledgement"

STEP 3 — If it is NOT a job email:
- company: null
- position: null
- status: "not_job"

OUTPUT: Return only a single JSON object, no explanation, no markdown:
{{"company": "x", "position": "y", "status": "rejected/pending/interview/acknowledgement/not_job"}}

EMAIL:
Subject: {e['subject']}
From: {e['sender']}
{e['body']}"""

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )
            return parse_json_object(response.choices[0].message.content.strip())

        except Exception as ex:
            error_str = str(ex)
            is_rate_limit = "429" in error_str or "rate_limit_exceeded" in error_str

            # 429 should never happen with batch strategy — but if it does, bail
            # loudly so we know the batch size needs adjusting
            if is_rate_limit:
                print(f"  ⚠ Unexpected 429 — consider reducing BATCH_SIZE [{e['subject'][:35]}]")
                return None

            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  ↺ Transient error, retry in {wait}s (attempt {attempt+1}/{MAX_RETRIES}) [{e['subject'][:35]}]")
                await asyncio.sleep(wait)
            else:
                print(f"  ✗ Gave up [{e['subject'][:40]}]: {error_str[:80]}")
                return None


async def classify_all(job_emails):
    total       = len(job_emails)
    results     = []
    batches     = [job_emails[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    total_batches = len(batches)

    print(f"\n{'='*40}")
    print(f"Total emails     : {total}")
    print(f"Batch size       : {BATCH_SIZE}")
    print(f"Total batches    : {total_batches}")
    print(f"Wait between     : {WAIT_SECONDS}s")
    eta_minutes = (total_batches * WAIT_SECONDS) / 60
    print(f"ETA              : ~{eta_minutes:.1f} min")
    print(f"{'='*40}\n")

    for i, batch in enumerate(batches):
        print(f"Batch {i+1}/{total_batches} — firing {len(batch)} requests...")

        # fire all requests in this batch concurrently
        batch_results = await asyncio.gather(
            *[classify_single(e) for e in batch]
        )
        results.extend(batch_results)

        done = min((i + 1) * BATCH_SIZE, total)
        print(f"  ✓ Done: {done}/{total} emails classified")

        # wait between batches — skip after the last one
        if i < total_batches - 1:
            print(f"  ⏳ Waiting {WAIT_SECONDS}s for TPM window to reset...")
            await asyncio.sleep(WAIT_SECONDS)

    return results


# ── run ───────────────────────────────────────────────────
raw_results = asyncio.run(classify_all(job_emails))


# ── save results ──────────────────────────────────────────
final = []
for e, r in zip(job_emails, raw_results):
    if r is None:
        r = {"company": "ERROR", "position": "ERROR", "status": "error"}
    final.append({
        "subject" : e["subject"],
        "sender"  : e["sender"],
        "company" : r.get("company") or "Unknown",
        "position": r.get("position") or "Unknown",
        "status"  : r.get("status", "error"),
    })

with open("results.json", "w", encoding="utf-8") as f:
    json.dump(final, f, indent=2, ensure_ascii=False)
print("Saved → results.json")

with open("results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["subject", "sender", "company", "position", "status"])
    writer.writeheader()
    writer.writerows(final)
print("Saved → results.csv")

# ── summary ───────────────────────────────────────────────
rejected  = sum(1 for r in final if r["status"] == "rejected")
interview = sum(1 for r in final if r["status"] == "interview")
pending   = sum(1 for r in final if r["status"] == "pending")
not_job   = sum(1 for r in final if r["status"] == "not_job")
errors    = sum(1 for r in final if r["status"] == "error")

print(f"\n{'='*40}")
print(f"Total classified : {len(final)}")
print(f"Rejected         : {rejected}")
print(f"Interviews       : {interview}")
print(f"Pending          : {pending}")
print(f"Not a job        : {not_job}")
print(f"Errors           : {errors}")
print(f"{'='*40}")