import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from .models import User
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
import os # Added for environment variables

auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            if check_password_hash(user.password, password):
                flash('Logged in successfully!', category='success')
                login_user(user, remember=True)
                return redirect(url_for('views.home'))
            else:
                flash('Incorrect password, try again.', category='error')
        else:
            flash('Email does not exist.', category='error')

    return render_template("login.html", user=current_user)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@auth.route('/sign-up', methods=['GET', 'POST'])
def sign_up():
    otp_sent = False

    # Load sender credentials from environment variables (recommended)
    # Fallback to hardcoded values for demonstration, but not for production
    sender_email = os.environ.get('SENDER_EMAIL', 'kshitijcodes7@gmail.com')
    sender_password = os.environ.get('SENDER_PASSWORD', 'hgtkohaniqxwpguo') # Replace with your actual App Password

    if request.method == 'POST':
        email = request.form.get('email')
        first_name = request.form.get('firstName')
        password1 = request.form.get('password1')
        password2 = request.form.get('password2')
        entered_otp = request.form.get('otp')

        user = User.query.filter_by(email=email).first()

        # First submission without OTP -> generate and email OTP
        if not entered_otp:
            if user:
                flash('Email already exists.', category='error')
            elif len(email) < 4:
                flash('Email must be greater than 4 characters.', category='error')
            elif len(first_name) < 2:
                flash('First name must be greater than 1 character.', category='error')
            elif password1 != password2:
                flash('Passwords do not match.', category='error')
            elif len(password1) < 7:
                flash('Password must be at least 7 characters.', category='error')
            else:
                otp = str(random.randint(100000, 999999))
                session['temp_user'] = {
                    'email': email,
                    'first_name': first_name,
                    'password': generate_password_hash(password1, method='pbkdf2:sha256'),
                    'otp': otp
                }

                # Send OTP via email
                subject = "Email Verification OTP"
                body = f"Hello {first_name},\n\nYour OTP for sign-up is: {otp}\n\nThank you!"

                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = email
                msg['Subject'] = subject
                msg.attach(MIMEText(body, 'plain'))

                try:
                    server = smtplib.SMTP('smtp.gmail.com', 587)
                    server.starttls()
                    server.login(sender_email, sender_password)
                    server.sendmail(sender_email, email, msg.as_string())
                    server.quit()
                    flash('OTP sent to your email address. Enter it below to complete sign-up.', category='info')
                    otp_sent = True
                except Exception as e:
                    flash(f'Failed to send OTP: {e}', category='error')

                return render_template("sign-up.html", user=current_user, email=email,
                                       firstName=first_name, otp_sent=otp_sent)

        # Second submission with OTP entered
        elif entered_otp:
            temp_user = session.get('temp_user')
            if not temp_user:
                flash('Session expired. Please fill the form again.', category='error')
                return redirect(url_for('auth.sign_up'))

            if temp_user['email'] != email:
                flash('Email mismatch. Start again.', category='error')
                return redirect(url_for('auth.sign_up'))

            if temp_user['otp'] == entered_otp:
                new_user = User(
                    email=temp_user['email'],
                    first_name=temp_user['first_name'],
                    password=temp_user['password']
                )
                db.session.add(new_user)
                db.session.commit()
                session.pop('temp_user', None)
                login_user(new_user, remember=True)
                flash('Account created and verified!', category='success')
                return redirect(url_for('views.home'))
            else:
                flash('Invalid OTP. Please try again.', category='error')
                otp_sent = True
                return render_template("sign-up.html", user=current_user, email=email,
                                       firstName=first_name, otp_sent=otp_sent)

    return render_template("sign-up.html", user=current_user)

@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    # Load sender credentials from environment variables (recommended)
    sender_email = os.environ.get('SENDER_EMAIL', 'kshitijcodes7@gmail.com')
    sender_password = os.environ.get('SENDER_PASSWORD', 'hgtkohaniqxwpguo') # Replace with your actual App Password

    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            otp = str(random.randint(100000, 999999))
            session['reset_otp'] = otp
            session['reset_email'] = email

            # Send OTP
            subject = "Password Reset OTP"
            body = f"Your OTP for resetting the password is: {otp}"

            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            try:
                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(sender_email, sender_password)
                server.sendmail(sender_email, email, msg.as_string())
                server.quit()
                flash('OTP sent to your email.', category='info')
                return redirect(url_for('auth.reset_password'))
            except Exception as e:
                flash(f'Failed to send OTP: {e}', category='error')
        else:
            flash('Email not found.', category='error')

    return render_template('forgot_password.html', user=current_user)

@auth.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        entered_otp = request.form.get('otp')
        new_password1 = request.form.get('password1')
        new_password2 = request.form.get('password2')
        session_email = session.get('reset_email')
        session_otp = session.get('reset_otp')

        if not session_email or not session_otp:
            flash('Session expired. Try again.', category='error')
            return redirect(url_for('auth.forgot_password'))

        if entered_otp != session_otp:
            flash('Incorrect OTP.', category='error')
        elif new_password1 != new_password2:
            flash('Passwords do not match.', category='error')
        elif len(new_password1) < 7:
            flash('Password must be at least 7 characters.', category='error')
        else:
            user = User.query.filter_by(email=session_email).first()
            if user:
                user.password = generate_password_hash(new_password1, method='pbkdf2:sha256')
                db.session.commit()
                session.pop('reset_otp', None)
                session.pop('reset_email', None)
                flash('Password reset successful! Please log in.', category='success')
                return redirect(url_for('auth.login'))
    
    return render_template('reset_password.html', user=current_user)
