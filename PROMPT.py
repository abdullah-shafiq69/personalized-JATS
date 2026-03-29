prompt = """You are a job application email parser. Analyze the email below and extract exactly three fields.

RULES:
- company: Extract the company name. If not explicitly stated, infer from the sender domain or email signature. If unknown, use "Unknown"
- position: Extract the exact job title applied to. If not stated, use "Unknown"  
- status: Classify as exactly one of: "rejected", "pending", or "interview"
  - "rejected": any rejection, regret, or "we went with other candidates" language
  - "interview": any invitation to chat, call, meet, or proceed to next step
  - "pending": acknowledgement emails, "we'll be in touch", or no clear decision

OUTPUT: Return only valid JSON, no explanation, no markdown, no code blocks:
{{"company": "xyz", "position": "engineer", "status": "rejected"}}

EMAIL:
{email_content}"""