from flask import Blueprint, render_template, request, flash, jsonify, redirect, url_for, send_file
from flask_login import login_required, current_user
from .models import Note, User
from . import db
import json, io
from xhtml2pdf import pisa
from datetime import datetime
from flask import Response

views = Blueprint('views', __name__)

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
        tags = request.form.get('tags') or ''
        is_pinned = 'is_pinned' in request.form  # Proper checkbox check

        if not note_text or len(note_text.strip()) < 1:
            flash('Note is too short!', category='error')
        elif note_id:
            note = Note.query.get(int(note_id))
            if note and note.user_id == current_user.id:
                note.data = note_text
                note.bg_color = note_bg
                note.tags = tags
                note.is_pinned = is_pinned
                db.session.commit()
                flash('Note updated!', category='success')
            else:
                flash('Note not found or permission denied.', category='error')
        else:
            new_note = Note(
                data=note_text,
                bg_color=note_bg,
                user_id=current_user.id,
                tags=tags,
                is_pinned=is_pinned
            )
            db.session.add(new_note)
            db.session.commit()
            flash('Note added!', category='success')

    edit_id = request.args.get('edit')
    edit_note = None
    if edit_id:
        edit_note = Note.query.get(int(edit_id))
        if not edit_note or edit_note.user_id != current_user.id:
            flash('Note not found or permission denied.', category='error')
            return redirect(url_for('views.home'))

    notes_json = [{'id': n.id, 'data': n.data, 'bg_color': n.bg_color or 'white'} for n in current_user.notes]
    return render_template("home.html", user=current_user, notes_json=notes_json, edit_note=edit_note)

@views.route('/saved-notes')
@login_required
def saved_notes():
    notes = Note.query.filter_by(user_id=current_user.id).order_by(Note.is_pinned.desc(), Note.date.desc()).all()

    all_tags = set()
    for note in notes:
        if note.tags:
            all_tags.update(tag.strip() for tag in note.tags.split(',') if tag.strip())

    notes_json = [{'id': n.id, 'data': n.data, 'bg_color': n.bg_color or 'white'} for n in notes]
    return render_template(
        'saved_notes.html',
        notes=notes,
        notes_json=notes_json,
        tags=sorted(all_tags),
        user=current_user
    )

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
        text = ''
        for op in delta.get('ops', []):
            if 'insert' in op:
                text += op['insert']
        return text
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
    <html>
      <head>
        <style>
          body {{ font-family: Arial, sans-serif; padding: 20px; }}
          pre {{ white-space: pre-wrap; word-wrap: break-word; background-color: {note.bg_color or 'white'}; padding: 15px; border-radius: 10px; }}
        </style>
      </head>
      <body>
        <h2>Your Note</h2>
        <pre>{note_text}</pre>
      </body>
    </html>
    """

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(src=html, dest=result)

    if pisa_status.err:
        flash("Error generating PDF.", "error")
        return redirect(url_for("views.saved_notes"))

    result.seek(0)
    return send_file(result, download_name=f"note_{note_id}.pdf", as_attachment=True)



@views.route('/sitemap.xml', methods=['GET'])
def sitemap():
    # Query all notes
    notes = Note.query.all()

    sitemap_xml = '''<?xml version="1.0" encoding="UTF-8"?>\n'''
    sitemap_xml += '''<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'''

    # Home and Saved Notes
    static_urls = [
        {"loc": "https://noters.online/", "priority": "1.0"},
        {"loc": "https://noters.online/home", "priority": "0.9"},
        {"loc": "https://noters.online/saved-notes", "priority": "0.8"}
    ]
    for url in static_urls:
        sitemap_xml += f'''
    <url>
      <loc>{url["loc"]}</loc>
      <changefreq>daily</changefreq>
      <priority>{url["priority"]}</priority>
    </url>'''

    # Add each note download URL
    for note in notes:
        sitemap_xml += f'''
    <url>
      <loc>https://noters.online/download-pdf/{note.id}</loc>
      <changefreq>monthly</changefreq>
      <priority>0.5</priority>
    </url>'''

    sitemap_xml += '\n</urlset>'

    return Response(sitemap_xml, mimetype='application/xml')

@views.route('/robots.txt')
def robots():
    return Response(
        "User-agent: *\nAllow: /\nSitemap: https://noters.online/sitemap.xml",
        mimetype='text/plain'
    )
