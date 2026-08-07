import makeWASocket, { DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } from '@whiskeysockets/baileys';
import express from 'express';
import qrcode from 'qrcode-terminal';
import QRCode from 'qrcode';
import pino from 'pino';
import { Boom } from '@hapi/boom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.WA_BRIDGE_PORT || 3100;
const BACKEND_URL = process.env.SALAR_BACKEND_URL || 'http://127.0.0.1:8000';
// Base auth dir; each user's auth state lives in AUTH_DIR/<userId>
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, 'auth');

const logger = pino({ level: 'silent' });

const app = express();
app.use(express.json({ limit: '10mb' }));

// Per-user sessions: Map<userId, session>
// session = { sock, status, qr, reason, chats, store, timer }
const sessions = new Map();

function authDirFor(userId) {
  return path.join(AUTH_DIR, sanitizeUserId(userId));
}

function sanitizeUserId(userId) {
  // Prevent traversal via user id (ids may contain dots in test fixtures)
  return String(userId).replace(/[^a-zA-Z0-9._@-]/g, '_');
}

function getUserId(req) {
  const userId = req.headers['x-user-id'];
  if (!userId || String(userId).trim() === '') return null;
  return String(userId).trim();
}

function getSession(req) {
  const userId = getUserId(req);
  if (!userId) return null;
  return sessions.get(userId) || null;
}

async function startSession(userId) {
  const dir = authDirFor(userId);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  const { state, saveCreds } = await useMultiFileAuthState(dir);
  const { version } = await fetchLatestBaileysVersion();

  const session = {
    sock: null,
    status: 'connecting',
    qr: null,
    reason: null,
    chats: [],
    store: new Map(),
    timer: null,
  };
  sessions.set(userId, session);

  const sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    printQRInTerminal: false,
    browser: ['SALAR AI', 'Chrome', '120.0'],
  });
  session.sock = sock;

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      session.qr = qr;
      session.status = 'waiting_scan';
      console.log(`\n[WA:${userId}] === WhatsApp QR Code ===`);
      qrcode.generate(qr, { small: true });
      console.log(`[WA:${userId}] Scan with WhatsApp on your phone\n`);
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      session.reason = statusCode;
      session.status = 'disconnected';

      if (statusCode !== DisconnectReason.loggedOut) {
        console.log(`[WA:${userId}] Connection closed, reconnecting...`);
        session.timer = setTimeout(() => startSession(userId), 3000);
      } else {
        console.log(`[WA:${userId}] Logged out — clearing session and re-pairing...`);
        session.status = 'logged_out';
        session.qr = null;
        session.chats = [];
        session.store.clear();
        try {
          fs.rmSync(dir, { recursive: true, force: true });
        } catch (e) {
          console.error(`[WA:${userId}] Failed to clear auth dir:`, e.message);
        }
        session.timer = setTimeout(() => startSession(userId), 1500);
      }
    }

    if (connection === 'open') {
      session.status = 'connected';
      session.qr = null;
      console.log(`[WA:${userId}] WhatsApp connected!`);
    }
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return;

    for (const msg of messages) {
      if (msg.key.fromMe) continue;
      if (!msg.message) continue;

      const from = msg.key.remoteJid;
      const isGroup = from.endsWith('@g.us');
      const text = extractText(msg.message);
      const senderName = msg.pushName || 'Unknown';

      console.log(`[WA:${userId}] ${isGroup ? 'Group' : 'DM'} from ${senderName}: ${text?.substring(0, 100) || '[media]'}`);

      const chatMsgs = session.store.get(from) || [];
      chatMsgs.push({ id: msg.key.id, fromMe: false, text: text || '[media]', timestamp: msg.messageTimestamp, senderName });
      if (chatMsgs.length > 50) chatMsgs.splice(0, chatMsgs.length - 50);
      session.store.set(from, chatMsgs);

      forwardToBackend(userId, from, senderName, text, isGroup).catch(() => {});

      updateRecentChat(session, from, senderName, text, false);
    }
  });

  return session;
}

function extractText(message) {
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
  if (message.imageMessage?.caption) return message.imageMessage.caption;
  if (message.videoMessage?.caption) return message.videoMessage.caption;
  return '';
}

async function forwardToBackend(userId, jid, senderName, text, isGroup) {
  if (!text) return;
  try {
    await fetch(`${BACKEND_URL}/api/whatsapp/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, from: jid, sender_name: senderName, text, is_group: isGroup, timestamp: Date.now() }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {}
}

function updateRecentChat(session, jid, name, text, fromMe) {
  const existing = session.chats.find(c => c.jid === jid);
  if (existing) {
    existing.lastMessage = text || '';
    existing.unread = fromMe ? 0 : (existing.unread || 0) + 1;
  } else {
    session.chats.unshift({ jid, name: name || jid.split('@')[0], lastMessage: text || '', unread: fromMe ? 0 : 1 });
  }
  if (session.chats.length > 100) session.chats.length = 100;
}

// Ensure a session exists for the requested user (lazy start).
async function ensureSession(req, res) {
  const userId = getUserId(req);
  if (!userId) {
    res.status(400).json({ error: 'x-user-id header is required' });
    return null;
  }
  if (!sessions.has(userId)) {
    try {
      await startSession(userId);
    } catch (e) {
      console.error(`[WA:${userId}] Session start failed:`, e.message);
    }
  }
  return sessions.get(userId) || null;
}

// === REST API ===

app.get('/status', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  res.json({
    status: session.status,
    has_qr: !!session.qr,
    phone_number: session.sock?.user?.id?.split(':')[0] || null,
    name: session.sock?.user?.name || null,
    last_disconnect: session.reason,
  });
});

app.get('/qr', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  if (!session.qr) return res.json({ qr: null, status: session.status, image: null });
  let image = null;
  try {
    image = await QRCode.toDataURL(session.qr, { width: 320, margin: 2 });
  } catch (e) {
    console.error(`[WA] QR image generation failed:`, e.message);
  }
  res.json({ qr: session.qr, status: session.status, image });
});

app.post('/send', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  if (session.status !== 'connected' || !session.sock) {
    return res.status(503).json({ error: 'WhatsApp not connected' });
  }

  const { to, text, phone } = req.body;
  if (!text) return res.status(400).json({ error: 'text is required' });

  let jid = to;
  if (phone && !to) {
    const clean = phone.replace(/[^0-9]/g, '');
    jid = clean + '@s.whatsapp.net';
  }
  if (!jid) return res.status(400).json({ error: 'to or phone is required' });

  try {
    const result = await session.sock.sendMessage(jid, { text });

    const chatMsgs = session.store.get(jid) || [];
    chatMsgs.push({ id: result.key.id, fromMe: true, text, timestamp: Date.now(), senderName: 'Me' });
    if (chatMsgs.length > 50) chatMsgs.splice(0, chatMsgs.length - 50);
    session.store.set(jid, chatMsgs);

    updateRecentChat(session, jid, '', text, true);
    res.json({ ok: true, id: result.key.id, jid });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/chats', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  res.json(session.chats);
});

app.get('/messages/:jid', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  const { jid } = req.params;
  const limit = parseInt(req.query.limit) || 20;
  const msgs = session.store.get(jid) || [];
  res.json(msgs.slice(-limit));
});

app.get('/contacts', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  if (session.status !== 'connected' || !session.sock?.store?.contacts) {
    return res.json([]);
  }
  try {
    const contacts = Object.values(session.sock.store.contacts).map(c => ({
      id: c.id, name: c.name || c.notify || '',
    }));
    res.json(contacts.slice(0, 200));
  } catch {
    res.json([]);
  }
});

app.post('/logout', async (req, res) => {
  const session = await ensureSession(req, res);
  if (!session) return;
  try {
    if (session.sock) await session.sock.logout();
    session.status = 'logged_out';
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(`SALAR WhatsApp Bridge running on port ${PORT} (localhost only)`);
  console.log(`Backend URL: ${BACKEND_URL}`);
  console.log(`Auth base dir: ${AUTH_DIR}`);
});
