# views.py
from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for
from flask_login import login_required, current_user
from .models import Note, User
from . import db
import json
import logging

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
        note_bg = request.form.get('note_bg') or 'white'

        if not note_text or len(note_text.strip()) < 1:
            flash('Note is too short!', category='error')

        elif note_id and note_id.strip() != "":
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                note.data = note_text
                note.bg_color = note_bg
                db.session.commit()
                flash('Note updated!', category='success')
            else:
                flash('Note not found or permission denied.', category='error')

        else:
            new_note = Note(data=note_text, bg_color=note_bg, user_id=current_user.id)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')

    # Handle edit redirect from saved_notes
    edit_id = request.args.get('edit')
    edit_note = None
    if edit_id:
        note = Note.query.get(int(edit_id))
        if note and note.user_id == current_user.id:
            edit_note = {
                'id': note.id,
                'data': note.data,
                'bg_color': note.bg_color or 'white'
            }

    notes_json = [{'id': n.id, 'data': n.data, 'bg_color': n.bg_color} for n in current_user.notes]
    return render_template("home.html", user=current_user, notes_json=notes_json, edit_note=edit_note)

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
        Note.query.filter_by(user_id=user_id).delete()
        db.session.delete(user)
        db.session.commit()
        flash('Account deleted successfully!', category='success')
        return redirect(url_for('auth.logout'))
    else:
        flash('Account deletion failed.', category='error')
        return redirect(url_for('auth.login'))
@views.route('/saved-notes')
@login_required
def saved_notes():
    notes = current_user.notes
    notes_json = [
        {
            'id': note.id,
            'data': note.data,
            'bg_color': note.bg_color or 'white'
        }
        for note in notes
    ]
    return render_template(
        'saved_notes.html',
        notes=notes,
        notes_json=notes_json,
        user=current_user
    )
