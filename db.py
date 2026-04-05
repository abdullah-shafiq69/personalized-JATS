import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db     = client[os.getenv("MONGO_DB")]

emails = db["emails"]

# ensure message_id is unique — prevents duplicates on rerun
emails.create_index([("message_id", ASCENDING)], unique=True)


def is_seen(message_id: str) -> bool:
    return emails.find_one({"message_id": message_id}) is not None


def insert_email(message_id, subject, sender, company, position, status):
    try:
        emails.insert_one({
            "message_id": message_id,
            "subject"   : subject,
            "sender"    : sender,
            "company"   : company,
            "position"  : position,
            "status"    : status,
        })
    except Exception:
        pass  # duplicate — unique index silently blocks it