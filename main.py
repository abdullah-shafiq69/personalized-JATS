import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re


def get_email_body(msg):
    body = ""
    text = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="ignore")
                    text += body
            if part.get_content_type() == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(errors="ignore")
                    html += body
        return {"text": text, "html": html}
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(errors="ignore")

    return {"text": body}


def indeed_title_and_company_name(html):
    soup = BeautifulSoup(html, 'html.parser')
    job_h1 = soup.find('h1')
    job_title = job_h1.get_text(strip=True) if job_h1 else None
    company_p = soup.find('a', href=re.compile(r'indeed.com/cmp/'))
    if company_p:
        company_name = company_p.get_text(strip=True)

    return job_title, company_name


# credentials
username = "shafiqabdullah275@gmail.com"
password = ""

# connect
imap = imaplib.IMAP4_SSL("imap.gmail.com")
imap.login(username, password)

# select inbox
imap.select("INBOX")

# search all emails
status, messages = imap.search(None, "ALL")

mail_ids = messages[0].split()[::-1]

for mail_id in mail_ids[:200]:  # last 10 emails
    status, msg_data = imap.fetch(mail_id, "(RFC822)")

    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject, encoding = decode_header(msg["Subject"])[0]

            if isinstance(subject, bytes):
                if encoding == "unknown-8bit":
                    subject = subject.decode("latin1", errors="ignore")
                else:
                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")

            from_ = msg.get("From")
            body = get_email_body(msg)
            if "Your application has been submitted. Good luck!".lower() in body["text"].lower():
                title, cn = indeed_title_and_company_name(body["html"])
                print("From:", from_)
                print("Subject:", subject)
                print("date:", msg.get("date"))
                print("Position:", title)
                print("Company:", cn)
                # print("body:", body["text"])
                print("-" * 50)

# imap.logout()