/**
 * chat.js — عميل WebSocket مع Streaming
 * يتواصل مع FastAPI backend
 */

const API = '';  // نفس الأصل (same-origin)
const WS_URL = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/chat`;

// ─── State ─────────────────────────────────────────────────────────
let token = null;
let username = null;
let ws = null;
let isStreaming = false;
let currentAiBubble = null;
let ragWasUsed = false;
let pingInterval = null;

// ─── DOM ────────────────────────────────────────────────────────────
const loginScreen   = document.getElementById('login-screen');
const chatScreen    = document.getElementById('chat-screen');
const inpUsername   = document.getElementById('inp-username');
const inpPassword   = document.getElementById('inp-password');
const loginBtn      = document.getElementById('login-btn');
const loginError    = document.getElementById('login-error');
const userInfo      = document.getElementById('user-info');
const usernameLabel = document.getElementById('username-label');
const logoutBtn     = document.getElementById('logout-btn');
const newChatBtn    = document.getElementById('new-chat-btn');
const convList      = document.getElementById('conv-list');
const messages      = document.getElementById('messages');
const emptyState    = document.getElementById('empty-state');
const msgInput      = document.getElementById('msg-input');
const sendBtn       = document.getElementById('send-btn');
const connIndicator = document.getElementById('conn-indicator');
const connStatusTxt = document.getElementById('conn-status-text');
const fileInput     = document.getElementById('file-input');
const uploadStatus  = document.getElementById('upload-status');
const ragStats      = document.getElementById('rag-stats');
const toast         = document.getElementById('toast');

// ─── Toast ──────────────────────────────────────────────────────────
function showToast(msg, duration = 3000) {
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), duration);
}

// ─── Login ──────────────────────────────────────────────────────────
loginBtn.addEventListener('click', doLogin);
[inpUsername, inpPassword].forEach(el =>
  el.addEventListener('keydown', e => { if (e.key === 'Enter') doLogin(); })
);

async function doLogin() {
  const u = inpUsername.value.trim();
  const p = inpPassword.value;
  if (!u || !p) return;

  loginBtn.disabled = true;
  loginBtn.textContent = 'جاري الدخول...';
  loginError.style.display = 'none';

  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: u, password: p }),
    });
    if (!res.ok) throw new Error('auth_fail');
    const data = await res.json();

    token = data.access_token;
    username = data.username;
    localStorage.setItem('ai_support_token', token);
    localStorage.setItem('ai_support_user', username);

    onLoggedIn();
  } catch {
    loginError.style.display = 'block';
  } finally {
    loginBtn.disabled = false;
    loginBtn.textContent = 'تسجيل الدخول';
  }
}

function onLoggedIn() {
  loginScreen.style.display = 'none';
  chatScreen.classList.add('show');
  userInfo.classList.add('show');
  usernameLabel.textContent = username;
  connectWebSocket();
  loadConversations();
  loadRagStats();
}

// ─── Logout ─────────────────────────────────────────────────────────
logoutBtn.addEventListener('click', () => {
  localStorage.removeItem('ai_support_token');
  localStorage.removeItem('ai_support_user');
  token = null; username = null;
  if (ws) ws.close();
  location.reload();
});

// ─── Auto-login from storage ─────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
  const t = localStorage.getItem('ai_support_token');
  const u = localStorage.getItem('ai_support_user');
  if (t && u) {
    token = t; username = u;
    inpUsername.value = u;
    onLoggedIn();
  }
});

// ─── WebSocket ──────────────────────────────────────────────────────
function connectWebSocket() {
  if (ws && ws.readyState <= 1) return;

  setConnStatus('connecting');
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    // أرسل رسالة المصادقة أولاً
    ws.send(JSON.stringify({ type: 'auth', token }));
  };

  ws.onmessage = ({ data }) => {
    let msg;
    try { msg = JSON.parse(data); } catch { return; }
    handleServerMessage(msg);
  };

  ws.onerror = () => {
    setConnStatus('offline');
    showToast('خطأ في الاتصال بالخادم');
  };

  ws.onclose = () => {
    setConnStatus('offline');
    clearInterval(pingInterval);
    // إعادة الاتصال بعد 5 ثوانٍ إذا كان المستخدم مسجلاً
    if (token) setTimeout(connectWebSocket, 5000);
  };
}

function handleServerMessage(msg) {
  switch (msg.type) {
    case 'connected':
      setConnStatus('online');
      startPing();
      showToast(`✅ متصل كـ ${msg.username}`);
      break;

    case 'start_stream':
      ragWasUsed = msg.rag_used || false;
      currentAiBubble = appendAiMessage('', ragWasUsed);
      isStreaming = true;
      setSendDisabled(true);
      break;

    case 'stream_chunk':
      if (currentAiBubble) {
        currentAiBubble.textContent += msg.content;
        currentAiBubble.classList.add('typing-cursor');
        scrollToBottom();
      }
      break;

    case 'end_stream':
      if (currentAiBubble) {
        currentAiBubble.classList.remove('typing-cursor');
      }
      isStreaming = false;
      currentAiBubble = null;
      setSendDisabled(false);
      msgInput.focus();
      break;

    case 'error':
      showToast(`❌ ${msg.message}`, 5000);
      isStreaming = false;
      setSendDisabled(false);
      if (currentAiBubble) {
        currentAiBubble.textContent = `⚠️ ${msg.message}`;
        currentAiBubble.style.color = '#f05050';
        currentAiBubble.classList.remove('typing-cursor');
      }
      currentAiBubble = null;
      break;

    case 'pong':
      break; // heartbeat ok
  }
}

function setConnStatus(state) {
  connIndicator.className = 'conn-indicator';
  if (state === 'online') {
    connIndicator.classList.add('online');
    connStatusTxt.textContent = 'متصل';
  } else if (state === 'offline') {
    connIndicator.classList.add('offline');
    connStatusTxt.textContent = 'غير متصل — إعادة الاتصال...';
  } else {
    connStatusTxt.textContent = 'جاري الاتصال...';
  }
}

function startPing() {
  clearInterval(pingInterval);
  pingInterval = setInterval(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }));
    }
  }, 25000);
}

// ─── Send Message ────────────────────────────────────────────────────
sendBtn.addEventListener('click', sendMessage);
msgInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});
msgInput.addEventListener('input', () => {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 140) + 'px';
});

function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || isStreaming || !ws || ws.readyState !== WebSocket.OPEN) return;

  hideEmptyState();
  appendUserMessage(text);
  msgInput.value = '';
  msgInput.style.height = 'auto';

  ws.send(JSON.stringify({ type: 'message', content: text }));
}

// ─── Message Rendering ───────────────────────────────────────────────
function appendUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'msg user';
  div.innerHTML = `
    <div class="msg-bubble">${escapeHtml(text)}</div>
    <div class="msg-meta">${timeNow()}</div>
  `;
  messages.appendChild(div);
  scrollToBottom();
}

function appendAiMessage(text = '', ragUsed = false) {
  const div = document.createElement('div');
  div.className = 'msg ai';

  const ragBadge = ragUsed
    ? `<div class="rag-badge">📚 من قاعدة المعرفة</div>`
    : '';

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.textContent = text;

  div.innerHTML = ragBadge;
  div.appendChild(bubble);
  div.insertAdjacentHTML('beforeend', `<div class="msg-meta">${timeNow()}</div>`);
  messages.appendChild(div);
  scrollToBottom();
  return bubble;
}

function scrollToBottom() {
  messages.scrollTo({ top: messages.scrollHeight, behavior: 'smooth' });
}

function hideEmptyState() {
  if (emptyState) emptyState.style.display = 'none';
}

function setSendDisabled(val) {
  sendBtn.disabled = val;
  msgInput.disabled = val;
}

function escapeHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
          .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

function timeNow() {
  return new Date().toLocaleTimeString('ar', { hour: '2-digit', minute: '2-digit' });
}

// ─── New Chat ────────────────────────────────────────────────────────
newChatBtn.addEventListener('click', () => {
  messages.innerHTML = '';
  messages.insertAdjacentHTML('beforeend', `
    <div id="empty-state">
      <div class="big-icon">💬</div>
      <h3>ابدأ محادثتك</h3>
      <p>اكتب سؤالك في المربع أدناه.</p>
    </div>
  `);
  // إعادة الاتصال بـ WS لإنشاء محادثة جديدة
  if (ws) ws.close();
  setTimeout(connectWebSocket, 300);
});

// ─── Conversations History ───────────────────────────────────────────
async function loadConversations() {
  try {
    const res = await apiFetch('/api/conversations');
    const data = await res.json();
    convList.innerHTML = '';
    data.forEach(c => {
      const item = document.createElement('div');
      item.className = 'conv-item';
      item.textContent = `💬 ${c.title || 'محادثة'} — ${new Date(c.created_at).toLocaleDateString('ar')}`;
      item.title = c.title;
      convList.appendChild(item);
    });
  } catch (e) {
    convList.innerHTML = '<div style="font-size:11px;color:var(--text-muted);padding:4px">لا يوجد سجل</div>';
  }
}

// ─── File Upload ─────────────────────────────────────────────────────
fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;

  uploadStatus.textContent = '⏳ جاري الرفع والفهرسة...';
  uploadStatus.className = '';

  const form = new FormData();
  form.append('file', file);

  try {
    const res = await apiFetch('/api/documents/upload', { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok) throw new Error(data.detail || 'Upload failed');

    uploadStatus.textContent = `✅ ${data.chunks_indexed} قطعة مفهرسة`;
    uploadStatus.className = 'ok';
    loadRagStats();
    showToast(`📚 تم فهرسة ${file.name}`);
  } catch (e) {
    uploadStatus.textContent = `❌ ${e.message}`;
    uploadStatus.className = 'err';
    showToast(`❌ فشل رفع ${file.name}`, 4000);
  }

  fileInput.value = '';
});

// ─── RAG Stats ───────────────────────────────────────────────────────
async function loadRagStats() {
  try {
    const res = await apiFetch('/api/rag/stats');
    const data = await res.json();
    ragStats.innerHTML = `
      📊 متجهات: <strong>${data.total_vectors}</strong><br/>
      📄 قطع: <strong>${data.total_chunks}</strong><br/>
      🔍 FAISS: <strong>${data.faiss_available ? '✅ نشط' : '❌ غير متاح'}</strong>
    `;
  } catch {
    ragStats.textContent = 'تعذّر تحميل الإحصائيات';
  }
}

// ─── API Helper ──────────────────────────────────────────────────────
function apiFetch(path, opts = {}) {
  return fetch(`${API}${path}`, {
    ...opts,
    headers: {
      ...(opts.headers || {}),
      ...(opts.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      Authorization: `Bearer ${token}`,
    },
  });
}