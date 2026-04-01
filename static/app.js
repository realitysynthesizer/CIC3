const messagesDiv = document.getElementById("messages");
const textInput = document.getElementById("text-input");
const sendBtn = document.getElementById("send-btn");
const imageInput = document.getElementById("image-input");
const imagePreview = document.getElementById("image-preview");
const clearBtn = document.getElementById("clear-btn");

let conversationHistory = [];
let pendingImage = null;
let isLoading = false;

// Auto-resize textarea
textInput.addEventListener("input", () => {
  textInput.style.height = "auto";
  textInput.style.height = Math.min(textInput.scrollHeight, 120) + "px";
});

// Enter to send, Shift+Enter for newline
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);
clearBtn.addEventListener("click", () => {
  conversationHistory = [];
  messagesDiv.innerHTML = "";
  clearImage();
});

// Image handling
imageInput.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  pendingImage = await resizeAndEncode(file);
  imagePreview.style.display = "inline-block";
  imagePreview.innerHTML = `
    <img src="${pendingImage}">
    <button class="remove-img" onclick="clearImage()">x</button>
  `;
  imageInput.value = "";
});

function clearImage() {
  pendingImage = null;
  imagePreview.style.display = "none";
  imagePreview.innerHTML = "";
}
// Make clearImage available to onclick
window.clearImage = clearImage;

function resizeAndEncode(file) {
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      const img = new Image();
      img.onload = () => {
        const maxSize = 1024;
        let { width, height } = img;
        if (width > maxSize || height > maxSize) {
          const scale = maxSize / Math.max(width, height);
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        canvas.getContext("2d").drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.85));
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  });
}

async function sendMessage() {
  const text = textInput.value.trim();
  if ((!text && !pendingImage) || isLoading) return;

  // Build user message content
  let content;
  if (pendingImage) {
    content = [];
    if (text) content.push({ type: "text", text });
    content.push({
      type: "image_url",
      image_url: { url: pendingImage },
    });
  } else {
    content = text;
  }

  const userMessage = { role: "user", content };
  conversationHistory.push(userMessage);

  // Render user message
  renderMessage("user", text, pendingImage);

  // Clear inputs
  textInput.value = "";
  textInput.style.height = "auto";
  clearImage();

  // Show thinking indicator
  const thinkingEl = document.createElement("div");
  thinkingEl.className = "message thinking";
  thinkingEl.textContent = "Thinking...";
  messagesDiv.appendChild(thinkingEl);
  scrollToBottom();

  isLoading = true;
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: conversationHistory }),
    });

    const data = await res.json();
    thinkingEl.remove();

    if (!res.ok) {
      renderMessage("assistant", "Error: " + (data.detail || "Something went wrong"));
      return;
    }

    const reply = data.reply;
    conversationHistory.push({ role: "assistant", content: reply });
    renderMessage("assistant", reply);
  } catch (err) {
    thinkingEl.remove();
    renderMessage("assistant", "Error: Could not reach the server.");
  } finally {
    isLoading = false;
    sendBtn.disabled = false;
  }
}

function renderMessage(role, text, imageDataUrl) {
  const div = document.createElement("div");
  div.className = `message ${role}`;

  if (role === "assistant") {
    div.innerHTML = marked.parse(text || "");
  } else {
    if (text) {
      const p = document.createElement("p");
      p.textContent = text;
      div.appendChild(p);
    }
    if (imageDataUrl) {
      const img = document.createElement("img");
      img.src = imageDataUrl;
      div.appendChild(img);
    }
  }

  messagesDiv.appendChild(div);
  scrollToBottom();
}

function scrollToBottom() {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
