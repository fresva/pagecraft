// PageCraft — WebSocket client and DOM manipulation

let ws = null;

function initWebSocket(pageId) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/${pageId}`;

    ws = new WebSocket(url);

    ws.onopen = function() {
        console.log('PageCraft WebSocket connected');
    };

    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
    };

    ws.onclose = function() {
        console.log('PageCraft WebSocket disconnected, reconnecting in 3s...');
        setTimeout(() => initWebSocket(pageId), 3000);
    };

    ws.onerror = function(err) {
        console.error('WebSocket error:', err);
    };
}

function handleServerMessage(data) {
    // Every message has an html field containing a self-targeting fragment
    // with hx-swap-oob or a target id. We parse and swap manually.
    if (!data.html) return;

    const temp = document.createElement('div');
    temp.innerHTML = data.html;

    // Process all OOB swap elements
    const elements = temp.querySelectorAll('[hx-swap-oob]');
    elements.forEach(el => {
        const swapType = el.getAttribute('hx-swap-oob');
        const targetId = el.id;
        const target = document.getElementById(targetId);

        if (!target) {
            console.warn(`OOB target not found: #${targetId}`);
            return;
        }

        if (swapType === 'beforeend') {
            // Append children to existing element
            while (el.firstChild) {
                target.appendChild(el.firstChild);
            }
        } else {
            // Replace entire element (swapType === 'true' or 'outerHTML')
            target.replaceWith(el);
        }
    });

    // If no OOB elements found, try to use the root element
    if (elements.length === 0) {
        const el = temp.firstElementChild;
        if (el && el.id) {
            const target = document.getElementById(el.id);
            if (target) {
                target.replaceWith(el);
            }
        }
    }

    // Auto-scroll chat on new messages
    if (data.type === 'chat') {
        scrollChatToBottom();
    }

    // Open the edit modal once its form content has been swapped in
    if (data.type === 'edit_form') {
        const modal = document.getElementById('edit-modal');
        if (modal) modal.hidden = false;
    }
}

function sendChatMessage(event) {
    event.preventDefault();
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text || !ws || ws.readyState !== WebSocket.OPEN) return false;

    ws.send(JSON.stringify({ type: 'chat', text: text }));
    input.value = '';
    input.focus();
    return false;
}

function sendComponentAction(componentId, action) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({
        type: 'component_action',
        component_id: componentId,
        action: action
    }));
}

function requestEdit(componentId) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ type: 'edit_request', component_id: componentId }));
}

function saveEdit() {
    const form = document.getElementById('edit-form');
    if (!form) return;
    const componentId = parseInt(form.dataset.componentId, 10);
    const fields = {};
    form.querySelectorAll('input[name], textarea[name]').forEach(el => {
        fields[el.name] = el.value;
    });
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'component_edit', component_id: componentId, fields: fields }));
    }
    closeEditModal();
}

function closeEditModal() {
    const modal = document.getElementById('edit-modal');
    if (modal) modal.hidden = true;
}

function scrollChatToBottom() {
    const chat = document.getElementById('chat-messages');
    if (chat) {
        requestAnimationFrame(() => {
            chat.scrollTop = chat.scrollHeight;
        });
    }
}

// Auto-scroll on page load
document.addEventListener('DOMContentLoaded', scrollChatToBottom);
