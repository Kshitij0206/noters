import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Blueprint, render_template, request, flash, redirect, url_for, session
from .models import User
from . import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user

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
                sender_email = 'kshitijcodes7@gmail.com'
                sender_password = 'hgtkohaniqxwpguo'
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
