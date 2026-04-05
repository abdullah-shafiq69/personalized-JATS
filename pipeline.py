import re, json, asyncio, os
from groq import AsyncGroq
from dotenv import load_dotenv
from db import is_seen, insert_email

load_dotenv()

client = AsyncGroq(api_key=os.getenv("GROQ_KEY"))

BATCH_SIZE   = 10
WAIT_SECONDS = 61
MAX_RETRIES  = 3


def parse_json_object(raw):
    raw = re.sub(r"```json|```", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found")
    return json.loads(raw[start:end])


async def classify_single(e, model="llama-3.1-8b-instant"):
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

            if is_rate_limit:
                print(f"  ⚠ Unexpected 429 [{e['subject'][:35]}]")
                return None

            if attempt < MAX_RETRIES:
                wait = 2 ** attempt
                print(f"  ↺ Retry in {wait}s [{e['subject'][:35]}]")
                await asyncio.sleep(wait)
            else:
                print(f"  ✗ Gave up [{e['subject'][:35]}]")
                return None


async def run_pipeline(emails_list):
    """
    Takes a list of email dicts, skips already-seen ones,
    classifies in batches, stores to MongoDB.
    """
    # filter out already stored
    new_emails = [e for e in emails_list if not is_seen(e["message_id"])]
    total = len(new_emails)

    if total == 0:
        print("  Nothing new to classify.")
        return

    batches       = [new_emails[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    total_batches = len(batches)
    print(f"  Classifying {total} emails in {total_batches} batches...")

    for i, batch in enumerate(batches):
        print(f"  Batch {i+1}/{total_batches} — {len(batch)} requests...")

        for e in batch:
            result = await classify_single(e)
            if result:
                insert_email(
                    message_id = e["message_id"],
                    subject    = e["subject"],
                    sender     = e["sender"],
                    company    = result.get("company") or "Unknown",
                    position   = result.get("position") or "Unknown",
                    status     = result.get("status", "error"),
                )

        if i < total_batches - 1:
            print(f"  ⏳ Waiting {WAIT_SECONDS}s...")
            await asyncio.sleep(WAIT_SECONDS)

    print(f"  Pipeline done. {total} emails processed.")