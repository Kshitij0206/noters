function summarizeNote(noteId) {
  const noteDiv = document.getElementById(`note-content-${noteId}`);
  const loader = document.getElementById(`loader-${noteId}`);
  const button = document.getElementById(`summarize-btn-${noteId}`);
  const summaryOutput = document.getElementById(`summary-${noteId}`);

  // Get note content from data-delta attribute
  let noteContent = noteDiv.dataset.delta;
  try {
    const delta = JSON.parse(noteContent);
    if (delta.ops) {
      // Convert Quill delta to plain text
      noteContent = delta.ops.map(op => typeof op.insert === 'string' ? op.insert : '').join('');
    }
  } catch (e) {
    console.warn("Could not parse delta, sending raw:", e);
  }

  loader.style.display = 'block';
  if (button) button.disabled = true;

  fetch('/summarize_note', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ note_id: noteId, content: noteContent })
  })
  .then(response => response.json())
  .then(data => {
    if (data.summary) {
      summaryOutput.textContent = data.summary;
    } else {
      summaryOutput.textContent = 'Error: ' + (data.error || 'Unknown error.');
    }
  })
  .catch(err => {
    console.error(err);
    summaryOutput.textContent = 'An error occurred while summarizing.';
  })
  .finally(() => {
    loader.style.display = 'none';
    if (button) button.disabled = false;
  });
}
function copyNote(noteId) {
  const noteDiv = document.getElementById(`note-content-${noteId}`);
  if (!noteDiv) {
    alert("Note content not found.");
    return;
  }

  const text = noteDiv.innerText.trim();
  if (!text) {
    alert("No note content to copy.");
    return;
  }

  navigator.clipboard.writeText(text).then(() => {
    alert("Note copied to clipboard!");
  }).catch(err => {
    console.error("Copy failed:", err);
    alert("Failed to copy note.");
  });
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
