from groq import Groq
from load_dotenv import load_dotenv
import os, time
from PROMPT import prompt
from test_emails import test_emails

load_dotenv()

API_KEY = os.getenv("GROQ_KEY")

client = Groq(
    api_key=API_KEY,
)
def classify(email):
    t0 = time.time()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=150,
        messages=[
            {"role": "user", "content": prompt.format(email_content=email)}
        ]
    )

    return response.choices[0].message.content, time.time()-t0



for email in test_emails:
    print(f"\n--- Test {email['id']}: {email['label']} ---")
    result, _ = classify(email["body"])  # your function
    print(result, _)
    time.sleep(4)