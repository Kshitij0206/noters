import smtplib, random, re
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, render_template, request, flash, redirect, url_for, session,jsonify
from .models import User, OTP
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from dotenv import load_dotenv
import os
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from .models import User, OTP
from . import db, oauth
import random
from datetime import datetime
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Session expired. Please sign up again."})
        flash("Session expired. Please sign up again.", category='error')
        return redirect(url_for('auth.sign_up'))

    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        otp_obj = OTP.query.filter_by(email=temp['email'], purpose='signup') \
                           .order_by(OTP.created_at.desc()).first()

        # OTP expired or not found
        if not otp_obj or otp_obj.is_expired():
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "error", "message": "OTP expired. Please request a new one."})
            flash("OTP expired. Please request a new one.", category='error')
            return redirect(url_for('auth.sign_up'))

        # OTP match
        if entered_otp == otp_obj.otp:
            new_user = User(email=temp['email'],
                            first_name=temp['first_name'],
                            password=temp['password'])
            db.session.add(new_user)
            db.session.commit()

            # delete OTP record
            db.session.delete(otp_obj)
            db.session.commit()

            # remove signup temp data
            session.pop('signup_temp', None)

            # log in user
            login_user(new_user)

            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return jsonify({"status": "success"})
            flash("Account created successfully!", category='success')
            return redirect(url_for('views.home'))

        # OTP mismatch
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"status": "error", "message": "Invalid OTP."})
        flash("Invalid OTP.", category='error')

    # GET request → show OTP form page
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
@auth.route('/resend-otp', methods=['POST'])
def resend_otp():
    # Try to get email from signup or reset session
    if 'signup_temp' in session:
        email = session['signup_temp']['email']
        purpose = 'signup'
        first_name = session['signup_temp'].get('first_name', 'User')
    elif 'reset_email' in session:
        email = session['reset_email']
        purpose = 'reset'
        user = User.query.filter_by(email=email).first()
        first_name = user.first_name if user else 'User'
    else:
        return jsonify({"success": False, "message": "No email found in session"}), 400

    # Generate new OTP with cooldown check
    otp = generate_otp(email, purpose)
    if not otp:
        return jsonify({"success": False, "message": "Please wait 30 seconds before requesting another OTP"}), 429

    # Send email
    if send_email(email, "OTP - Noters", otp, purpose, first_name):
        return jsonify({"success": True, "message": "OTP resent successfully"})

    return jsonify({"success": False, "message": "Failed to send OTP"}), 500

# @auth.route('/login/google')
# def login_google():
#     redirect_uri = url_for('auth.auth_google_callback', _external=True)
#     return oauth.google.authorize_redirect(redirect_uri)

# # @auth.route('/auth/google/callback')
# # def auth_google_callback():
# #     token = oauth.google.authorize_access_token()
# #     user_info = oauth.google.parse_id_token(token)

# #     email = user_info.get('email')
# #     if not email:
# #         flash("Google login failed: email not available.", category="error")
# #         return redirect(url_for('auth.login'))

# #     user = User.query.filter_by(email=email).first()
# #     if not user:
# #         user = User(email=email,
# #                     first_name=user_info.get('given_name', ''),
# #                     password=generate_password_hash(random.token_urlsafe(16)))
# #         db.session.add(user)
# #         db.session.commit()

# #     login_user(user)
# #     flash("Logged in successfully with Google!", category="success")
# #     return redirect(url_for('views.home'))
from flask import current_app, redirect, url_for, flash, request
from flask_login import login_user
from . import db, oauth
from .models import User

@auth.route('/login/google')
def login_google():
    current_app.logger.debug("Starting Google OAuth login flow")
    redirect_uri = url_for('auth.google_callback', _external=True)
    current_app.logger.debug("Redirect URI for Google: %s", redirect_uri)
    return oauth.google.authorize_redirect(redirect_uri)

@auth.route('/auth/google/callback')
def google_callback():
    current_app.logger.debug("Google OAuth callback hit")
    current_app.logger.debug("Request args: %s", request.args)

    try:
        token = oauth.google.authorize_access_token()
        current_app.logger.debug("Access token received: %s", token)
    except Exception as e:
        current_app.logger.exception("Token exchange failed: %s", e)
        flash("Google login failed during token exchange", "error")
        return redirect(url_for('auth.login'))

    try:
        user_info = oauth.google.get('userinfo').json()
        current_app.logger.debug("User info from Google: %s", user_info)
    except Exception as e:
        current_app.logger.exception("Failed to fetch userinfo: %s", e)
        flash("Google login failed during user info retrieval", "error")
        return redirect(url_for('auth.login'))

    if not user_info:
        current_app.logger.error("No user_info returned from Google")
        flash("Google login returned no profile data", "error")
        return redirect(url_for('auth.login'))

    email = user_info.get('email')
    google_first = user_info.get('given_name')

    if not email:
        current_app.logger.error("Google profile missing email")
        flash("Google did not return an email address", "error")
        return redirect(url_for('auth.login'))

    # Check if user already exists
    user = User.query.filter_by(email=email).first()

    if user:
        if not user.first_name:
            user.first_name = google_first
            db.session.commit()
            current_app.logger.info("Updated first_name for existing user: %s", email)
    else:
        user = User(email=email, first_name=google_first, password=None)
        db.session.add(user)
        db.session.commit()
        current_app.logger.info("Created new user from Google login: %s", email)

    login_user(user)
    current_app.logger.info("Logged in user %s via Google", email)

    return redirect(url_for('views.home'))
