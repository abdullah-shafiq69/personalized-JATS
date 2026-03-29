test_emails = [
    {
        "id": 1,
        "label": "Clear Rejection",
        "body": """Subject: Your application at Google

Hi Abdullah,

Thank you for taking the time to apply for the Software Engineer position at Google. 
After careful consideration, we have decided to move forward with other candidates 
whose experience more closely matches our current needs.

We wish you the best in your job search.

Best regards,
Sarah Mitchell
Google Recruiting Team"""
    },
    {
        "id": 2,
        "label": "Clear Interview Invite",
        "body": """Subject: Interview Invitation - ML Engineer Role

Hi Abdullah,

We were impressed by your application for the Machine Learning Engineer position 
at Anthropic. We'd love to schedule a technical interview at your earliest convenience.

Please use this link to book a 45-minute slot: calendly.com/anthropic-hiring

Looking forward to speaking with you.

James Lee
Talent Acquisition, Anthropic"""
    },
    {
        "id": 3,
        "label": "Pending / Acknowledgement",
        "body": """Subject: We received your application

Hi,

Thank you for applying to the Data Scientist role at Microsoft. Your application 
is currently under review. We will be in touch if your profile matches our requirements.

HR Team
Microsoft"""
    },
    {
        "id": 4,
        "label": "Tricky - Rejection disguised as positive",
        "body": """Subject: Thank you for your interest

Dear Candidate,

We truly enjoyed learning about your background and were impressed by your 
experience. However, after much deliberation, we have chosen to proceed with 
a candidate whose skills more closely align with our immediate needs.

We will keep your profile on file for future opportunities.

Regards,
Hiring Team
Meta"""
    },
    {
        "id": 5,
        "label": "Tricky - Interview but no company name",
        "body": """Subject: Next Steps

Hi Abdullah,

Hope you're doing well. We'd like to move you to the next round. 
Can you hop on a quick call this week? 

Let me know your availability.

Thanks,
Alex"""
    },
    {
        "id": 6,
        "label": "Automated ATS Acknowledgement",
        "body": """Subject: Application Received - Req #45821

This is an automated confirmation that your application for the 
position of Python Developer has been successfully submitted.

Your application ID is: APP-2024-45821
Expected review time: 2-3 weeks

Do not reply to this email.

TCS Recruitment System"""
    },
    {
        "id": 7,
        "label": "Rejection after interview",
        "body": """Subject: RE: Interview Follow Up

Hi Abdullah,

It was great speaking with you last week regarding the MLOps Engineer 
position here at Amazon. After discussing with the team, we've decided 
to move forward with another candidate at this time.

We appreciate the time you invested in our interview process.

Best,
David Chen
Amazon Web Services"""
    },
    {
        "id": 8,
        "label": "Ghosted then rejected months later",
        "body": """Subject: Your application from October

Dear Applicant,

We are writing regarding your application submitted in October 2024 
for the AI Engineer role. Due to a hiring freeze, we are closing 
all open positions and will not be moving forward with any candidates.

Thank you for your patience.

People Operations
Careem"""
    },
    {
        "id": 9,
        "label": "Tricky - Interview disguised as casual",
        "body": """Subject: Quick chat?

Hey,

Came across your profile and think you could be a great fit for 
what we're building at our startup. Nothing formal — just a 
casual coffee chat to see if there's a mutual fit.

You around this week?

Raza
CTO, Stealth Startup"""
    },
    {
        "id": 10,
        "label": "Rejection with feedback",
        "body": """Subject: Application Update - Data Engineer Position

Hi Abdullah,

Thank you for applying for the Data Engineer role at Arbisoft. While your 
ML background was impressive, we were looking for someone with stronger 
data pipeline and warehouse experience (Airflow, dbt, Snowflake).

We encourage you to apply again in the future as your skills develop.

Kind regards,
Hiring Committee
Arbisoft"""
    },
]


expected = [
    {"id": 1, "company": "Google",          "position": "Software Engineer",    "status": "rejected"},
    {"id": 2, "company": "Anthropic",       "position": "Machine Learning Engineer", "status": "interview"},
    {"id": 3, "company": "Microsoft",       "position": "Data Scientist",       "status": "pending"},
    {"id": 4, "company": "Meta",            "position": "Unknown",              "status": "rejected"},
    {"id": 5, "company": "Unknown",         "position": "Unknown",              "status": "interview"},
    {"id": 6, "company": "TCS",             "position": "Python Developer",     "status": "pending"},
    {"id": 7, "company": "Amazon",          "position": "MLOps Engineer",       "status": "rejected"},
    {"id": 8, "company": "Careem",          "position": "AI Engineer",          "status": "rejected"},
    {"id": 9, "company": "Unknown",         "position": "Unknown",              "status": "interview"},
    {"id": 10, "company": "Arbisoft",       "position": "Data Engineer",        "status": "rejected"},
]
