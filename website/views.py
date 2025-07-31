from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, send_file, Response, session
from flask_login import login_required, current_user
from .models import Note, User, NoteVersion
from . import db
import json, io
from xhtml2pdf import pisa
from datetime import datetime
import pytz

views = Blueprint('views', __name__)

@views.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    return redirect(url_for('auth.login'))

@views.route('/toggle-dark-mode')
def toggle_dark_mode():
    current = session.get('dark_mode', False)
    session['dark_mode'] = not current
    return redirect(request.referrer or url_for('views.home'))

from werkzeug.security import generate_password_hash, check_password_hash

@views.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        note_id = request.form.get('note_id')
        note_text = request.form.get('note')
        note_bg = request.form.get('note_bg') or 'white'
        tags = request.form.get('tags') or ''
        is_pinned = 'is_pinned' in request.form
        is_completed = 'is_completed' in request.form
        password = request.form.get('password', '').strip()

        if not note_text or len(note_text.strip()) < 1:
            flash('Note is too short!', category='error')
        elif note_id:  # Edit note
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                old_version = NoteVersion(note_id=note.id, version_data=note.data)
                db.session.add(old_version)

                note.data = note_text
                note.bg_color = note_bg
                note.tags = tags
                note.is_pinned = is_pinned
                note.is_completed = is_completed
                note.last_updated = datetime.utcnow()

                if password:
                    note.set_password(password)
                else:
                    # Do not unlock the note unless it was never locked
                    if not note.password_hash:
                        note.is_locked = False

                db.session.commit()
                flash('Note updated!', category='success')
                return redirect(url_for('views.home'))
            else:
                flash('Note not found or permission denied.', category='error')
        else:  # New note
            new_note = Note(
                data=note_text,
                bg_color=note_bg,
                user_id=current_user.id,
                tags=tags,
                is_pinned=is_pinned,
                is_completed=is_completed,
                last_updated=datetime.utcnow()
            )
            if password:
                new_note.set_password(password)
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')
            return redirect(url_for('views.home'))

    # GET Method
    edit_id = request.args.get('edit')
    edit_note = None
    if edit_id:
        edit_note = Note.query.get(int(edit_id))
        if not edit_note or edit_note.user_id != current_user.id:
            flash('Note not found or permission denied.', category='error')
            return redirect(url_for('views.home'))

    # Convert dates to IST
    ist = pytz.timezone('Asia/Kolkata')
    for note in current_user.notes:
        note.date = note.date.astimezone(ist)
        note.last_updated = note.last_updated.astimezone(ist)

    notes_json = [{'id': n.id, 'data': n.data, 'bg_color': n.bg_color or 'white'} for n in current_user.notes]

    return render_template("home.html", user=current_user, notes_json=notes_json, edit_note=edit_note, dark_mode=session.get('dark_mode', False))

@views.route('/saved-notes')
@login_required
def saved_notes():
    sort = request.args.get('sort', 'pinned_date')
    tag_filter = request.args.get('tag')
    query = Note.query.filter_by(user_id=current_user.id)

    if tag_filter:
        query = query.filter(Note.tags.ilike(f"%{tag_filter}%"))

    if sort == 'title_asc':
        notes = query.order_by(Note.is_pinned.desc(), Note.data.asc()).all()
    elif sort == 'title_desc':
        notes = query.order_by(Note.is_pinned.desc(), Note.data.desc()).all()
    elif sort == 'date_asc':
        notes = query.order_by(Note.is_pinned.desc(), Note.date.asc()).all()
    else:
        notes = query.order_by(Note.is_pinned.desc(), Note.date.desc()).all()

    ist = pytz.timezone('Asia/Kolkata')
    for note in notes:
        note.date = note.date.astimezone(ist)
        note.last_updated = note.last_updated.astimezone(ist)

    all_tags = set()
    for note in notes:
        if note.tags:
            all_tags.update(tag.strip() for tag in note.tags.split(',') if tag.strip())

    notes_json = []
    for n in notes:
        try:
            delta = json.loads(n.data)
            if isinstance(delta, dict) and 'ops' in delta:
                preview = ''.join(op.get('insert', '') for op in delta.get('ops', []))
                note_data = delta
            else:
                raise ValueError("Invalid Delta format")
        except Exception:
            preview = n.data
            note_data = {'ops': [{'insert': preview}]}

        notes_json.append({
            'id': n.id,
            'data': note_data,
            'bg_color': n.bg_color or 'white',
            'is_locked': n.is_locked  # pass lock status to frontend
        })
        print(n.data)
    return render_template(
        'saved_notes.html',
        notes=notes,
        notes_json=notes_json,
        tags=sorted(all_tags),
        user=current_user,
        selected_sort=sort,
        selected_tag=tag_filter,
        dark_mode=session.get('dark_mode', False)
    )

@views.route('/pin-toggle/<int:note_id>', methods=['POST'])
@login_required
def toggle_pin(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({'message': 'Unauthorized'}), 403

    note.is_pinned = not note.is_pinned
    db.session.commit()
    return jsonify({'message': 'Pin status toggled', 'is_pinned': note.is_pinned})

@views.route('/note-history/<int:note_id>')
@login_required
def note_history(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash("Access denied.", "error")
        return redirect(url_for("views.saved_notes"))

    versions = sorted(note.versions, key=lambda v: v.timestamp, reverse=True)
    return render_template("note_history.html", note=note, versions=versions, user=current_user, dark_mode=session.get('dark_mode', False))

@views.route('/delete-note', methods=['POST'])
@login_required
def delete_note():
    data = json.loads(request.data)
    note_id = data.get('noteId')
    note = Note.query.get(note_id)
    if note and note.user_id == current_user.id:
        db.session.delete(note)
        db.session.commit()
        return jsonify({'message': 'Note deleted'})
    return jsonify({'message': 'Note not found or permission denied'}), 403

@views.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    user = User.query.get(current_user.id)
    if user:
        Note.query.filter_by(user_id=user.id).delete()
        db.session.delete(user)
        db.session.commit()
        flash('Account deleted successfully!', 'success')
        return redirect(url_for('auth.logout'))
    flash('Account deletion failed.', 'error')
    return redirect(url_for('auth.login'))

def quill_delta_to_plain_text(delta_json_str):
    try:
        delta = json.loads(delta_json_str)
        return ''.join(op.get('insert', '') for op in delta.get('ops', []))
    except Exception:
        return '[Error reading note content]'

@views.route('/download-pdf/<int:note_id>')
@login_required
def download_pdf(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash("You do not have permission to download this note.", "error")
        return redirect(url_for("views.saved_notes"))

    note_text = quill_delta_to_plain_text(note.data)
    html = f"""
    <html><head><style>
    body {{ font-family: Arial; padding: 20px; }}
    pre {{ background-color: {note.bg_color}; padding: 15px; border-radius: 10px; }}
    </style></head><body>
    <h2>Your Note</h2><pre>{note_text}</pre></body></html>
    """
    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=result)
    if pisa_status.err:
        flash("Error generating PDF.", "error")
        return redirect(url_for("views.saved_notes"))
    result.seek(0)
    return send_file(result, download_name=f"note_{note_id}.pdf", as_attachment=True)

@views.route('/sitemap.xml')
def sitemap():
    notes = Note.query.all()
    sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'''
    static_urls = [
        {"loc": "https://noters.online/", "priority": "1.0"},
        {"loc": "https://noters.online/home", "priority": "0.9"},
        {"loc": "https://noters.online/saved-notes", "priority": "0.8"}
    ]
    for url in static_urls:
        sitemap_xml += f'''
<url><loc>{url["loc"]}</loc><changefreq>daily</changefreq><priority>{url["priority"]}</priority></url>'''
    for note in notes:
        sitemap_xml += f'''
<url><loc>https://noters.online/download-pdf/{note.id}</loc><changefreq>monthly</changefreq><priority>0.5</priority></url>'''
    sitemap_xml += '\n</urlset>'
    return Response(sitemap_xml, mimetype='application/xml')

@views.route('/robots.txt')
def robots():
    return Response(
        "User-agent: *\nAllow: /\nSitemap: https://noters.online/sitemap.xml",
        mimetype='text/plain'
    )

@views.route('/unlock-note', methods=['POST'])
@login_required
def unlock_note():
    data = request.get_json()
    note_id = data.get('noteId')
    password = data.get('password')

    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note or not note.is_locked:
        return jsonify({'success': False, 'message': 'Note not found or not locked'}), 404

    if note.check_password(password):
        return jsonify({'success': True, 'data': note.data, 'bg_color': note.bg_color or 'white'})
    else:
        return jsonify({'success': False, 'message': 'Incorrect password'}), 401
import requests
@views.route('/summarize_note', methods=['POST'])
def summarize_note():
    print("📩 Summarize endpoint hit")
    data = request.get_json()
    print("📄 Received data:", data)
    data = request.get_json()
    note_text = data.get('content', '')

    api_key='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'

    if not note_text:
        return jsonify({'error': 'No note content provided'}), 400

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "mistralai/mistral-7b-instruct",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant that summarizes note content."},
                    {"role": "user", "content": f"Summarize this note in simple points:\n{note_text}"}
                ]
            },
            timeout=30  # optional: limit hang time
        )

        print("API response status:", response.status_code)
        print("API raw response:", response.text)

        if response.status_code == 200:
            summary = response.json()['choices'][0]['message']['content']
            return jsonify({'summary': summary})
        else:
            return jsonify({'error': 'Failed to summarize'}), 500

    except Exception as e:
        print("❌ Exception in summarize_note:", e)
        return jsonify({'error': str(e)}), 500

