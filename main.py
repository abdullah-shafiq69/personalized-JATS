import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re, os, json, csv
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

# credentials
username = os.getenv("GMAIL_USER")
password = os.getenv("GMAIL_PASS")

# groq client
client = Groq(api_key=os.getenv("GROQ_KEY"))

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
                body = part.get_payload(decode=True).decode(errors="ignore")
                break
            elif ct == "text/html":
                html = part.get_payload(decode=True).decode(errors="ignore")
                body = BeautifulSoup(html, "html.parser").get_text(separator=" ")
                break
    else:
        body = msg.get_payload(decode=True).decode(errors="ignore")
    return " ".join(body.split())[:500]


# ── fetch emails ──────────────────────────────────────────
job_ids = list(job_ids)
print(f"Fetching {len(job_ids)} emails...")

job_emails = []
for i, eid in enumerate(job_ids):
    try:
        status, data = imap.fetch(eid, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])

        subject = msg["subject"] or ""
        sender  = msg["from"] or ""
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


# ── classify ──────────────────────────────────────────────
def extract_json(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    start = raw.find("[")
    end   = raw.rfind("]") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON array found in response")
    return json.loads(raw[start:end])


def classify_batch(emails, model="llama-3.1-8b-instant"):
    emails_text = ""
    for i, e in enumerate(emails):
        emails_text += f"EMAIL {i+1}:\nSubject: {e['subject']}\nFrom: {e['sender']}\n{e['body']}\n\n---\n\n"

    prompt = f"""You are a job application email classifier.

STEP 1 — Is this a job application email?
A real job email is a direct response to a job application: rejection, interview invite, or status update from a recruiter or hiring manager.

NOT a job email:
- LinkedIn marketing, newsletters, "Jobs you might like"
- Promotional emails, product offers
- Job alert digests ("New jobs matching your search")
- Generic "we're hiring" blasts you didn't apply to
- Indeed/LinkedIn notifications that aren't responses to your application, Please submit a quick application

STEP 2 — If it IS a job email, extract:
- company: company name. Infer from sender domain if needed. Use "Unknown" if unclear
- position: exact job title applied to. Use "Unknown" if unclear
- status: exactly one of "rejected", "pending", "interview"

STEP 3 — If it is NOT a job email, return:
- company: null
- position: null  
- status: "not_job"
this step is crucial so dont break it 

OUTPUT: Return only a JSON array, one object per email, no explanation, no markdown:
[{{"company": "x", "position": "y", "status": "rejected/pending/interview/not_job"}}]

EMAILS:
{emails_text}"""

    response = client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return extract_json(response.choices[0].message.content.strip())

# ── run classification ────────────────────────────────────
results      = []
failed_chunks = []
chunks = [job_emails[i:i+20] for i in range(0, len(job_emails), 20)]

for i, chunk in enumerate(chunks):
    try:
        print(f"Classifying chunk {i+1}/{len(chunks)}...")
        batch_results = classify_batch(chunk)
        results.extend(batch_results)
    except Exception as e:
        print(f"Chunk {i+1} failed: {e}")
        failed_chunks.append(i)
        continue

# ── retry failed chunks ───────────────────────────────────
if failed_chunks:
    print(f"\nRetrying {len(failed_chunks)} failed chunks...")
    for i in failed_chunks:
        try:
            print(f"Retrying chunk {i+1}...")
            batch_results = classify_batch(chunks[i])
            results.extend(batch_results)
            print(f"Chunk {i+1} recovered: {len(batch_results)} results")
        except Exception as e:
            print(f"Chunk {i+1} failed again: {e}")

print(f"\nDone. Classified {len(results)}/{len(job_emails)} emails")

# ── save results ──────────────────────────────────────────
# merge email metadata with classification results
final = []
for e, r in zip(job_emails, results):
    final.append({
        "subject" : e["subject"],
        "sender"  : e["sender"],
        "company" : r.get("company", "Unknown"),
        "position": r.get("position", "Unknown"),
        "status"  : r.get("status", "Unknown"),
    })

# save as JSON
with open("results.json", "w", encoding="utf-8") as f:
    json.dump(final, f, indent=2, ensure_ascii=False)
print("Saved → results.json")

# save as CSV
with open("results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["subject", "sender", "company", "position", "status"])
    writer.writeheader()
    writer.writerows(final)
print("Saved → results.csv")

# ── print summary ─────────────────────────────────────────
rejected  = sum(1 for r in final if r["status"] == "rejected")
interview = sum(1 for r in final if r["status"] == "interview")
pending   = sum(1 for r in final if r["status"] == "pending")
not_job   = sum(1 for r in final if r["status"] == "not_job")

print(f"\n{'='*40}")
print(f"Total classified : {len(final)}")
print(f"Rejected         : {rejected}")
print(f"Interviews       : {interview}")
print(f"Pending          : {pending}")
print(f"Not a job        : {not_job}")

print(f"{'='*40}")

imap.logout()