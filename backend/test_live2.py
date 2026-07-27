import asyncio, json, base64, websockets, struct, math, logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

async def test():
    log.info("Connecting...")
    async with websockets.connect("ws://127.0.0.1:8000/ws/live", ping_interval=30) as ws:
        await ws.send(json.dumps({"type": "setup", "voice": "Kore"}))
        
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
            log.info("  <- %s", msg.get("type"))
            if msg.get("type") in ("ready", "error"):
                break

        log.info("Setup done. Streaming 5s of 440Hz tone in 100ms chunks...")
        sample_rate = 16000
        chunk_samples = 1600  # 100ms at 16kHz
        total_chunks = 50  # 5 seconds
        
        for chunk_i in range(total_chunks):
            tone = b""
            for s in range(chunk_samples):
                t = (chunk_i * chunk_samples + s) / sample_rate
                val = int(16000 * math.sin(2 * math.pi * 440 * t))
                tone += struct.pack("<h", val)
            b64 = base64.b64encode(tone).decode()
            await ws.send(json.dumps({"type": "audio", "data": b64}))
            if chunk_i % 10 == 0:
                log.info("  Sent chunk %d/%d", chunk_i + 1, total_chunks)
            await asyncio.sleep(0.1)
        
        log.info("All chunks sent. Waiting 15s for response...")
        try:
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                log.info("  <- %s: %s", msg.get("type"), str(msg)[:200])
        except asyncio.TimeoutError:
            log.info("  (timeout)")

asyncio.run(test())
