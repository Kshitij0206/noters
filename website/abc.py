import smtplib

try:
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('gkshitij0206@gmail.com', 'foub fxlr steq lvju')  # Use App Password
    print("SMTP server connection successful!")
except Exception as e:
    print(f"SMTP error: {e}")
