import imaplib, email, asyncio
from email.header import decode_header
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
from pipeline import run_pipeline
from db import emails as emails_col

load_dotenv()

SEARCHES = [
    'BODY "your application"',    'BODY "we regret"',
    'BODY "unfortunately"',       'BODY "move forward with other"',
    'BODY "not selected"',        'BODY "pleased to inform"',
    'BODY "invite you to interview"', 'BODY "next steps"',
    'BODY "we reviewed your"',    'BODY "thank you for applying"',
    'BODY "other candidates"',    'BODY "keep your resume on file"',
    'SUBJECT "application"',      'SUBJECT "interview"',
    'SUBJECT "your application"', 'SUBJECT "next steps"',
    'SUBJECT "unfortunately"',    'SUBJECT "offer"',
]


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
                decoded.append(part.decode("latin-1", errors="ignore"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


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
    return " ".join(body.split())[:300]


def fetch_all_emails():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_PASS"))
    imap.select("INBOX")

    # search
    job_ids = set()
    for query in SEARCHES:
        status, messages = imap.search(None, query)
        if status == "OK" and messages[0]:
            ids = messages[0].split()
            job_ids.update(ids)
            print(f"{query[:45]:<45} → {len(ids)} found")

    print(f"\nTotal unique candidates: {len(job_ids)}")

    # fetch
    job_emails = []
    job_ids = list(job_ids)
    for i, eid in enumerate(job_ids):
        try:
            status, data = imap.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            subject    = decode_field(msg["subject"])
            sender     = decode_field(msg["from"])
            body       = extract_body(msg)
            message_id = msg.get("Message-ID") or eid.decode()

            if len(body) < 50:
                continue

            job_emails.append({
                "message_id": message_id,
                "subject"   : subject,
                "sender"    : sender,
                "body"      : body,
            })

            if i % 50 == 0:
                print(f"Fetched {i}/{len(job_ids)}...")

        except Exception as e:
            print(f"  Failed on {eid}: {e}")

    imap.logout()
    return job_emails


async def main():
    print("=== Backfill started ===")
    emails = fetch_all_emails()
    print(f"Fetched {len(emails)} emails. Starting pipeline...\n")
    await run_pipeline(emails)

    # summary
    total     = emails_col.count_documents({})
    rejected  = emails_col.count_documents({"status": "rejected"})
    interview = emails_col.count_documents({"status": "interview"})
    pending   = emails_col.count_documents({"status": "pending"})
    not_job   = emails_col.count_documents({"status": "not_job"})

    print(f"\n{'='*40}")
    print(f"Total in DB      : {total}")
    print(f"Rejected         : {rejected}")
    print(f"Interviews       : {interview}")
    print(f"Pending          : {pending}")
    print(f"Not a job        : {not_job}")
    print(f"{'='*40}")


if __name__ == "__main__":
    asyncio.run(main())