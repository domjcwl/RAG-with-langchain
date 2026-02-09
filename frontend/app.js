const sessionsEl = document.getElementById("sessions");
const messagesEl = document.getElementById("messages");
const sendBtn = document.getElementById("send-btn");
const userInput = document.getElementById("user-input");
const newSessionBtn = document.getElementById("new-session-btn");
const fileInput = document.getElementById("file-input");
const filePreview = document.getElementById("file-preview");

let selectedFile = null;

/* --------------------
   Session State
-------------------- */

let sessions = {};
let activeSessionId = null;

/* --------------------
   Helpers
-------------------- */

function generateId() {
  return crypto.randomUUID();
}

function renderSessions() {
  sessionsEl.innerHTML = "";

  Object.entries(sessions).forEach(([id, session]) => {
    const div = document.createElement("div");
    div.className = "session" + (id === activeSessionId ? " active" : "");

    // Session name
    const name = document.createElement("div");
    name.className = "session-name";
    name.textContent = session.name;
    name.onclick = () => switchSession(id);

    // Rename button
    const rename = document.createElement("button");
    rename.textContent = "✏️";
    rename.onclick = (e) => {
      e.stopPropagation();
      startRenameSession(div, id);
    };

    // Delete button
    const del = document.createElement("button");
    del.textContent = "🗑";
    del.onclick = (e) => {
      e.stopPropagation();
      deleteSession(id);
    };

    div.appendChild(name);
    div.appendChild(rename);
    div.appendChild(del);
    sessionsEl.appendChild(div);
  });
}

function startRenameSession(container, id) {
  const session = sessions[id];

  const input = document.createElement("input");
  input.value = session.name;

  input.onblur = () => {
    session.name = input.value.trim() || session.name;
    renderSessions();
  };

  input.onkeydown = (e) => {
    if (e.key === "Enter") input.blur();
    if (e.key === "Escape") renderSessions();
  };
  session;
  container.innerHTML = "";
  container.appendChild(input);
  input.focus();
  input.select();
}

function renderMessages() {
  messagesEl.innerHTML = "";

  if (!activeSessionId) return;

  sessions[activeSessionId].messages.forEach((msg) => {
    addMessageToUI(msg.text, msg.sender);
  });
}

function addMessageToUI(text, sender) {
  const msg = document.createElement("div");
  msg.className = `message ${sender}`;
  msg.textContent = text;
  messagesEl.appendChild(msg);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

/* --------------------
   Session Actions
-------------------- */

function createSession() {
  const id = generateId();
  sessions[id] = {
    name: `Session ${Object.keys(sessions).length + 1}`,
    messages: [{ sender: "bot", text: "Hello 👋 How can I help you?" }],
  };

  activeSessionId = id;
  renderSessions();
  renderMessages();
}

function switchSession(id) {
  activeSessionId = id;
  renderSessions();
  renderMessages();
}

function deleteSession(id) {
  delete sessions[id];

  if (activeSessionId === id) {
    activeSessionId = Object.keys(sessions)[0] || null;
  }

  renderSessions();
  renderMessages();
}

/* --------------------
   Messaging
-------------------- */

sendBtn.addEventListener("click", () => {
  const text = userInput.value.trim();
  if (!text || !activeSessionId) return;

  const session = sessions[activeSessionId];

  session.messages.push({ sender: "user", text });
  addMessageToUI(text, "user");

  userInput.value = "";

  // Fake bot reply (replace with backend call)
  setTimeout(() => {
    const reply = "This is a placeholder response 🤖";
    session.messages.push({ sender: "bot", text: reply });
    addMessageToUI(reply, "bot");
  }, 600);
});

userInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendBtn.click();
});

/* --------------------
   Init
-------------------- */

newSessionBtn.addEventListener("click", createSession);

// Start with one session
createSession();

fileInput.addEventListener("change", () => {
  if (!fileInput.files.length) return;

  selectedFile = fileInput.files[0];
  renderFilePreview();
});

function renderFilePreview() {
  filePreview.innerHTML = "";

  if (!selectedFile) return;

  const container = document.createElement("div");
  container.className = "file-item";

  const name = document.createElement("div");
  name.className = "file-name";
  name.textContent = selectedFile.name;

  const loadBtn = document.createElement("button");
  loadBtn.className = "load-btn";
  loadBtn.textContent = "Load file";

  loadBtn.onclick = () => {
    loadFileToDatabase(container);
  };

  const removeBtn = document.createElement("button");
  removeBtn.className = "remove-btn";
  removeBtn.textContent = "Remove file";

  removeBtn.onclick = () => {
    removeFile();
  };

  container.appendChild(name);
  container.appendChild(loadBtn);
  container.appendChild(removeBtn);
  filePreview.appendChild(container);
}

function loadFileToDatabase(container) {
  const status = document.createElement("div");
  status.className = "file-status";
  status.textContent = `${selectedFile.name} has been loaded to database`;

  // Prevent double-loading UI
  container.querySelector(".load-btn").disabled = true;
  container.querySelector(".load-btn").textContent = "Loaded";

  container.appendChild(status);
}

function removeFile() {
  selectedFile = null;
  fileInput.value = ""; // reset input
  filePreview.innerHTML = "";
}
