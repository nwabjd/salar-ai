import makeWASocket, { DisconnectReason, useMultiFileAuthState, fetchLatestBaileysVersion, makeCacheableSignalKeyStore } from '@whiskeysockets/baileys';
import express from 'express';
import qrcode from 'qrcode-terminal';
import pino from 'pino';
import { Boom } from '@hapi/boom';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = process.env.WA_BRIDGE_PORT || 3100;
const BACKEND_URL = process.env.SALAR_BACKEND_URL || 'http://127.0.0.1:8000';
// Use persistent storage path if available (Render), otherwise local auth dir
const AUTH_DIR = process.env.WA_AUTH_DIR || path.join(__dirname, 'auth');
// Auto-reply handled by SALAR backend via Gemini — removed hardcoded draft

const logger = pino({ level: 'silent' });

const app = express();
app.use(express.json({ limit: '10mb' }));

let sock = null;
let connectionStatus = 'disconnected';
let qrCode = null;
let lastDisconnectReason = null;
let recentChats = [];
const messageStore = new Map();

async function startWhatsApp() {
  if (!fs.existsSync(AUTH_DIR)) fs.mkdirSync(AUTH_DIR, { recursive: true });

  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    printQRInTerminal: false,
    browser: ['SALAR AI', 'Chrome', '120.0'],
  });

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrCode = qr;
      connectionStatus = 'waiting_scan';
      console.log('\n=== WhatsApp QR Code ===');
      qrcode.generate(qr, { small: true });
      console.log('Scan with WhatsApp on your phone\n');
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      lastDisconnectReason = statusCode;
      connectionStatus = 'disconnected';

      if (statusCode !== DisconnectReason.loggedOut) {
        console.log('Connection closed, reconnecting...');
        setTimeout(() => startWhatsApp(), 3000);
      } else {
        console.log('Logged out — clearing session and re-pairing...');
        connectionStatus = 'logged_out';
        qrCode = null;
        try {
          fs.rmSync(AUTH_DIR, { recursive: true, force: true });
        } catch (e) {
          console.error('Failed to clear auth dir:', e.message);
        }
        setTimeout(() => startWhatsApp(), 1500);
      }
    }

    if (connection === 'open') {
      connectionStatus = 'connected';
      qrCode = null;
      console.log('WhatsApp connected!');
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

      console.log(`[WA] ${isGroup ? 'Group' : 'DM'} from ${senderName}: ${text?.substring(0, 100) || '[media]'}`);

      // Store message
      const chatMsgs = messageStore.get(from) || [];
      chatMsgs.push({ id: msg.key.id, fromMe: false, text: text || '[media]', timestamp: msg.messageTimestamp, senderName });
      if (chatMsgs.length > 50) chatMsgs.splice(0, chatMsgs.length - 50);
      messageStore.set(from, chatMsgs);

      // Forward to SALAR backend — auto-reply handled by backend via Gemini
      forwardToBackend(from, senderName, text, isGroup).catch(() => {});

      // Update chat list
      updateRecentChat(from, senderName, text, false);
    }
  });
}

function extractText(message) {
  if (message.conversation) return message.conversation;
  if (message.extendedTextMessage?.text) return message.extendedTextMessage.text;
  if (message.imageMessage?.caption) return message.imageMessage.caption;
  if (message.videoMessage?.caption) return message.videoMessage.caption;
  return '';
}

async function forwardToBackend(jid, senderName, text, isGroup) {
  if (!text) return;
  try {
    await fetch(`${BACKEND_URL}/api/whatsapp/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from: jid, sender_name: senderName, text, is_group: isGroup, timestamp: Date.now() }),
      signal: AbortSignal.timeout(5000),
    });
  } catch {}
}

function updateRecentChat(jid, name, text, fromMe) {
  const existing = recentChats.find(c => c.jid === jid);
  if (existing) {
    existing.lastMessage = text || '';
    existing.unread = fromMe ? 0 : (existing.unread || 0) + 1;
  } else {
    recentChats.unshift({ jid, name: name || jid.split('@')[0], lastMessage: text || '', unread: fromMe ? 0 : 1 });
  }
  if (recentChats.length > 100) recentChats.length = 100;
}

// === REST API ===

app.get('/status', (req, res) => {
  res.json({
    status: connectionStatus,
    has_qr: !!qrCode,
    phone_number: sock?.user?.id?.split(':')[0] || null,
    name: sock?.user?.name || null,
    last_disconnect: lastDisconnectReason,
  });
});

app.get('/qr', (req, res) => {
  if (!qrCode) return res.json({ qr: null, status: connectionStatus });
  res.json({ qr: qrCode, status: connectionStatus });
});

app.post('/send', async (req, res) => {
  if (connectionStatus !== 'connected') {
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
    const result = await sock.sendMessage(jid, { text });

    // Store outgoing message
    const chatMsgs = messageStore.get(jid) || [];
    chatMsgs.push({ id: result.key.id, fromMe: true, text, timestamp: Date.now(), senderName: 'Me' });
    if (chatMsgs.length > 50) chatMsgs.splice(0, chatMsgs.length - 50);
    messageStore.set(jid, chatMsgs);

    updateRecentChat(jid, '', text, true);
    res.json({ ok: true, id: result.key.id, jid });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/chats', (req, res) => {
  res.json(recentChats);
});

app.get('/messages/:jid', async (req, res) => {
  const { jid } = req.params;
  const limit = parseInt(req.query.limit) || 20;
  const msgs = messageStore.get(jid) || [];
  res.json(msgs.slice(-limit));
});

app.get('/contacts', (req, res) => {
  if (connectionStatus !== 'connected' || !sock?.store?.contacts) {
    return res.json([]);
  }
  try {
    const contacts = Object.values(sock.store.contacts).map(c => ({
      id: c.id, name: c.name || c.notify || '',
    }));
    res.json(contacts.slice(0, 200));
  } catch {
    res.json([]);
  }
});

app.post('/logout', async (req, res) => {
  try {
    if (sock) await sock.logout();
    connectionStatus = 'logged_out';
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(`SALAR WhatsApp Bridge running on port ${PORT} (localhost only)`);
  console.log(`Backend URL: ${BACKEND_URL}`);
  startWhatsApp().catch(e => {
    console.error('WhatsApp start failed:', e);
    connectionStatus = 'error';
  });
});
