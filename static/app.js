// static/app.js (Optimized)

class ChatApp {
  constructor() {
    this.socket  = io({ path: "/ilmagent" });
    this.md = window.markdownit({
      html: true,
      breaks: true,
      linkify: true,
      typographer: false,
      quotes: '“”‘’',
    });

    this.sessionId = this.initializeSessionId();
    this.messagesEl = document.getElementById("messages");
    this.sendBtn = document.getElementById("send");
    this.inputEl = document.getElementById("input");

    this.setupSocketEvents();
    this.setupEventListeners();

    this.appendMessage("Hello I am LLM agent, how may I help you?", "agent");
  }

  initializeSessionId() {
    let id = localStorage.getItem("chat_session_id");
    if (!id) {
      id = 'room_' + Math.random().toString(36).slice(2, 11);
      localStorage.setItem("chat_session_id", id);
    }
    this.socket.emit('join', { room: id });
    return id;
  }

  scrollToBottom() {
    this.messagesEl.scrollTop = this.messagesEl.scrollHeight;
  }

  appendMessage(text, sender) {
    const wrapper = document.createElement("div");
    wrapper.className = sender === "user" ? "user-message" : "agent-message";
    wrapper.innerHTML = sender === "user"
      ? `<div class="message-box"><div class="user-query">${this.md.render(text)}</div></div>`
      : `
        <div class="mime-aviator-avatar">
          <div class="mime-aviator-avatar-light">
            <img class="mime3" src="/static/icons/mime2.svg" alt="avatar">
          </div>
        </div>
        <div class="agent-content">${this.md.render(text)}</div>`;

    this.messagesEl.appendChild(wrapper);
    this.scrollToBottom();
  }

  showTypingIndicator() {
    const indicator = document.createElement("div");
    indicator.id = "thinking";
    indicator.className = "thinking";
    indicator.innerHTML = `
      <div class="aviator-dp">
        <div class="container2">
          <div class="mime-aviator-avatar">
            <div class="mime-aviator-avatar-light">
              <img class="mime3" src="/static/icons/mime2.svg" alt="avatar">
            </div>
          </div>
        </div>
      </div>
      <svg id="dots" width="132px" height="58px" viewBox="0 0 132 58" version="1.1" xmlns="http://www.w3.org/2000/svg"
        xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:sketch="http://www.bohemiancoding.com/sketch/ns">
        <!-- Generator: Sketch 3.5.1 (25234) - http://www.bohemiancoding.com/sketch -->
        <title>dots</title>
        <desc>Created with Sketch.</desc>
        <defs></defs>
        <g id="Page-1" stroke="none" stroke-width="1" fill="none" fill-rule="evenodd" sketch:type="MSPage">
            <g id="dots" sketch:type="MSArtboardGroup" fill="#A3A3A3">
                <circle id="dot1" sketch:type="MSShapeGroup" cx="25" cy="30" r="13"></circle>
                <circle id="dot2" sketch:type="MSShapeGroup" cx="65" cy="30" r="13"></circle>
                <circle id="dot3" sketch:type="MSShapeGroup" cx="105" cy="30" r="13"></circle>
            </g>
        </g>
    </svg>`;

    this.messagesEl.appendChild(indicator);
    this.scrollToBottom();
  }

  removeTypingIndicator() {
    document.getElementById("thinking")?.remove();
  }

  setupSocketEvents() {
    this.socket.on("history", history => {
      this.messagesEl.innerHTML = "";
      history.forEach(msg => {
        if (msg.user) this.appendMessage(msg.user, "user");
        if (msg.ai) this.appendMessage(msg.ai, "agent");
      });
      this.scrollToBottom();
    });

    this.socket.on("ai_message", data => {
      this.removeTypingIndicator();
      if (data.message) this.appendMessage(data.message, "agent");
      this.sendBtn.disabled = false;
      this.inputEl.focus();
    });
  }

  setupEventListeners() {
    this.sendBtn.addEventListener("click", () => {
      const text = this.inputEl.value.trim();
      if (!text) return;

      this.appendMessage(text, "user");
      this.inputEl.value = "";
      this.sendBtn.disabled = true;
      this.showTypingIndicator();
      this.socket.emit("message", { room: this.sessionId, message: text });
    });

    this.inputEl.addEventListener("keydown", e => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.sendBtn.click();
      }
    });
  }
}

// Initialize the ChatApp
new ChatApp();