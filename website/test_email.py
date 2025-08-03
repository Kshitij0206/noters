import smtplib
from email.mime.text import MIMEText

# --- CONFIG ---
SENDER_EMAIL = "no-reply@noters.online"
SENDER_PASSWORD = "Noters@1501"
SMTP_SERVER = "smtpout.secureserver.net"
SMTP_PORT = 465  # Use 465 for SSL

# --- EMAIL ---
TO_EMAIL = "gkshitij0206@gmail.com"
SUBJECT = "SMTP Test"
BODY = "If you received this email, GoDaddy SMTP is working!"

# Create message
msg = MIMEText(BODY)
msg["From"] = SENDER_EMAIL
msg["To"] = TO_EMAIL
msg["Subject"] = SUBJECT

try:
    # Connect with SSL
    server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    server.sendmail(SENDER_EMAIL, TO_EMAIL, msg.as_string())
    server.quit()
    print("✅ Email sent successfully!")
except Exception as e:
    print("❌ Email send error:", e)
