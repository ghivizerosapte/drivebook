"""
WhatsApp Cloud API adapter (webhook) for DriveBook.

Env:
  DRIVEBOOK_API_URL
  WA_VERIFY_TOKEN — webhook verification
  WA_ACCESS_TOKEN — Graph API token (optional dry-run)
  WA_PHONE_NUMBER_ID

Endpoints (mounted under this mini-app or reverse-proxied):
  GET  /whatsapp/webhook  — Meta verification
  POST /whatsapp/webhook  — inbound messages

Without tokens: `python -m bots.whatsapp.app --dry-run` exercises API path.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

API = os.environ.get("DRIVEBOOK_API_URL", "http://127.0.0.1:8100").rstrip("/")
VERIFY = os.environ.get("WA_VERIFY_TOKEN", "drivebook-verify")
ACCESS = os.environ.get("WA_ACCESS_TOKEN", "")
PHONE_ID = os.environ.get("WA_PHONE_NUMBER_ID", "")

app = FastAPI(title="DriveBook WhatsApp adapter")
# naive session: phone -> {step, slot_id}
SESS: dict[str, dict] = {}


async def api_get(path: str):
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get(API + path)
        r.raise_for_status()
        return r.json()


async def api_post(path: str, body: dict, idem: str | None = None):
    headers = {"Content-Type": "application/json"}
    if idem:
        headers["Idempotency-Key"] = idem
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(API + path, json=body, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text}")
        return r.json()


async def wa_send(to: str, text: str) -> None:
    if not ACCESS or not PHONE_ID:
        print(f"[wa-dry] -> {to}: {text}")
        return
    url = f"https://graph.facebook.com/v19.0/{PHONE_ID}/messages"
    async with httpx.AsyncClient(timeout=20) as c:
        await c.post(
            url,
            headers={"Authorization": f"Bearer {ACCESS}"},
            json={
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": text},
            },
        )


@app.get("/whatsapp/webhook")
async def verify(
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(403, "verification failed")


@app.post("/whatsapp/webhook")
async def inbound(request: Request):
    body = await request.json()
    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages") or []
        if not messages:
            return {"ok": True}
        msg = messages[0]
        from_phone = msg["from"]
        text = (msg.get("text") or {}).get("body", "").strip()
    except Exception:
        return {"ok": True}

    await handle_text(from_phone, text)
    return {"ok": True}


async def handle_text(phone: str, text: str) -> None:
    low = text.lower().strip()
    sess = SESS.setdefault(phone, {"step": "start"})

    if low in ("hi", "hello", "start", "salut", "bună", "buna"):
        inst = await api_get("/v1/instructors?limit=5")
        lines = [f"{i['id']}. {i['name']} — {i['district']}" for i in inst["items"]]
        sess["step"] = "pick_instructor"
        await wa_send(phone, "DriveBook Chișinău\nAlege instructor (trimite ID):\n" + "\n".join(lines))
        return

    if sess.get("step") == "pick_instructor" and text.isdigit():
        iid = int(text)
        slots = await api_get(f"/v1/slots?instructor_id={iid}&limit=8")
        if not slots["items"]:
            await wa_send(phone, "Nu sunt sloturi. Scrie start.")
            return
        sess["step"] = "pick_slot"
        sess["slots"] = {str(s["id"]): s for s in slots["items"]}
        lines = [f"{s['id']}: {s['starts_at'][:16]}" for s in slots["items"]]
        await wa_send(phone, "Alege slot ID:\n" + "\n".join(lines))
        return

    if sess.get("step") == "pick_slot" and text.isdigit():
        sid = text
        if sid not in sess.get("slots", {}):
            await wa_send(phone, "Slot invalid.")
            return
        sess["slot_id"] = int(sid)
        sess["step"] = "name"
        await wa_send(phone, "Trimite numele tău:")
        return

    if sess.get("step") == "name":
        sess["name"] = text
        sess["step"] = "phone_confirm"
        await wa_send(phone, "Confirmă telefonul (sau trimite altul):")
        return

    if sess.get("step") == "phone_confirm":
        phone_num = text if text.startswith("+") else f"+{text}"
        if not re.match(r"^\+?[0-9]{8,15}$", phone_num.replace(" ", "")):
            phone_num = f"+{phone}" if not phone.startswith("+") else phone
        try:
            res = await api_post(
                "/v1/bookings",
                {
                    "slot_id": sess["slot_id"],
                    "student_name": sess.get("name", "WhatsApp User"),
                    "student_phone": phone_num,
                    "source": "whatsapp",
                    "lang": "ro",
                },
                idem=f"wa-{phone}-{sess['slot_id']}",
            )
            b = res["booking"]
            await wa_send(phone, f"✅ Programat #{b['id']}\n{b['instructor_name']}\n{b['starts_at']}")
            SESS.pop(phone, None)
        except Exception as e:
            await wa_send(phone, f"Eroare: {e}")
        return

    await wa_send(phone, "Scrie start pentru programare.")


async def dry_run() -> None:
    print(f"[wa dry-run] API={API}")
    await handle_text("37360001111", "start")
    # simulate picking first instructor from last API call
    inst = await api_get("/v1/instructors?limit=1")
    await handle_text("37360001111", str(inst["items"][0]["id"]))
    slots = await api_get(f"/v1/slots?instructor_id={inst['items'][0]['id']}&limit=1")
    if slots["items"]:
        await handle_text("37360001111", str(slots["items"][0]["id"]))
        await handle_text("37360001111", "Maria WhatsApp")
        await handle_text("37360001111", "+37360001111")
    print("[wa dry-run] done")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--serve", action="store_true")
    p.add_argument("--port", type=int, default=8101)
    args = p.parse_args()
    if args.dry_run or not args.serve:
        asyncio.run(dry_run())
        return
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
