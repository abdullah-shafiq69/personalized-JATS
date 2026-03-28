from openai import OpenAI
from load_dotenv import load_dotenv
import os, time
load_dotenv()

API_KEY = os.getenv("API_KEY")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

email = """
Hi Abdullah

Thank you for applying for the job advert position at Thingtrax.
We’ve received your application and our team will review it shortly.

Please respond with your availability so we can schedule for our interview.

Thank you for your interest in joining Thingtrax, and we appreciate the time you took to apply.

Best regards,

Human Resource Department
Thingtrax



https://thingtrax.com"""

PROMPT = """below is an email i received from a company/recuiter that i applied to i want u to extract name
            of company the position applied to and classify into one of three (rejected, pending, called for
            interview) based on the contents of the mail output should be in the following format: {company: xyz, position: engineer, status: rejected}
            below is the mail""" + "\n" + email


t0 = time.time()
response = client.chat.completions.create(
    model="stepfun/step-3.5-flash:free",
    messages=[
        {"role": "user", "content": PROMPT}
    ]
)

print(response.choices[0].message.content, "\n", time.time()-t0)