from flask import Flask, request, jsonify
import os
from openai import OpenAI
import sendgrid
from sendgrid.helpers.mail import Mail
import traceback

app = Flask(__name__)

# === API KEYS (set in Replit Secrets or your environment) ===
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# === Admin QA Email Recipients ===
ADMIN_EMAILS = [
    "roy.flores0226@gmail.com",
    "rsptaurus21@gmail.com",
    "georgemccleary@gmail.com"
]

# === Verified From Email in SendGrid ===
FROM_EMAIL = "support@titlefrauddefender.com"

# === Toggle: Set to True to send replies to customers ===
SEND_TO_CUSTOMER = False

# === Initialize OpenAI client ===
client = OpenAI(api_key=OPENAI_API_KEY)

@app.route('/', methods=['GET'])
def health_check():
    return "✅ Webhook Flask API is running. Use POST /webhook to receive data."

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json() or {}
        print("RAW PAYLOAD RECEIVED FROM GHL:", data)

        message_body = data.get("message", {}).get("body")
        contact_email = data.get("email")
        contact_name = data.get("full_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip()
        first_name_only = contact_name.split()[0] if contact_name else "there"

        if not message_body or not contact_email:
            return jsonify({"error": "Missing message body or contact email"}), 400

        # Generate AI response
        ai_response = generate_ai_reply(message_body, first_name_only)

        # === Choose email content based on toggle ===
        if SEND_TO_CUSTOMER:
            # Plain reply for customers with signature included
            email_body = ai_response
        else:
            # Detailed format for internal QA
            email_body = f"""
=== AI Generated Reply ===

{ai_response}

--- Original Message Info ---
Name: {contact_name}
Email: {contact_email}
Message:
{message_body}
"""

        # Choose recipients and subject
        recipients = [contact_email] if SEND_TO_CUSTOMER else ADMIN_EMAILS
        subject = f"Title Fraud Defender Response for {first_name_only}"
        send_emails(recipients, subject, email_body)

        return jsonify({
            "status": "Reply processed",
            "sent_to": recipients
        }), 200

    except Exception:
        error_msg = traceback.format_exc()
        print("Exception occurred:\n", error_msg)
        return jsonify({"error": error_msg}), 500


def generate_ai_reply(user_msg, first_name):
    prompt = f"""
You are a helpful assistant for Title Fraud Defender.

Your job is to respond professionally and clearly to customer inquiries about title fraud protection services.

Always:
- Begin your response with a personalized greeting using the customer's first name (e.g., "Hi {first_name},")
- End the message with the following exact signature (always, without exception):

Best regards,
Title Fraud Defender Support

Important: Do not leave a blank or request someone else to sign. You, the assistant, must always close with the exact signature above.

Background: Title Fraud Defender monitors property title records, alerts homeowners to suspicious activity, and gives peace of mind through early detection of title fraud.

Customer message:
{user_msg}
"""
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for Title Fraud Defender."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=300
    )
    return response.choices[0].message.content.strip()


def send_emails(recipients, subject, content):
    sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
    for email in recipients:
        mail = Mail(
            from_email=FROM_EMAIL,
            to_emails=email,
            subject=subject,
            plain_text_content=content
        )
        resp = sg.send(mail)
        print(f"Email sent to {email}: {resp.status_code}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
