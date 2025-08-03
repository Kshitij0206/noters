from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, send_file, Response, session
from flask_login import login_required, current_user
from .models import Note, User, NoteVersion
from . import db
import json, io, re
from xhtml2pdf import pisa
from datetime import datetime
import pytz
import requests
from dotenv import load_dotenv
import os
load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY')


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
        note_bg = request.form.get('note_bg') or 'white'
        tags = request.form.get('tags') or ''
        is_pinned = 'is_pinned' in request.form
        is_completed = 'is_completed' in request.form
        password = request.form.get('password', '').strip()

        # Prevent saving empty notes
        if is_blank_quill(note_text):
            return jsonify({"success": False, "error": "Note cannot be empty"}), 400

        if note_id:  # Edit note
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                # Save old version for history
                db.session.add(NoteVersion(note_id=note.id, version_data=note.data))

                note.data = note_text
                note.bg_color = note_bg
                note.tags = tags
                note.is_pinned = is_pinned
                note.is_completed = is_completed
                note.last_updated = datetime.utcnow()

                if password:
                    note.set_password(password)
                elif not note.password_hash:
                    note.is_locked = False

                db.session.commit()
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
            return jsonify({"success": True, "message": "Note added"})

    # ------------------ GET REQUEST ------------------
    edit_id = request.args.get('edit')
    edit_note = None
    if edit_id:
        edit_note = Note.query.get(int(edit_id))
        if not edit_note or edit_note.user_id != current_user.id:
            flash('Note not found or permission denied.', category='error')
            return redirect(url_for('views.home'))

    # Format dates to IST
    ist = pytz.timezone('Asia/Kolkata')
    for note in current_user.notes:
        note.date = note.date.astimezone(ist)
        note.last_updated = note.last_updated.astimezone(ist)

    # Prepare JSON for saved notes
    notes_json = [
        {
            'id': n.id,
            'data': n.data,
            'bg_color': n.bg_color or 'white'
        } for n in current_user.notes
    ]

    # Convert edit note to JSON for JavaScript
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
        dark_mode=session.get('dark_mode', False)
    )


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

    # Collect all tags
    all_tags = set()
    for note in notes:
        if note.tags:
            all_tags.update(tag.strip() for tag in note.tags.split(',') if tag.strip())

    # Prepare note previews
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
    note_html = quill_delta_to_html(note.data)
    html = f"""
    <html><head><style>
    body {{ font-family: Arial, sans-serif; padding: 20px; }}
    .note-content {{ background-color: {note.bg_color}; padding: 15px; border-radius: 10px; }}
    </style></head><body>
    <h2>Your Note</h2>
    <div class="note-content">{note_html}</div>
    </body></html>
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
    "model": "mistralai/mistral-7b-instruct",  # ✅ correct OpenRouter model name
    "messages": [
        {"role": "system", "content": "You are a helpful assistant that summarizes notes in clear, concise language and answers in points and in under 500 words and does not bolden any text."},
        {"role": "user", "content": f"Summarize this:\n\n{content}"}
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

@views.route('/edit/<string:title>', methods=['GET', 'POST'])
@login_required
def edit_note_by_title(title):
    decoded_title = unquote(title).strip()

    # Look up the note by title for the current user
    note = Note.query.filter_by(user_id=current_user.id, title=decoded_title).first_or_404()

    if request.method == 'POST':
        note_text = request.form.get('note')
        note_bg = request.form.get('note_bg') or 'white'
        tags = request.form.get('tags') or ''
        is_pinned = 'is_pinned' in request.form
        is_completed = 'is_completed' in request.form
        password = request.form.get('password', '').strip()

        if is_blank_quill(note_text):
            return jsonify({"success": False, "error": "Note cannot be empty"}), 400

        # Save old version for history
        db.session.add(NoteVersion(note_id=note.id, version_data=note.data))

        note.data = note_text
        note.bg_color = note_bg
        note.tags = tags
        note.is_pinned = is_pinned
        note.is_completed = is_completed
        note.last_updated = datetime.utcnow()

        if password:
            note.set_password(password)
        elif not note.password_hash:
            note.is_locked = False

        db.session.commit()
        return jsonify({"success": True, "message": "Note updated"})

    # Pre-fill edit form
    def note_to_dict(note):
        return {
            "id": note.id,
            "title": note.title,
            "data": note.data,
            "bg_color": note.bg_color or "white",
            "tags": note.tags or "",
            "is_pinned": note.is_pinned,
            "is_completed": note.is_completed,
            "is_locked": note.is_locked
        }

    # Convert datetime to IST
    ist = pytz.timezone('Asia/Kolkata')
    note.date = note.date.astimezone(ist)
    note.last_updated = note.last_updated.astimezone(ist)

    return render_template(
        "home.html",
        user=current_user,
        edit_note=note,
        edit_note_json=json.dumps(note_to_dict(note)),
        dark_mode=session.get('dark_mode', False)
    )
