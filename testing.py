import os
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI"))
db     = client[os.getenv("MONGO_DB")]
emails = db["emails"]

print(emails.count_documents({}))


# # see first 5 documents
# for doc in emails.find().limit(5):
#     print(doc)

# summary counts
for status in ["rejected", "interview", "pending", "not_job", "error"]:
    print(f"{status}: {emails.count_documents({'status': status})}")

#
# for doc in emails.find({"status": "rejected"}).limit(5):
#     print(doc)