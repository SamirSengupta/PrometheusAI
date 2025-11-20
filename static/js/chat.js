// Firebase Configuration
const firebaseConfig = {
    apiKey: "AIzaSyAPmNRiyRQFtA9U5V7b2nqoDDOGJa5KLpo",
    authDomain: "peteai-3536c.firebaseapp.com",
    projectId: "peteai-3536c",
    storageBucket: "peteai-3536c.firebasestorage.app",
    messagingSenderId: "949807627453",
    appId: "1:949807627453:web:81b13a46fbbf462c3b0bd4",
    measurementId: "G-803TL0LL28"
};

// Initialize Firebase
firebase.initializeApp(firebaseConfig);
const auth = firebase.auth();

// UI Elements
const sidebar = document.getElementById('sidebar');
const toggleSidebar = document.getElementById('toggleSidebar');
const sidebarIcon = document.getElementById('sidebarIcon');
const newChatBtn = document.getElementById('newChatBtn');
const chatInput = document.getElementById('chatInput');
const sendBtn = document.getElementById('sendBtn');
const chatContainer = document.getElementById('chatContainer').querySelector('.message-container');
const chatList = document.getElementById('chatList');
const welcomeMessage = document.getElementById('welcomeMessage');

// File upload elements
const uploadBtn = document.getElementById('uploadBtn');
const fileInput = document.getElementById('fileInput');
const uploadedFileDisplay = document.getElementById('uploadedFileDisplay');

// Auth UI Elements
const googleLoginBtn = document.getElementById('googleLoginBtn');
const userProfile = document.getElementById('userProfile');
const userAvatar = document.getElementById('userAvatar');
const userName = document.getElementById('userName');
const userEmail = document.getElementById('userEmail');
const logoutBtn = document.getElementById('logoutBtn');

// Send/Stop button icons
const sendIcon = document.getElementById('sendIcon');
const stopIcon = document.getElementById('stopIcon');

let currentChatId = null;
let isProcessing = false;
let currentUser = null;
let currentReader = null;
let uploadedDocument = null;

// File upload handler
uploadBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    if (file.size > 16 * 1024 * 1024) {
        alert('File size must be less than 16MB');
        fileInput.value = '';
        return;
    }

    showProcessingBadge(file.name);

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.success) {
            uploadedDocument = {
                file_name: data.file_name,
                file_type: data.file_type,
                text: data.text,
                method: data.method,
                pages: data.pages
            };

            hideProcessingBadge();
            showFileBadge(data.file_name, data.file_type, data.pages);
            
            console.log('File uploaded successfully:', data);
        } else {
            hideProcessingBadge();
            alert(`Upload failed: ${data.error}`);
        }
    } catch (error) {
        hideProcessingBadge();
        console.error('Upload error:', error);
        alert('Failed to upload file. Please try again.');
    }

    fileInput.value = '';
});

function showProcessingBadge(filename) {
    uploadedFileDisplay.classList.remove('hidden');
    uploadedFileDisplay.querySelector('.max-w-4xl').innerHTML = `
        <div class="processing-badge">
            <div class="processing-spinner"></div>
            <span>Processing ${filename}...</span>
        </div>
    `;
}

function hideProcessingBadge() {
    const processingBadge = uploadedFileDisplay.querySelector('.processing-badge');
    if (processingBadge) {
        processingBadge.remove();
    }
}

function showFileBadge(filename, filetype, pages) {
    uploadedFileDisplay.classList.remove('hidden');
    const icon = filetype === 'pdf' 
        ? '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>'
        : '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>';
    
    const pagesInfo = pages ? ` (${pages} pages)` : '';
    
    uploadedFileDisplay.querySelector('.max-w-4xl').innerHTML = `
        <div class="file-badge">
            ${icon}
            <span>${filename}${pagesInfo}</span>
            <div class="file-badge-close" onclick="clearUploadedFile()">
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
            </div>
        </div>
    `;
}

function clearUploadedFile() {
    uploadedDocument = null;
    uploadedFileDisplay.classList.add('hidden');
    uploadedFileDisplay.querySelector('.max-w-4xl').innerHTML = '';
}

window.clearUploadedFile = clearUploadedFile;

function toggleSendStopButton(showStop) {
    if (showStop) {
        sendIcon.classList.add('hidden');
        stopIcon.classList.remove('hidden');
    } else {
        sendIcon.classList.remove('hidden');
        stopIcon.classList.add('hidden');
    }
}

function stopGeneration() {
    console.log('Stopping generation...');
    
    if (currentReader) {
        try {
            currentReader.cancel();
            currentReader = null;
            console.log('Stream cancelled successfully');
        } catch (error) {
            console.error('Error cancelling stream:', error);
        }
    }
    
    isProcessing = false;
    chatInput.disabled = false;
    sendBtn.disabled = false;
    toggleSendStopButton(false);
    chatInput.focus();
}

auth.onAuthStateChanged((user) => {
    if (user) {
        currentUser = user;
        googleLoginBtn.classList.add('hidden');
        userProfile.classList.remove('hidden');
        
        userAvatar.src = user.photoURL || 'https://ui-avatars.com/api/?name=' + encodeURIComponent(user.displayName || 'User');
        userName.textContent = user.displayName || 'User';
        userEmail.textContent = user.email;
        
        console.log('User signed in:', user.displayName);
        loadChats();
    } else {
        currentUser = null;
        googleLoginBtn.classList.remove('hidden');
        userProfile.classList.add('hidden');
        chatList.innerHTML = '';
        console.log('User signed out');
    }
});

googleLoginBtn.addEventListener('click', async () => {
    const provider = new firebase.auth.GoogleAuthProvider();
    try {
        const result = await auth.signInWithPopup(provider);
        console.log('Successfully signed in:', result.user.displayName);
    } catch (error) {
        console.error('Error signing in:', error);
        alert(`Failed to sign in: ${error.message}`);
    }
});

logoutBtn.addEventListener('click', async () => {
    try {
        await auth.signOut();
        currentChatId = null;
        chatContainer.innerHTML = '';
        welcomeMessage.style.display = 'block';
        clearUploadedFile();
        console.log('Successfully signed out');
    } catch (error) {
        console.error('Error signing out:', error);
        alert('Failed to sign out. Please try again.');
    }
});

toggleSidebar.addEventListener('click', () => {
    sidebar.classList.toggle('-translate-x-full');
    sidebar.classList.toggle('translate-x-0');
    if (sidebar.classList.contains('-translate-x-full')) {
        sidebarIcon.innerHTML = '<polyline points="9 18 15 12 9 6"></polyline>';
    } else {
        sidebarIcon.innerHTML = '<polyline points="15 18 9 12 15 6"></polyline>';
    }
});

newChatBtn.addEventListener('click', async () => {
    if (!currentUser) {
        alert('Please login to save chats. You can chat anonymously without saving.');
        return;
    }
    
    try {
        const response = await fetch('/api/new-chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                user_id: currentUser.uid 
            })
        });
        const data = await response.json();
        
        if (data.success) {
            currentChatId = data.chat_id;
            chatContainer.innerHTML = '';
            welcomeMessage.style.display = 'block';
            clearUploadedFile();
            chatInput.focus();
            await loadChats();
        }
    } catch (error) {
        console.error('Error starting new chat:', error);
        alert('Failed to create new chat. Please try again.');
    }
});

async function loadChats() {
    if (!currentUser) return;
    
    try {
        const response = await fetch(`/api/chats?user_id=${currentUser.uid}`);
        const data = await response.json();
        
        if (data.success) {
            renderChatList(data.chats);
        }
    } catch (error) {
        console.error('Error loading chats:', error);
    }
}

function renderChatList(chats) {
    chatList.innerHTML = '';
    
    chats.forEach(chat => {
        const chatItem = document.createElement('button');
        chatItem.className = 'chat-item w-full rounded-md';
        if (chat.id === currentChatId) {
            chatItem.classList.add('active');
        }
        
        const content = document.createElement('div');
        content.className = 'chat-item-content';
        
        const title = document.createElement('span');
        title.className = 'chat-item-title';
        title.textContent = chat.title || 'New chat';
        
        const deleteBtn = document.createElement('span');
        deleteBtn.className = 'chat-item-delete';
        deleteBtn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>';
        
        deleteBtn.addEventListener('click', async (e) => {
            e.stopPropagation();
            if (confirm('Delete this chat?')) {
                await deleteChat(chat.id);
            }
        });
        
        content.appendChild(title);
        content.appendChild(deleteBtn);
        chatItem.appendChild(content);
        
        chatItem.addEventListener('click', () => switchToChat(chat.id));
        
        chatList.appendChild(chatItem);
    });
}

async function switchToChat(chatId) {
    if (!currentUser) {
        alert('Please login to access saved chats.');
        return;
    }
    
    try {
        const response = await fetch(`/api/chats/${chatId}?user_id=${currentUser.uid}`);
        const data = await response.json();
        
        if (data.success) {
            currentChatId = chatId;
            chatContainer.innerHTML = '';
            welcomeMessage.style.display = 'none';
            clearUploadedFile();
            
            const messages = data.chat.messages || [];
            messages.forEach(msg => {
                if (msg.role === 'user') {
                    appendMessage(msg.content, 'user', false);
                } else if (msg.role === 'assistant') {
                    appendMessage(msg.content, 'ai', false);
                }
            });
            
            setTimeout(() => {
                chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;
            }, 50);
            
            await loadChats();
        }
    } catch (error) {
        console.error('Error switching chat:', error);
    }
}

async function deleteChat(chatId) {
    if (!currentUser) return;
    
    try {
        const response = await fetch(`/api/chats/${chatId}?user_id=${currentUser.uid}`, {
            method: 'DELETE'
        });
        const data = await response.json();
        
        if (data.success) {
            if (chatId === currentChatId) {
                currentChatId = null;
                chatContainer.innerHTML = '';
                welcomeMessage.style.display = 'block';
                clearUploadedFile();
            }
            await loadChats();
        }
    } catch (error) {
        console.error('Error deleting chat:', error);
    }
}

sendBtn.addEventListener('click', () => {
    if (isProcessing) {
        stopGeneration();
    } else {
        sendMessage();
    }
});

chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !isProcessing) {
        sendMessage();
    }
});

async function sendMessage() {
    const message = chatInput.value.trim();
    if (message === '' || isProcessing) return;

    isProcessing = true;
    toggleSendStopButton(true);
    welcomeMessage.style.display = 'none';
    
    appendMessage(message, 'user');
    chatInput.value = '';
    chatInput.disabled = true;
    sendBtn.disabled = false;
    
    const typingId = appendTypingIndicator();

    const streamId = 'stream-' + Date.now();
    const aiWrapper = document.createElement('div');
    aiWrapper.classList.add('flex', 'items-start', 'gap-4', 'mb-4', 'ai-message');

    const avatar = document.createElement('div');
    avatar.classList.add('w-8', 'h-8', 'rounded-full', 'flex', 'items-center', 'justify-center', 'flex-shrink-0', 'border', 'bg-white', 'border-gray-700', 'p-1');
    avatar.innerHTML = `<img src="/static/images/peacock-logo.png" class="w-6 h-6 object-cover">`;

    const messageContent = document.createElement('div');
    messageContent.classList.add('max-w-[80%]', 'p-3', 'rounded-lg');
    const p = document.createElement('div');
    p.id = streamId;
    p.classList.add('message-text');
    messageContent.appendChild(p);

    aiWrapper.appendChild(avatar);
    aiWrapper.appendChild(messageContent);
    chatContainer.appendChild(aiWrapper);
    chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;

    let isSearching = false;
    let searchAnimationEl = null;
    
    try {
        const requestBody = { 
            message: message,
            chat_id: currentChatId,
            user_id: currentUser ? currentUser.uid : null
        };

        if (uploadedDocument) {
            requestBody.document_context = uploadedDocument.text;
        }

        const resp = await fetch('/api/chat/stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        if (!resp.ok) {
            removeTypingIndicator(typingId);
            const errorText = await resp.text();
            appendMessage('Error: ' + errorText, 'ai');
            isProcessing = false;
            toggleSendStopButton(false);
            chatInput.disabled = false;
            return;
        }

        const decoder = new TextDecoder('utf-8');
        const readerStream = resp.body.getReader();
        currentReader = readerStream;
        
        let { value, done } = await currentReader.read();
        let buffer = '';
        let fullText = '';
        
        while (!done && currentReader) {
            buffer += decoder.decode(value, { stream: true });

            let parts = buffer.split('\n\n');
            buffer = parts.pop();

            for (const part of parts) {
                const line = part.trim();
                if (!line) continue;

                let jsonText = line.startsWith('data:') ? line.slice(5).trim() : line;
                try {
                    const payload = JSON.parse(jsonText);
                    if (payload.type === 'delta') {
                        if (payload.delta.includes('[Searching the web...]')) {
                            removeTypingIndicator(typingId);
                            isSearching = true;
                            searchAnimationEl = appendSearchAnimation();
                        } else {
                            if (isSearching && searchAnimationEl) {
                                removeSearchAnimation(searchAnimationEl);
                                isSearching = false;
                                searchAnimationEl = null;
                            }
                            
                            fullText += payload.delta;
                            p.innerHTML = formatText(fullText);
                            highlightCodeBlocks(p);
                            chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;
                        }
                    } else if (payload.type === 'done') {
                        removeTypingIndicator(typingId);
                        if (searchAnimationEl) {
                            removeSearchAnimation(searchAnimationEl);
                        }
                        currentChatId = payload.chat_id || currentChatId;
                        await loadChats();
                        isProcessing = false;
                        toggleSendStopButton(false);
                        chatInput.disabled = false;
                        sendBtn.disabled = false;
                        chatInput.focus();
                        currentReader = null;
                    } else if (payload.type === 'error') {
                        removeTypingIndicator(typingId);
                        if (searchAnimationEl) {
                            removeSearchAnimation(searchAnimationEl);
                        }
                        p.innerHTML = 'Error: ' + escapeHtml(payload.error || 'Unknown error');
                        isProcessing = false;
                        toggleSendStopButton(false);
                        chatInput.disabled = false;
                        sendBtn.disabled = false;
                        currentReader = null;
                    }
                } catch (e) {
                    console.error('Parse error:', e);
                }
            }

            if (currentReader) {
                ({ value, done } = await currentReader.read());
            } else {
                break;
            }
        }

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Stream was cancelled by user');
            p.innerHTML = formatText(fullText + '\n\n[Generation stopped by user]');
        } else {
            removeTypingIndicator(typingId);
            if (searchAnimationEl) {
                removeSearchAnimation(searchAnimationEl);
            }
            const pEl = document.getElementById(streamId);
            if (pEl) pEl.innerHTML = formatText('Sorry, I could not connect to the server. Please ensure the Flask app is running.');
            console.error('Streaming error:', error);
        }
    } finally {
        if (currentReader) {
            try { 
                await currentReader.cancel(); 
            } catch (e) {
                console.log('Reader already closed');
            }
            currentReader = null;
        }
        isProcessing = false;
        toggleSendStopButton(false);
        chatInput.disabled = false;
        sendBtn.disabled = false;
        chatInput.focus();
    }
}

function appendMessage(message, sender, scroll = true) {
    const messageWrapper = document.createElement('div');
    messageWrapper.classList.add('flex', 'items-start', 'gap-4', 'mb-4');
    
    if (sender === 'user') {
        messageWrapper.classList.add('justify-end', 'user-message');
    } else {
        messageWrapper.classList.add('ai-message');
    }

    const avatar = document.createElement('div');
    avatar.classList.add('w-8', 'h-8', 'rounded-full', 'flex', 'items-center', 'justify-center', 'flex-shrink-0', 'border');
    
    const messageContent = document.createElement('div');
    messageContent.classList.add('max-w-[80%]', 'p-3', 'rounded-lg');

    if (sender === 'user') {
        avatar.classList.add('bg-blue-800', 'border-blue-700');
        avatar.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="w-4 h-4"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>`;
        messageContent.innerHTML = `<div class="message-text">${formatText(message)}</div>`;
        messageWrapper.appendChild(messageContent);
        messageWrapper.appendChild(avatar);
    } else {
        avatar.classList.add('bg-white', 'border-gray-700');
        avatar.innerHTML = `<img src="/static/images/peacock-logo.png" class="w-6 h-6 object-cover">`;
        const textDiv = document.createElement('div');
        textDiv.classList.add('message-text');
        textDiv.innerHTML = formatText(message);
        messageContent.appendChild(textDiv);
        messageWrapper.appendChild(avatar);
        messageWrapper.appendChild(messageContent);
        
        setTimeout(() => highlightCodeBlocks(textDiv), 0);
    }

    chatContainer.appendChild(messageWrapper);
    
    if (scroll) {
        chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;
    }
}

function appendSearchAnimation() {
    const searchWrapper = document.createElement('div');
    const searchId = 'search-' + Date.now();
    searchWrapper.id = searchId;
    searchWrapper.classList.add('flex', 'items-start', 'gap-4', 'mb-4', 'ai-message');

    const avatar = document.createElement('div');
    avatar.classList.add('w-8', 'h-8', 'rounded-full', 'flex', 'items-center', 'justify-center', 'flex-shrink-0', 'border', 'bg-white', 'border-gray-700', 'p-1');
    avatar.innerHTML = `<img src="/static/images/peacock-logo.png" class="w-6 h-6 object-cover">`;

    const messageContent = document.createElement('div');
    messageContent.classList.add('max-w-[80%]');
    messageContent.innerHTML = `
        <div class="search-animation">
            <div class="search-spinner"></div>
            <span class="search-text">Searching the web</span>
            <div class="search-pulse">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;

    searchWrapper.appendChild(avatar);
    searchWrapper.appendChild(messageContent);
    chatContainer.appendChild(searchWrapper);
    chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;

    return searchId;
}

function removeSearchAnimation(searchId) {
    const element = document.getElementById(searchId);
    if (element) {
        element.style.transition = 'opacity 0.3s';
        element.style.opacity = '0';
        setTimeout(() => {
            element.remove();
        }, 300);
    }
}

function formatText(text) {
    if (!text) return '';
    
    try {
        let formatted = text;
        
        formatted = formatted.replace(
            /```(\w+)?[^\n]*\n([\s\S]*?)```/g,
            (match, lang, code) => {
                const language = lang || 'plaintext';
                const codeId = 'code-' + Math.random().toString(36).substr(2, 9);
                const escapedCode = escapeHtml(code.trim());
                return `___CODE_BLOCK_${codeId}___${language}___${escapedCode}___END_CODE_BLOCK___`;
            }
        );
        
        formatted = escapeHtml(formatted);
        formatted = formatted.replace(/`([^`\n]+)`/g, '<code class="inline-code">$1</code>');
        formatted = formatted.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        formatted = formatted.replace(/\*(.+?)\*/g, '<em>$1</em>');
        formatted = formatted.replace(/\n/g, '<br>');
        
        formatted = formatted.replace(
            /___CODE_BLOCK_([^_]+)___([^_]+)___(.+?)___END_CODE_BLOCK___/g,
            (match, codeId, language, code) => {
                code = code.replace(/<br>/g, '\n');
                return `
                    <div class="code-block-container">
                        <div class="code-block-header">
                            <span class="code-language">${language}</span>
                            <button class="copy-button" onclick="copyCode(this, '${codeId}')">
                                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                                <span class="copy-text">Copy code</span>
                            </button>
                        </div>
                        <div class="code-block-body">
                            <pre><code id="${codeId}" class="language-${language}">${code}</code></pre>
                        </div>
                    </div>
                `;
            }
        );
        
        return formatted;
    } catch (e) {
        console.error('Format error:', e);
        return escapeHtml(text);
    }
}

function appendTypingIndicator() {
    const messageWrapper = document.createElement('div');
    const typingId = 'typing-' + Date.now();
    messageWrapper.id = typingId;
    messageWrapper.classList.add('flex', 'items-start', 'gap-4', 'mb-4', 'ai-message');

    const avatar = document.createElement('div');
    avatar.classList.add('w-8', 'h-8', 'rounded-full', 'flex', 'items-center', 'justify-center', 'flex-shrink-0', 'border', 'bg-white', 'border-gray-700', 'p-1');
    avatar.innerHTML = `<img src="/static/images/peacock-logo.png" class="w-6 h-6 object-cover">`;

    const messageContent = document.createElement('div');
    messageContent.classList.add('max-w-[80%]', 'p-3', 'rounded-lg');
    messageContent.innerHTML = `<div class="typing-indicator"><span></span><span></span><span></span></div>`;

    messageWrapper.appendChild(avatar);
    messageWrapper.appendChild(messageContent);
    chatContainer.appendChild(messageWrapper);
    chatContainer.parentElement.scrollTop = chatContainer.parentElement.scrollHeight;

    return typingId;
}

function removeTypingIndicator(typingId) {
    const element = document.getElementById(typingId);
    if (element) {
        element.remove();
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function copyCode(button, codeId) {
    const codeElement = document.getElementById(codeId);
    if (!codeElement) return;
    
    const text = codeElement.textContent;
    
    navigator.clipboard.writeText(text).then(() => {
        const textSpan = button.querySelector('.copy-text');
        const originalText = textSpan.textContent;
        
        button.classList.add('copied');
        textSpan.textContent = 'Copied!';
        
        setTimeout(() => {
            button.classList.remove('copied');
            textSpan.textContent = originalText;
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy code to clipboard');
    });
}

window.copyCode = copyCode;

function highlightCodeBlocks(container) {
    const codeBlocks = container.querySelectorAll('pre code');
    codeBlocks.forEach((block) => {
        if (!block.dataset.highlighted) {
            hljs.highlightElement(block);
            block.dataset.highlighted = 'yes';
        }
    });
}

if (currentUser) {
    loadChats();
}