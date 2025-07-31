from . import db
from flask_login import UserMixin
from sqlalchemy.sql import func


from werkzeug.security import generate_password_hash, check_password_hash

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Text)
    date = db.Column(db.DateTime(timezone=True), default=func.now())
    last_updated = db.Column(db.DateTime(timezone=True), default=func.now(), onupdate=func.now())
    bg_color = db.Column(db.String(20))
    tags = db.Column(db.String(100))
    is_pinned = db.Column(db.Boolean, default=False)
    is_completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    summary = db.Column(db.Text, nullable=True)


    # NEW fields for password lock
    password_hash = db.Column(db.String(128), nullable=True)
    is_locked = db.Column(db.Boolean, default=False)

    versions = db.relationship('NoteVersion', backref='note', cascade='all, delete-orphan')

    # Optional helper methods to set/check password
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.is_locked = True if password else False

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class NoteVersion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    note_id = db.Column(db.Integer, db.ForeignKey('note.id', ondelete='CASCADE'), nullable=False)
    version_data = db.Column(db.Text)
    timestamp = db.Column(db.DateTime(timezone=True), default=func.now())

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    first_name = db.Column(db.String(150), nullable=False)
    notes = db.relationship('Note', backref='user', cascade='all, delete-orphan')