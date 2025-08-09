from flask import Blueprint, app, render_template, request, flash, jsonify, redirect, url_for, send_file, Response, session
from flask_login import login_required, current_user

from website.auth import send_email
from .models import Note, Notification, User, NoteVersion
from . import db
import json, io, re
from xhtml2pdf import pisa
from datetime import datetime
import pytz
import requests
from dotenv import load_dotenv
import os
load_dotenv()
import random

BG_COLORS = [
    "default", "white", "black", "#f8f9fa", "#fff3cd", "#d4edda", "#f8d7da", "#d1ecf1",
    "#e1bee7", "#ffccbc", "#c8e6c9", "#f0f4c3", "#ffe4e1", "#fafad2", "#e6e6fa",
    "#f5f5dc", "#ffe4b5", "#add8e6", "#90ee90", "#ffb6c1", "#ffd700", "#40e0d0",
    "#ff69b4", "#b0c4de"
]

api_key = os.getenv('OPENROUTER_API_KEY')
def add_notification(message):
    if current_user.is_authenticated:
        notif = Notification(user_id=current_user.id, message=message)
        db.session.add(notif)
        db.session.commit()


views = Blueprint('views', __name__)

# -------------------
# Utility: Check if note is blank
# -------------------
def is_blank_quill(content):
    """Detect if Quill HTML/JSON is actually empty."""
    if not content:
        return True

    # Try JSON (Quill Delta)
    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict) and "ops" in parsed:
            text = "".join(op.get("insert", "") for op in parsed["ops"])
            return not text.strip()
    except Exception:
        pass

    # Strip HTML tags
    clean_text = re.sub(r"<[^>]+>", "", content or "").strip()
    return not clean_text

# -------------------
# Routes
# -------------------
@views.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    return redirect(url_for('auth.login'))

@views.route('/toggle-dark-mode')
def toggle_dark_mode():
    session['dark_mode'] = not session.get('dark_mode', False)
    return redirect(request.referrer or url_for('views.home'))

@views.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        note_id = request.form.get('note_id')
        note_text = request.form.get('note')
        note_bg = request.form.get('note_bg') or 'white'  # store in a separate variable
        tags = request.form.get('tags') or ''
        is_pinned = 'is_pinned' in request.form
        is_completed = 'is_completed' in request.form
        password = request.form.get('password', '').strip()

        if is_blank_quill(note_text):
            return jsonify({"success": False, "error": "Note cannot be empty"}), 400

        if note_id:  # Edit note
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                db.session.add(NoteVersion(note_id=note.id, version_data=note.data))

                note.data = note_text
                note.bg_color = note_bg  # assign here after note exists
                note.tags = tags
                note.is_pinned = is_pinned
                note.is_completed = is_completed
                note.last_updated = datetime.utcnow()

                if password:
                    note.set_password(password)
                elif not note.password_hash:
                    note.is_locked = False

                db.session.commit()
                add_notification(f'Note "{note.title}" updated')
                return jsonify({"success": True, "message": "Note updated"})
            else:
                return jsonify({"success": False, "error": "Note not found or permission denied"}), 403

        else:  # New note
            new_note = Note(
                title=request.form.get('title', 'Untitled Note'),
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
            flash("Note added successfully!", category="success")
            return redirect(url_for('views.home'))


        # ... (existing GET request logic remains unchanged)


    # ------------------ GET REQUEST ------------------
    edit_id = request.args.get('edit')
    edit_note = None
    if edit_id:
        edit_note = Note.query.get(int(edit_id))
        if not edit_note or edit_note.user_id != current_user.id:
            flash('Note not found or permission denied.', category='error')
            return redirect(url_for('views.home'))

    # If not editing an existing note, prepare a default bg_color for the new note form
    default_bg_color = random.choice(BG_COLORS) if not edit_note else edit_note.bg_color or "white"

    # Format dates to IST for existing notes
    ist = pytz.timezone('Asia/Kolkata')
    for note in current_user.notes:
        note.date = note.date.astimezone(ist)
        note.last_updated = note.last_updated.astimezone(ist)

    notes_json = [
        {
            'id': n.id,
            'data': n.data,
            'bg_color': n.bg_color or 'white'
        } for n in current_user.notes
    ]

    def note_to_dict(note):
        return {
            "id": note.id,
            "data": note.data,
            "bg_color": note.bg_color or "white",
            "tags": note.tags or "",
            "is_pinned": note.is_pinned,
            "is_completed": note.is_completed,
            "is_locked": note.is_locked
        }

    return render_template(
        "home.html",
        user=current_user,
        notes_json=notes_json,
        edit_note=edit_note,
        edit_note_json=json.dumps(note_to_dict(edit_note)) if edit_note else 'null',
        default_bg_color=default_bg_color,  # pass this to template
        dark_mode=session.get('dark_mode', False)
    )


@views.route('/saved-notes')
@login_required
def saved_notes():
    sort = request.args.get('sort', 'pinned_date')
    tag_filter = request.args.get('tag')

    # Start with query object, no .all() here
    query = Note.query.filter_by(user_id=current_user.id)

    # Apply tag filter if any
    if tag_filter:
        query = query.filter(Note.tags.ilike(f"%{tag_filter}%"))

    # Apply sorting
    if sort == 'title_asc':
        query = query.order_by(Note.is_pinned.desc(), Note.title.asc())
    elif sort == 'title_desc':
        query = query.order_by(Note.is_pinned.desc(), Note.title.desc())
    elif sort == 'date_asc':
        query = query.order_by(Note.is_pinned.desc(), Note.date.asc())
    else:
        query = query.order_by(Note.is_pinned.desc(), Note.date.desc())

    # Finally get all results here
    notes = query.all()

    # Rest of your code (timezones, tags, json prep)
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
            'is_locked': n.is_locked
        })

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

def quill_delta_to_html(data):
    """Convert Quill JSON/dict/plain text into basic HTML."""
    try:
        if isinstance(data, dict) and "ops" in data:
            ops = data["ops"]
        elif isinstance(data, str):
            try:
                parsed = json.loads(data)
                if isinstance(parsed, dict) and "ops" in parsed:
                    ops = parsed["ops"]
                else:
                    return f"<p>{data}</p>"
            except json.JSONDecodeError:
                return f"<p>{data}</p>"
        else:
            return f"<p>{str(data)}</p>"

        html_parts = []
        for op in ops:
            insert_text = op.get("insert", "")
            attrs = op.get("attributes", {})
            if attrs.get("bold"):
                insert_text = f"<b>{insert_text}</b>"
            if attrs.get("italic"):
                insert_text = f"<i>{insert_text}</i>"
            if attrs.get("underline"):
                insert_text = f"<u>{insert_text}</u>"
            if attrs.get("strike"):
                insert_text = f"<s>{insert_text}</s>"
            if attrs.get("header") == 1:
                insert_text = f"<h1>{insert_text}</h1>"
            elif attrs.get("header") == 2:
                insert_text = f"<h2>{insert_text}</h2>"
            if attrs.get("list") == "bullet":
                insert_text = f"<li>{insert_text}</li>"
            elif attrs.get("list") == "ordered":
                insert_text = f"<li>{insert_text}</li>"
            html_parts.append(insert_text)

        html_content = "".join(html_parts)
        if "<li>" in html_content:
            if "ordered" in json.dumps(ops):
                html_content = f"<ol>{html_content}</ol>"
            else:
                html_content = f"<ul>{html_content}</ul>"
        return html_content
    except Exception as e:
        print("❌ Error parsing Quill HTML:", e)
        return "<p>[Error reading note content]</p>"

@views.route('/download-pdf/<int:note_id>')
@login_required
def download_pdf(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash("You do not have permission to download this note.", "error")
        return redirect(url_for("views.saved_notes"))

    bg_color = note.bg_color or "white"
    note_html = quill_delta_to_html(note.data)  # ensure this returns safe HTML

    html = f"""
    <html>
    <head>
      <style>
        body {{ font-family: Arial, sans-serif; padding: 20px; }}
        .note-content {{
            background-color: {bg_color};
            padding: 15px;
            border-radius: 10px;
        }}
      </style>
    </head>
    <body>
      <h2>{note.title}</h2>
      <div class="note-content">{note_html}</div>
    </body>
    </html>
    """

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=result)

    if pisa_status.err:
        flash("Error generating PDF.", "error")
        return redirect(url_for("views.saved_notes"))

    result.seek(0)
    return send_file(result, download_name=f"{note.title}.pdf", as_attachment=True)

@views.route("/get-note/<int:note_id>")
@login_required
def get_note(note_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({
        "id": note.id,
        "tags": note.tags or "",
        "password": "",  # never send hash
        "is_pinned": bool(note.is_pinned),
        "bg_color": note.bg_color or "white",
        "note_html": note.data or ""
    })

load_dotenv()
api_key = os.getenv("OPENROUTER_API_KEY")

@views.route("/summarize_note", methods=["POST"])
@login_required
def summarize_note():
    print("🔑 API Key Loaded:", bool(api_key))

    try:
        # Check API key first
        if not api_key:
            return jsonify({"error": "OpenRouter API key not set in .env"}), 500

        data = request.get_json()
        content = data.get("content", "")

        if not content.strip():
            return jsonify({"error": "No content to summarize"}), 400

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
    "model": "mistralai/mistral-7b-instruct",
    "messages": [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant that summarizes notes into short, clear bullet points. "
                "Keep the summary under half the length of the original text. "
                "Write in plain language without bold text, numbering, or long sentences. "
                "Do not add extra commentary or explanations."
            )
        },
        {
            "role": "user",
            "content": f"Summarize this:\n\n{content}"
        }
    ]
}


        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload)
        )

        # Debug logging
        print("🔹 API Status:", response.status_code)
        print("🔹 API Response:", response.text)

        if response.status_code != 200:
            return jsonify({"error": f"API request failed ({response.status_code})"}), 500

        result = response.json()

        # Safe parsing
        summary = ""
        try:
            choices = result.get("choices", [])
            if choices:
                summary = choices[0].get("message", {}).get("content", "").strip()
        except Exception as e:
            print("❌ Parsing error:", e)

        if not summary:
            return jsonify({"error": "No summary generated"}), 500

        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

from urllib.parse import unquote



@views.route("/privacy")
def privacy():
    return render_template("privacy.html")

@views.route("/terms")
def terms():
    return render_template("terms.html")
@views.route('/sitemap.xml', methods=['GET'])
def sitemap():
    pages = []
    now = datetime.utcnow().date().isoformat()

    # Static pages (update this list with your own static routes)
    static_urls = ['/', '/login', '/sign-up', '/saved-notes', '/settings', '/about', '/contact']
    
    for url in static_urls:
        pages.append(f"""
   <url>
      <loc>{request.url_root.strip('/')}{url}</loc>
      <lastmod>{now}</lastmod>
      <changefreq>weekly</changefreq>
      <priority>0.8</priority>
   </url>
""")

    sitemap_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{''.join(pages)}
</urlset>"""

    return Response(sitemap_xml, mimetype='application/xml')
@views.route('/edit/<int:note_id>', methods=['GET', 'POST'])
@login_required
def edit_note(note_id):
    note = Note.query.filter_by(user_id=current_user.id, id=note_id).first_or_404()

    if request.method == 'POST':
        note_title = request.form.get('title')  # <-- add this
        note_text = request.form.get('note')
        note.bg_color = request.form.get('note_bg') or 'white'
        tags = request.form.get('tags')
        is_pinned = request.form.get('is_pinned') == 'true'

        note.title = note_title  # <-- update the title
        note.data = note_text
        note.bg_color = note.bg_color
        note.tags = tags
        note.is_pinned = is_pinned
        note.updated_at = datetime.utcnow()

        # Save version history
        is_autosave = request.form.get('autosave') == 'true'
        if not is_autosave:
            version = NoteVersion(note_id=note.id, version_data=note_text)
            db.session.add(version)

        db.session.commit()
        flash('Note updated successfully!', category='success')
        return redirect(url_for('views.saved_notes'))

    return render_template("home.html", user=current_user, editing=True, edit_note=note)


@views.route("/save_note", methods=["POST"])
def save_note():
    data = request.get_json()

    title = data.get("title", "").strip()
    note_content = data.get("note", "").strip()
    is_autosave = data.get("is_autosave", False)

    if not title and not note_content:
        return jsonify({"success": False, "message": "Empty note"}), 400

    # Save note (new or update existing)
    note = save_or_update_note_in_db(title, note_content, user_id=current_user.id)

    # Add to history only if not autosave
    if not is_autosave:
        add_note_to_history(note.id, title, note_content, user_id=current_user.id)

    return jsonify({"success": True, "message": "Note saved"})
from datetime import datetime
from website import db
from website.models import NoteVersion

def add_note_to_history(note_id, title, content, user_id):
    """
    Adds a manual save entry to the note's version history.
    """
    version = NoteVersion(
        note_id=note_id,
        version_data=content,
        timestamp=datetime.utcnow()
    )
    db.session.add(version)
    db.session.commit()
def save_or_update_note_in_db(title, note_content, user_id):
    # Try to find a note by title or create a new note
    note = Note.query.filter_by(title=title, user_id=user_id).first()
    if note:
        note.data = note_content
        note.last_updated = datetime.utcnow()
    else:
        note = Note(title=title, data=note_content, user_id=user_id, last_updated=datetime.utcnow())
        db.session.add(note)
    db.session.commit()
    return note

import os
from flask import (
    render_template, request, redirect, url_for, flash, current_app
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from . import db
from .models import User, Note

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@login_required
@views.route('/settings', methods=['GET', 'POST'])
def settings():
    user = current_user

    # Calculate total notes created by user
    total_notes = Note.query.filter_by(user_id=user.id).count()

    if request.method == 'POST':
        # Update username
        new_username = request.form.get('username')
        if new_username and new_username != user.username:
            # Optionally, add validation for username uniqueness here
            user.username = new_username

        # Update dark mode preference
        user.dark_mode = bool(request.form.get('dark_mode'))

    # Handle profile picture upload
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        print(f"Received file: {file.filename}")
        if file and allowed_file(file.filename):
            import uuid
            filename = secure_filename(file.filename)
            unique_suffix = uuid.uuid4().hex
            filename = f"user_{user.id}_{unique_suffix}_{filename}"

            upload_folder = os.path.join(current_app.root_path, 'static/profile_pics')
            os.makedirs(upload_folder, exist_ok=True)
            file_path = os.path.join(upload_folder, filename)
            print(f"Saving file to: {file_path}")
            file.save(file_path)
            user.profile_pic_url = filename
        elif file.filename != '':
            flash('Invalid file type for profile picture. Allowed: png, jpg, jpeg, gif, webp', 'danger')
    else:
        print("No profile_pic found in request.files")

    try:
        db.session.commit()
        flash('Settings updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while updating settings.', 'danger')
        current_app.logger.error(f"Settings update error: {e}")

    return render_template('settings.html', user=user, total_notes=total_notes)

@views.route('/note/<int:note_id>/restore/<int:version_id>', methods=['POST'])
@login_required
def restore_version(note_id, version_id):
    note = Note.query.get_or_404(note_id)
    if note.user_id != current_user.id:
        flash("Unauthorized", "error")
        return redirect(url_for('views.saved_notes'))

    version = NoteVersion.query.filter_by(id=version_id, note_id=note_id).first_or_404()

    # Save current version before restoring (optional)
    db.session.add(NoteVersion(note_id=note.id, version_data=note.data))

    # Restore version content
    note.data = version.version_data
    note.last_updated = datetime.utcnow()

    db.session.commit()
    flash("Note restored to selected version.", "success")
    return redirect(url_for('views.note_history', note_id=note_id))
from flask import request, jsonify

@views.route('/save-note-order', methods=['POST'])
@login_required
def save_note_order():
    data = request.get_json()
    order = data.get('order', [])
    user_id = current_user.id

    # Assuming you have a NoteOrder table to store order indexes per user
    # Or update 'order_index' column in Note table for this user

    for index, note_id in enumerate(order):
        note = Note.query.filter_by(id=note_id, user_id=user_id).first()
        if note:
            note.order_index = index
    db.session.commit()
    return jsonify(success=True)
from flask import request, jsonify
from flask_login import current_user
from website.models import Note
from website import db

@views.route('/update-note-order', methods=['POST'])
def update_note_order():
    data = request.get_json()
    order = data.get('order', [])

    if not order:
        return jsonify({'error': 'No order provided'}), 400

    # update order_index of notes for current user
    for index, note_id in enumerate(order):
        note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
        if note:
            note.order_index = index
    db.session.commit()

    return jsonify({'message': 'Order updated'})
@views.route('/notes')
def notes_view():
    sort = request.args.get('sort', 'date_desc')
    query = Note.query.filter_by(user_id=current_user.id)

    if sort == 'order_custom':
        query = query.order_by(Note.is_pinned.desc(), Note.order_index.asc())
    elif sort == 'date_asc':
        query = query.order_by(Note.date.asc())
    else:  # default date_desc
        query = query.order_by(Note.date.desc())

    notes = query.all()
    render_template('saved_notes.html',user=User)

from flask import send_from_directory

@views.route('/robots.txt')
def robots_txt():
    return send_from_directory('static', 'robots.txt')
