function summarizeNote(noteId) {
  const noteDiv = document.getElementById(`note-content-${noteId}`);
  const loader = document.getElementById(`loader-${noteId}`);
  const button = document.getElementById(`summarize-btn-${noteId}`);
  const summaryOutput = document.getElementById(`summary-${noteId}`);

  let noteContent = "";
  try {
    const delta = JSON.parse(noteDiv.dataset.delta);
    if (delta.ops) {
      noteContent = delta.ops.map(op => typeof op.insert === 'string' ? op.insert : '').join('');
    }
  } catch {
    noteContent = noteDiv.innerText.trim();
  }

  if (!noteContent.trim()) {
    summaryOutput.textContent = 'Error: No note content found.';
    return;
  }

  loader.style.display = 'block';
  if (button) button.disabled = true;

  fetch('/summarize_note', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content: noteContent })
  })
  .then(res => res.json())
  .then(data => {
    summaryOutput.textContent = data.summary || ('Error: ' + (data.error || 'Unknown error.'));
  })
  .catch(() => {
    summaryOutput.textContent = 'An error occurred while summarizing.';
  })
  .finally(() => {
    loader.style.display = 'none';
    if (button) button.disabled = false;
  });
}
function copyNote(noteId) {
  const noteDiv = document.getElementById(`note-content-${noteId}`);
  if (!noteDiv) return alert("Note content not found.");

  let content = "";
  try {
    const delta = JSON.parse(noteDiv.dataset.delta);
    if (delta.ops) {
      content = delta.ops
        .map(op => (typeof op.insert === "string" ? op.insert : ""))
        .join("");
    }
  } catch {
    content = noteDiv.innerText.trim();
  }

  if (!content.trim()) return alert("No note content to copy.");

  navigator.clipboard.writeText(content.trim())
    .then(() => alert("Note copied to clipboard!"))
    .catch(() => alert("Failed to copy note."));
}


function copySummary(noteId) {
  const text = document.getElementById(`summary-${noteId}`).innerText.trim();
  if (!text) {
    alert("No summary to copy.");
    return;
  }

  navigator.clipboard.writeText(text).then(() => {
    alert("Summary copied to clipboard!");
  }).catch(err => {
    console.error("Copy failed:", err);
    alert("Failed to copy summary.");
  });
}
