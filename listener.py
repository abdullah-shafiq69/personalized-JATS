import imaplib, email, asyncio, os
from email.header import decode_header
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from pipeline import run_pipeline

load_dotenv()


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


def imap_connect():
    imap = imaplib.IMAP4_SSL("imap.gmail.com")
    imap.login(os.getenv("GMAIL_USER"), os.getenv("GMAIL_PASS"))
    imap.select("INBOX")
    return imap


def fetch_new_emails(imap, last_uid):
    """Fetch all emails with UID greater than last_uid."""
    status, messages = imap.uid("search", None, f"UID {last_uid+1}:*")
    if status != "OK" or not messages[0]:
        return [], last_uid

    uids = messages[0].split()
    new_emails = []
    new_last_uid = last_uid

    for uid in uids:
        try:
            status, data = imap.uid("fetch", uid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])

            subject    = decode_field(msg["subject"])
            sender     = decode_field(msg["from"])
            body       = extract_body(msg)
            message_id = msg.get("Message-ID") or uid.decode()

            if len(body) < 50:
                continue

            new_emails.append({
                "message_id": message_id,
                "subject"   : subject,
                "sender"    : sender,
                "body"      : body,
            })
            new_last_uid = max(new_last_uid, int(uid))

        except Exception as e:
            print(f"  Fetch error {uid}: {e}")

    return new_emails, new_last_uid


def get_latest_uid(imap):
    """Get the highest UID currently in inbox."""
    status, messages = imap.uid("search", None, "ALL")
    if status == "OK" and messages[0]:
        uids = messages[0].split()
        return int(uids[-1]) if uids else 0
    return 0


async def idle_loop():
    imap = imap_connect()
    last_uid = get_latest_uid(imap)
    print(f"Listener ready. Watching from UID {last_uid}...")

    while True:
        try:
            # enter IDLE
            imap.send(b"A001 IDLE\r\n")
            imap.readline()  # "+ idling"

            # wait up to 9 min (Gmail drops IDLE at 10min)
            imap.sock.settimeout(540)
            try:
                response = imap.readline()
                print(f"IDLE event: {response.decode().strip()}")
            except:
                pass  # timeout — re-IDLE normally

            # exit IDLE
            imap.send(b"DONE\r\n")
            imap.readline()

            # fetch anything new since last_uid
            new_emails, last_uid = fetch_new_emails(imap, last_uid)

            if new_emails:
                print(f"New emails detected: {len(new_emails)}")
                await run_pipeline(new_emails)
            else:
                print("No new relevant emails.")

        except Exception as ex:
            print(f"IDLE error: {ex} — reconnecting in 10s...")
            await asyncio.sleep(10)
            try:
                imap = imap_connect()
                last_uid = get_latest_uid(imap)
            except Exception as e:
                print(f"Reconnect failed: {e}")


if __name__ == "__main__":
    print("=== Listener started ===")
    asyncio.run(idle_loop())