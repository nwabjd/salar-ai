import asyncio, json, base64, websockets, struct, math, logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def test():
    log.info("Connecting to backend ws://127.0.0.1:8000/ws/live")
    async with websockets.connect("ws://127.0.0.1:8000/ws/live", ping_interval=30) as ws:
        log.info("Connected. Sending setup...")
        await ws.send(json.dumps({"type": "setup", "voice": "Kore"}))

        async def read_msgs(timeout=10):
            msgs = []
            try:
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                    data = json.loads(msg)
                    t = data.get("type", "unknown")
                    log.info("  <- %s: %s", t, str(data)[:200])
                    msgs.append(data)
                    if t in ("ready", "error"):
                        break
            except asyncio.TimeoutError:
                log.info("  (timeout after %ds)", timeout)
            return msgs

        msgs = await read_msgs(15)
        if not any(m.get("type") == "ready" for m in msgs):
            log.error("FAIL: Did not receive ready")
            return

        log.info("Setup complete. Sending 2s silence...")
        silence = b"\x00" * 64000
        b64 = base64.b64encode(silence).decode()
        await ws.send(json.dumps({"type": "audio", "data": b64}))
        log.info("Sent silence. Waiting 8s...")
        msgs = await read_msgs(8)

        log.info("Sending 2s 440Hz tone...")
        samples = 32000
        tone = b""
        for i in range(samples):
            val = int(16000 * math.sin(2 * math.pi * 440 * i / 16000))
            tone += struct.pack("<h", val)
        b64 = base64.b64encode(tone).decode()
        chunk_size = 8000
        for i in range(0, len(b64), chunk_size):
            await ws.send(json.dumps({"type": "audio", "data": b64[i:i+chunk_size]}))
        log.info("Sent tone. Waiting 15s for Gemini response...")
        msgs = await read_msgs(15)
        log.info("Done. Total messages received: %d", len(msgs))

asyncio.run(test())
