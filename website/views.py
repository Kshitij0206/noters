from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Note, User
from . import db
import json

views = Blueprint('views', __name__)

# Redirect root URL "/" to login page
@views.route('/')
def index():
    return redirect(url_for('auth.login'))

@views.route('/home', methods=['GET', 'POST'])  # Moved home route to /home instead of /
@login_required
def home():
    if request.method == 'POST':
        note_id = request.form.get('note_id')
        note_text = request.form.get('note')

        if len(note_text) < 1:
            flash('Note is too short!', category='error')
        elif note_id:  # Editing an existing note
            note = Note.query.get(note_id)
            if note and note.user_id == current_user.id:
                note.data = note_text
                db.session.commit()
                flash('Note updated successfully!', category='success')
            else:
                flash('Invalid note or permission denied.', category='error')
        else:  # Creating a new note
            new_note = Note(data=note_text, user_id=current_user.id)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')

    return render_template("home.html", user=current_user)

@views.route('/delete-note', methods=['POST'])
@login_required
def delete_note():
    note = json.loads(request.data)
    note_id = note['noteId']
    note = Note.query.get(note_id)
    if note and note.user_id == current_user.id:
        db.session.delete(note)
        db.session.commit()
        flash('Note deleted!', category='success')
    return jsonify({})

@views.route('/edit-note', methods=['POST'])
@login_required
def edit_note():
    data = request.get_json()
    note_id = data.get('noteId')
    new_content = data.get('content')

    note = Note.query.get(note_id)
    if note and note.user_id == current_user.id:
        note.data = new_content
        db.session.commit()
        return jsonify({"message": "Note updated successfully."}), 200
    return jsonify({"message": "Note not found or permission denied."}), 400

@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id
    user = User.query.get(user_id)
    if user:
        # Delete all notes by the user
        Note.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        flash('Account deleted successfully!', category='success')
        return redirect(url_for('auth.logout'))
    else:
        flash('Account deletion failed.', category='error')
    return redirect(url_for('auth.login'))  # Fixed incorrect reference
