import smtplib, random, re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from .models import User, OTP
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os

load_dotenv()

SENDER_EMAIL = os.getenv('SENDER_EMAIL')  # no-reply@noters.online
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')  # GoDaddy email password
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.secureserver.net')
SMTP_PORT = int(os.getenv('SMTP_PORT', 465))  # 465 for SSL, 587 for TLS

auth = Blueprint('auth', __name__)

if not SENDER_EMAIL or not SENDER_PASSWORD:
    raise ValueError("Missing email credentials in environment variables.")

# Utility: Email validation
def is_valid_email(email):
    return re.match(r"^[^@]+@[^@]+\.[^@]+$", email) is not None

# Utility: Send email using GoDaddy SMTP
def send_email(to_email, subject, otp, action, recipient_name):
    """
    Sends a formatted OTP email via GoDaddy SMTP.
    """
    body = f"""Hello {recipient_name},

Your OTP for {action} is: {otp}.

Sincerely,  
Noters Team.
"""

    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP_SSL("smtpout.secureserver.net", 465)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!")
        return True
    except Exception as e:
        print("Email send error:", e)
        return False

# Utility: Generate OTP
def generate_otp(email, purpose):
    last_otp = OTP.query.filter_by(email=email, purpose=purpose).order_by(OTP.created_at.desc()).first()
    if last_otp and (datetime.utcnow() - last_otp.created_at).total_seconds() < 30:
        flash("Please wait 30 seconds before requesting another OTP.", category="error")
        return None

    otp = str(random.randint(100000, 999999))
    db.session.add(OTP(email=email, otp=otp, purpose=purpose))
    db.session.commit()
    return otp

# Login
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=True)
            flash('Logged in successfully!', category='success')
            return redirect(url_for('views.home'))
        elif user:
            flash('Incorrect password.', category='error')
        else:
            flash('Email not found.', category='error')
    return render_template("login.html", user=current_user)

# Logout
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

# Step 1: Sign-up → Request OTP
@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')

        if not is_valid_email(email):
            flash('Invalid email format.', category='error')
        elif User.query.filter_by(email=email).first():
            flash('Email already exists.', category='error')
        elif len(first_name) < 2:
            flash('First name too short.', category='error')
        elif password1 != password2:
            flash('Passwords do not match.', category='error')
        elif len(password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            otp = generate_otp(email, 'signup')
            if otp:
                if send_email(email, "Sign-Up OTP - Noters", otp, "creating your account", first_name):
                    session['signup_temp'] = {
                        'email': email,
                        'first_name': first_name,
                        'password': generate_password_hash(password1)
                    }
                    return redirect(url_for('auth.verify_signup_otp'))
    return render_template("sign-up.html", user=current_user)

# Step 2: Verify OTP
@auth.route('/verify-sign-up-otp', methods=['GET', 'POST'])
def verify_signup_otp():
    temp = session.get('signup_temp')
    if not temp:
        flash("Session expired. Please sign up again.", category='error')
        return redirect(url_for('auth.sign_up'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        otp_obj = OTP.query.filter_by(email=temp['email'], purpose='signup').order_by(OTP.created_at.desc()).first()

        if not otp_obj or otp_obj.is_expired():
            flash("OTP expired. Please request a new one.", category='error')
            return redirect(url_for('auth.sign_up'))

        if entered_otp == otp_obj.otp:
            new_user = User(email=temp['email'], first_name=temp['first_name'], password=temp['password'])
            db.session.add(new_user)
            db.session.commit()
            db.session.delete(otp_obj)
            db.session.commit()
            session.pop('signup_temp')
            login_user(new_user)
            flash("Account created successfully!", category='success')
            return redirect(url_for('views.home'))
        else:
            flash("Invalid OTP.", category='error')

    return render_template("verify_signup_otp.html", email=temp['email'], user=current_user)

# Forgot password → request OTP
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if not is_valid_email(email):
            flash("Invalid email format.", category='error')
        elif not user:
            flash("Email not found.", category='error')
        else:
            otp = generate_otp(email, 'reset')
            if otp and send_email(email, "Password Reset OTP - Noters", otp, "resetting your password", user.first_name):
                session['reset_email'] = email
                return redirect(url_for('auth.reset_password'))
    return render_template('forgot_password.html', user=current_user)

# Reset password
@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        flash("Session expired. Please try again.", category='error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        new_password1 = request.form.get('password1')
        new_password2 = request.form.get('password2')

        otp_obj = OTP.query.filter_by(email=email, purpose='reset').order_by(OTP.created_at.desc()).first()

        if not otp_obj or otp_obj.is_expired():
            flash("OTP expired. Request a new one.", category='error')
            return redirect(url_for('auth.forgot_password'))

        if entered_otp != otp_obj.otp:
            flash("Invalid OTP.", category='error')
        elif new_password1 != new_password2:
            flash("Passwords do not match.", category='error')
        elif len(new_password1) < 7:
            flash("Password must be at least 7 characters.", category='error')
        else:
            user = User.query.filter_by(email=email).first()
            user.password = generate_password_hash(new_password1)
            db.session.commit()
            db.session.delete(otp_obj)
            db.session.commit()
            session.pop('reset_email')
            flash("Password reset successfully! Please log in.", category='success')
            return redirect(url_for('auth.login'))

    return render_template('reset_password.html', user=current_user)
