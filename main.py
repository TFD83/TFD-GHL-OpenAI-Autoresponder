from flask import Flask, request, jsonify
import os
from openai import OpenAI
import sendgrid
from sendgrid.helpers.mail import Mail
import traceback

app = Flask(__name__)

# === API KEYS (set in environment or secrets) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# === Admin QA Recipients ===
ADMIN_EMAILS = [
    "roy.flores0226@gmail.com",
    "rsptaurus21@gmail.com",
    "georgemccleary@gmail.com",
]

# === Verified From Email (SendGrid) ===
FROM_EMAIL = "support@titlefrauddefender.com"

# === Toggle: True → send to customer | False → QA only ===
SEND_TO_CUSTOMER = False

# === OpenAI client (v1.x) ===
client = OpenAI(api_key=OPENAI_API_KEY)

# =============================================================
# PROMPT CONFIGURATION (edit only these two blocks)
# =============================================================
# -- 1) BEHAVIOR SECTION --
AI_BEHAVIOR = """
You are a helpful, professional support agent for Title Fraud Defender.

Always:
- Open with a personalized greeting ("Hi {first_name},")
- End with the following signature (always, without exception):

Best regards,
Title Fraud Defender Support

Tone and Approach:
- Professional and respectful, appropriate for communication with county officials.
- Persuasive but not pushy – focused on educating and offering a helpful solution.
- Emphasizes community protection, public trust, and proactive governance.

Write with clarity and warmth, aiming for ~3‑5 short paragraphs.
"""

# -- 2) KNOWLEDGE BASE SECTION --
KNOWLEDGE_BASE = """
Title Fraud Defender (TFD) – County Official FAQ Knowledge Base

Primary Goal:
To write responses to emails from county officials with the aim of convincing them to take steps to protect their constituents from title fraud.

Key Messaging Focus:
- Title fraud is a real and growing threat to homeowners.
- Homeowners are often unaware of the risk until it’s too late.
- Counties can play a proactive role in protecting residents.
- The solution is Title Fraud Defender (TFD) – a low‑cost technology that offers peace of mind and protection.

About Title Fraud Defender (TFD):
- A software solution designed to monitor and alert homeowners of suspicious activity related to the title of their property.
- Easy to implement and low‑cost, especially compared to the financial and emotional toll of title fraud.
- Offers early detection and alerts, enabling homeowners to respond quickly.

Overview:
TFD is a low-cost technology solution designed to protect homeowners from title fraud. It monitors property records and alerts owners when suspicious or unauthorized changes occur. The goal is to help counties provide a proactive defense for their constituents.

FAQs:

1. What is title fraud, and why should counties be concerned?
- Title fraud involves criminals forging documents to transfer ownership of a home without the owner's knowledge.
- Counties should care because it undermines trust in public records and often results in legal headaches for constituents and clerks.

2. What is Title Fraud Defender (TFD)?
- A proactive, affordable platform that notifies homeowners of changes to their property title.
- Helps prevent fraud before it becomes financially or legally damaging.

3. What are the steps to implementing TFD in a county?
- Step 1: Learn About the Platform
  - Request a demo or receive technical information about TFD.
- Step 2: Get Stakeholder Buy-In
  - Present to commissioners, recorders, or other decision-makers.
- Step 3: Formalize Partnership
  - Sign a non-binding agreement or MOU.
- Step 4: Launch Public Awareness Campaign
  - Share information with homeowners via websites, tax mailings, or events.
- Step 5: Monitor and Report
  - Evaluate effectiveness and share results with stakeholders.

4. How much does TFD cost?
- Pricing is low and flexible.
- Counties can either sponsor the service or allow homeowners to opt in for a small fee.

5. Does TFD replace or interfere with existing systems?
- No. TFD complements existing public record systems.
- It operates as a passive monitor, requiring no major system changes.

6. What support is provided during implementation?
- Full onboarding and training for staff.
- Public outreach materials and ongoing technical support.
- Usage metrics and performance tracking.

7. How do we get started?
- County officials can reply to our outreach email or contact us directly.
- A no-obligation demo or informational call can be arranged quickly.

Main Benefits:
- Protects residents from a growing type of fraud.
- Boosts public trust in local government.
- Easy to implement and maintain.
"""
# =============================================================

@app.route("/", methods=["GET"])
def health_check():
    return "✅ Webhook live. POST ➜ /webhook"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json(force=True) or {}
        print("RAW PAYLOAD:", data)

        body = data.get("message", {}).get("body")
        contact_email = data.get("email")
        contact_name = data.get("full_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        first_name = contact_name.split()[0] if contact_name else "there"

        if not body or not contact_email:
            return jsonify({"error": "Missing body or email"}), 400

        ai_reply = generate_ai_reply(body, first_name)

        # -------- email assembly --------
        if SEND_TO_CUSTOMER:
            email_body = ai_reply  # plain for customer
            recipients = [contact_email]
        else:
            email_body = f"""=== AI Generated Reply ===\n\n{ai_reply}\n\n--- Original Message ---\n{body}\n"""
            recipients = ADMIN_EMAILS

        subject = f"Title Fraud Defender Response for {first_name}"
        send_emails(recipients, subject, email_body)
        return jsonify({"status": "sent", "recipients": recipients}), 200

    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Server error"}), 500


def generate_ai_reply(customer_msg: str, first_name: str) -> str:
    """Call OpenAI with clearly segmented prompt."""
    prompt = f"""
### BEHAVIOR
{AI_BEHAVIOR}

### KNOWLEDGE BASE
{KNOWLEDGE_BASE}

### PARAMETERS
first_name = {first_name}

### CUSTOMER MESSAGE
{customer_msg}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=350,
    )
    return response.choices[0].message.content.strip()


def send_emails(recipients, subject, content):
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    for r in recipients:
        resp = sg.send(Mail(from_email=FROM_EMAIL, to_emails=r, subject=subject, plain_text_content=content))
        print(f"Email ➜ {r} status {resp.status_code}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
