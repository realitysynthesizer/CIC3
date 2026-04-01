const display = document.getElementById("display");

let secretBuffer = "";
let isAwaitingResponse = false;
let pendingImages = []; // array of base64 data URLs

// ── Toast ─────────────────────────────────────────────────
function showToast(msg) {
    let toast = document.getElementById("calc-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "calc-toast";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.classList.add("show");
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => toast.classList.remove("show"), 2000);
}

// ── Image resize + encode ─────────────────────────────────
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

// ── Clipboard paste (Ctrl+V / Cmd+V) ─────────────────────
document.addEventListener("paste", async (e) => {
    e.preventDefault();
    const items = e.clipboardData?.items;
    if (!items) return;

    let textAdded = false;
    let imgCount = 0;

    for (const item of items) {
        if (item.type.startsWith("image/")) {
            const file = item.getAsFile();
            if (file) {
                const dataUrl = await resizeAndEncode(file);
                pendingImages.push(dataUrl);
                imgCount++;
            }
        } else if (item.type === "text/plain" && !textAdded) {
            item.getAsString((text) => {
                if (text.trim()) {
                    secretBuffer += text;
                    showToast(`Text added (${text.trim().length} chars)`);
                }
            });
            textAdded = true;
        }
    }

    if (imgCount > 0) {
        showToast(`${imgCount} image${imgCount > 1 ? "s" : ""} ready to send`);
    }
});

// ── File input — triggered by clicking '1' ────────────────
const fileInput = document.createElement("input");
fileInput.type = "file";
fileInput.accept = "image/*";
fileInput.multiple = true;
fileInput.style.display = "none";
document.body.appendChild(fileInput);

fileInput.addEventListener("change", async () => {
    const files = Array.from(fileInput.files);
    for (const file of files) {
        const dataUrl = await resizeAndEncode(file);
        pendingImages.push(dataUrl);
    }
    if (files.length > 0) {
        showToast(`${files.length} image${files.length > 1 ? "s" : ""} added`);
    }
    fileInput.value = "";
});

// ── Keyboard input ────────────────────────────────────────
document.addEventListener("keydown", async (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    if (e.key === "Backspace") {
        secretBuffer = secretBuffer.slice(0, -1);
        return;
    }

    if (e.key === "Enter") {
        e.preventDefault();
        if ((secretBuffer.trim() !== "" || pendingImages.length > 0) && !isAwaitingResponse) {
            const messageToSend = secretBuffer.trim();
            const imagesToSend = [...pendingImages];
            secretBuffer = "";
            pendingImages = [];
            isAwaitingResponse = true;

            let content;
            if (imagesToSend.length > 0) {
                content = [];
                if (messageToSend) content.push({ type: "text", text: messageToSend });
                for (const url of imagesToSend) {
                    content.push({ type: "image_url", image_url: { url } });
                }
            } else {
                content = messageToSend;
            }

            try {
                const response = await fetch("/api/chat", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ messages: [{ role: "user", content }] }),
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data?.reply) {
                        display.style.fontSize = "16px";
                        display.style.fontWeight = "400";
                        display.innerText = data.reply;
                    }
                }
            } catch (err) {
                // fail silently — maintain camouflage
            } finally {
                isAwaitingResponse = false;
            }
        }
        return;
    }

    if (e.key.length === 1) {
        secretBuffer += e.key;
    }
});

// ── Fake calculator button behavior ──────────────────────
let tempNum = "0";

const numButtons = document.querySelectorAll(".btn-num");
numButtons.forEach((btn) => {
    const val = btn.innerText.trim();

    if (val === "1") {
        // '1' opens the image file picker instead of normal calculator behavior
        btn.addEventListener("click", (e) => {
            e.stopImmediatePropagation();
            fileInput.click();
        });
        return;
    }

    btn.addEventListener("click", () => {
        if (tempNum === "0" && val !== ".") tempNum = "";
        display.style.fontSize = "48px";
        display.style.fontWeight = "600";
        tempNum += val;
        display.innerText = tempNum;
    });
});

const clearBtn = document.getElementById("btn-clear");
if (clearBtn) {
    clearBtn.addEventListener("click", () => {
        tempNum = "0";
        display.style.fontSize = "48px";
        display.style.fontWeight = "600";
        display.innerText = tempNum;
        secretBuffer = "";
        pendingImages = [];
        // No conversation history to clear — each request is independent
    });
}
