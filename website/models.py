# --- MODELS.PY ---
from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    bg_color = db.Column(db.String(20))
    tags = db.Column(db.String(100))  # New
    is_pinned = db.Column(db.Boolean, default=False)  # New
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    notes = db.relationship('Note')