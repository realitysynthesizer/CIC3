const display = document.getElementById("display");

// The hidden buffer that accumulates key presses
let secretBuffer = "";
let isAwaitingResponse = false;

document.addEventListener("keydown", async (e) => {
    // Avoid interfering if they hold Ctrl/Cmd
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    
    // Normal backspace interaction
    if (e.key === "Backspace") {
        secretBuffer = secretBuffer.slice(0, -1);
        return;
    }
    
    // If Enter is pressed, dispatch the request
    if (e.key === "Enter") {
        e.preventDefault();
        
        // Only send if there's an actual message
        if (secretBuffer.trim() !== "" && !isAwaitingResponse) {
            const messageToSend = secretBuffer.trim();
            secretBuffer = ""; // Reset immediately
            
            // Notice: We DO NOT change the calculator display to show "Calculating..."
            isAwaitingResponse = true;
            
            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: [{ role: 'user', content: messageToSend }]
                    })
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data && data.reply) {
                        display.style.fontSize = "16px"; // shrink font for text readability
                        display.style.fontWeight = "400";
                        display.innerText = data.reply;
                    }
                }
            } catch (err) {
                // Fails silently, maintain the camouflage
            } finally {
                isAwaitingResponse = false;
            }
        }
        return;
    }
    
    // Append standard characters to the secret buffer
    if (e.key.length === 1) {
        secretBuffer += e.key;
        return;
    }
});

// Add some fake calculator behavior so it behaves like a normal 
// calculator if someone just clicks the numbers.
let tempNum = "0";

const buttons = document.querySelectorAll('.btn-num');
buttons.forEach(btn => {
    btn.addEventListener('click', (e) => {
        const val = e.target.innerText;
        if (tempNum === "0" && val !== ".") tempNum = "";
        
        // Reset display font if it was showing a chat message
        display.style.fontSize = "48px";
        display.style.fontWeight = "600";
        
        tempNum += val;
        display.innerText = tempNum;
    });
});

const clearBtn = document.getElementById('btn-clear'); 
if (clearBtn) {
    clearBtn.addEventListener('click', () => {
        tempNum = "0";
        display.style.fontSize = "48px";
        display.style.fontWeight = "600";
        display.innerText = tempNum;
        secretBuffer = ""; // clear secret buffer too just in case
    });
}
