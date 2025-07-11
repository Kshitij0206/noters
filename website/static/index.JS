document.addEventListener("DOMContentLoaded", () => {
    // Attach click event listener to Edit buttons
    document.querySelectorAll(".edit-note-btn").forEach((button) => {
      button.addEventListener("click", () => {
        const noteId = button.getAttribute("data-id");
        const noteText = button.getAttribute("data-text");
  
        // Populate the textarea and hidden input with the note details
        const noteInput = document.getElementById("note");
        const noteIdInput = document.getElementById("note_id");
  
        if (noteInput && noteIdInput) {
          noteInput.value = noteText;
          noteIdInput.value = noteId;
        } else {
          console.error("Note input elements not found!");
        }
      });
    });
  
    // Attach click event listener to Delete buttons
    document.querySelectorAll(".delete-note-btn").forEach((button) => {
      button.addEventListener("click", () => {
        const noteId = button.getAttribute("data-id");
  
        if (!noteId) {
          console.error("Note ID not found for deletion.");
          return;
        }
  
        // Confirm deletion with the user
        const confirmDeletion = confirm("Are you sure you want to delete this note?");
        if (confirmDeletion) {
          deleteNote(noteId);
        }
      });
    });
  });
  
  /**
   * Sends a request to delete a note.
   * @param {number} noteId - The ID of the note to delete.
   */
  function deleteNote(noteId) {
    fetch("/delete-note", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ noteId: noteId }),
    })
      .then((response) => {
        if (!response.ok) {
          throw new Error("Failed to delete note.");
        }
        return response.json();
      })
      .then(() => {
        // Reload the page to reflect changes
        window.location.reload();
      })
      .catch((error) => {
        console.error("Error deleting note:", error);
      });
  }
  