# __init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from os import path
from flask_login import LoginManager
from datetime import datetime
import pytz
from dotenv import load_dotenv
import os
from authlib.integrations.flask_client import OAuth

oauth = OAuth()
# Load environment variables
load_dotenv()
GOOGLE_CLIENT_ID = os.getenv('client_id')
GOOGLE_CLIENT_SECRET = os.getenv('client_secret')
# Initialize database
db = SQLAlchemy()
DB_NAME = "database.db"

# Initialize OAuth globally so it's accessible everywhere


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'sjgsfjhsdjkdsgh'
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_NAME}'
    db.init_app(app)

    # Initialize OAuth with app
    oauth.init_app(app)

    # Register Google OAuth
    oauth.register(
    name='google',
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    access_token_url='https://oauth2.googleapis.com/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    api_base_url='https://openidconnect.googleapis.com/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid email profile'},
)



    # Register Blueprints
    from .views import views
    from .auth import auth
    app.register_blueprint(views, url_prefix='/')
    app.register_blueprint(auth, url_prefix='/')

    # Initialize Database
    from .models import User, Note
    create_database(app)

    # Login Manager Setup
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(id):
        return User.query.get(int(id))

    # ✅ Custom Jinja Filter: IST Timezone
    @app.template_filter('ist')
    def ist(dt):
        if not dt:
            return ''
        utc = dt.replace(tzinfo=pytz.utc)
        ist_time = utc.astimezone(pytz.timezone('Asia/Kolkata'))
        return ist_time.strftime('%d %b %Y %H:%M')

    # ✅ Custom Jinja Filter: Time Ago
    @app.template_filter('time_ago')
    def time_ago(dt):
        if not dt:
            return "unknown"
        now = datetime.utcnow().replace(tzinfo=pytz.utc)
        diff = now - (dt if dt.tzinfo else dt.replace(tzinfo=pytz.utc))

        seconds = diff.total_seconds()
        minutes = int(seconds // 60)
        hours = int(minutes // 60)
        days = int(hours // 24)

        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif minutes < 60:
            return f"{minutes} minutes ago"
        elif hours < 24:
            return f"{hours} hours ago"
        elif days < 7:
            return f"{days} days ago"
        else:
            return dt.strftime('%d %b %Y')

    return app

def create_database(app):
    db_path = path.join(app.root_path, DB_NAME)
    if not path.exists(db_path):
        with app.app_context():
            db.create_all()
        print("✅ Created Database!")
