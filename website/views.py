# views.py
from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Note, User
from . import db
import json
import logging # Added for logging

# Configure logging (can be done once in __init__.py or a config file)
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

views = Blueprint('views', __name__)

# Redirect root URL "/" to login page if not logged in
@views.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    return redirect(url_for('auth.login'))

@views.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        note_id = request.form.get('note_id')
        note_text = request.form.get('note')

        if not note_text or len(note_text.strip()) < 1:
            flash('Note is too short!', category='error')

        elif note_id and note_id.strip() != "":
            # Editing existing note
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                note.data = note_text
                db.session.commit()
                flash('Note updated!', category='success')
            else:
                flash('Note not found or permission denied.', category='error')

        else:
            # Adding new note (note_id is empty or invalid)
            new_note = Note(data=note_text, user_id=current_user.id)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')

    # Serialize notes as JSON for JS
    notes_json = [{'id': note.id, 'data': note.data} for note in current_user.notes]

    return render_template("home.html", user=current_user, notes_json=notes_json)


@views.route('/delete-note', methods=['POST'])
@login_required
def delete_note():
    try:
        data = json.loads(request.data)
        note_id = data.get('noteId')
        note = Note.query.get(int(note_id))
        if note and note.user_id == current_user.id:
            db.session.delete(note)
            db.session.commit()
            print("Note deleted!")
            return jsonify({'message': 'Note deleted'})
        else:
            return jsonify({'message': 'Note not found or permission denied'}), 403
    except Exception as e:
        logging.error(f"Error deleting note: {e}")
        return jsonify({'message': 'Server error'}), 500

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
    return redirect(url_for('auth.login'))
