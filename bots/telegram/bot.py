"""
Telegram bot for DriveBook (aiogram 3).

Env:
  TELEGRAM_BOT_TOKEN  — required for live mode
  DRIVEBOOK_API_URL   — default http://127.0.0.1:8100
  DRIVEBOOK_DRY_RUN=1 — print actions without Telegram network

Flow: /start → list instructors → pick → list slots → confirm booking.
"""
from __future__ import annotations

import asyncio
import os
import sys

import httpx

API = os.environ.get("DRIVEBOOK_API_URL", "http://127.0.0.1:8100").rstrip("/")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
DRY = os.environ.get("DRIVEBOOK_DRY_RUN", "0") == "1" or not TOKEN


async def api_get(path: str):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(API + path)
        r.raise_for_status()
        return r.json()


async def api_post(path: str, body: dict, idem: str | None = None):
    headers = {"Content-Type": "application/json"}
    if idem:
        headers["Idempotency-Key"] = idem
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(API + path, json=body, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code}: {r.text}")
        return r.json()


async def dry_run_demo() -> None:
    """Prove adapter without Telegram token."""
    print(f"[dry-run] API={API}")
    health = await api_get("/health")
    print("[dry-run] health", health)
    inst = await api_get("/v1/instructors?limit=3")
    print(f"[dry-run] instructors total={inst['total']} sample={inst['items'][0]['name']}")
    slots = await api_get(f"/v1/slots?instructor_id={inst['items'][0]['id']}&limit=3")
    print(f"[dry-run] open slots for instructor: {len(slots['items'])}")
    if slots["items"]:
        slot = slots["items"][0]
        booking = await api_post(
            "/v1/bookings",
            {
                "slot_id": slot["id"],
                "student_name": "Telegram DryRun",
                "student_phone": "+37360009999",
                "source": "telegram",
                "lang": "ro",
            },
            idem=f"tg-dry-{slot['id']}",
        )
        print("[dry-run] booked", booking["booking"]["id"], booking["booking"]["status"])
    print("[dry-run] OK — set TELEGRAM_BOT_TOKEN for live polling")


async def live_bot() -> None:
    from aiogram import Bot, Dispatcher, F
    from aiogram.filters import CommandStart
    from aiogram.types import CallbackQuery, Message
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    bot = Bot(TOKEN)
    dp = Dispatcher()
    # simple in-memory session
    sessions: dict[int, dict] = {}

    @dp.message(CommandStart())
    async def start(m: Message):
        sessions[m.from_user.id] = {}
        data = await api_get("/v1/instructors?limit=10")
        kb = InlineKeyboardBuilder()
        for i in data["items"][:10]:
            kb.button(text=f"{i['name']} ({i['district']})", callback_data=f"i:{i['id']}")
        kb.adjust(1)
        await m.answer(
            f"DriveBook · Chișinău\nAlege instructorul ({data['total']} total):",
            reply_markup=kb.as_markup(),
        )

    @dp.callback_query(F.data.startswith("i:"))
    async def pick_inst(c: CallbackQuery):
        iid = int(c.data.split(":")[1])
        sessions[c.from_user.id] = {"instructor_id": iid}
        slots = await api_get(f"/v1/slots?instructor_id={iid}&limit=12")
        if not slots["items"]:
            await c.message.answer("Nu sunt sloturi libere.")
            await c.answer()
            return
        kb = InlineKeyboardBuilder()
        for s in slots["items"]:
            label = s["starts_at"][:16].replace("T", " ")
            kb.button(text=label, callback_data=f"s:{s['id']}")
        kb.adjust(2)
        await c.message.answer("Alege ora:", reply_markup=kb.as_markup())
        await c.answer()

    @dp.callback_query(F.data.startswith("s:"))
    async def pick_slot(c: CallbackQuery):
        sid = int(c.data.split(":")[1])
        sessions.setdefault(c.from_user.id, {})["slot_id"] = sid
        await c.message.answer("Trimite numele și telefonul pe o linie:\n`Ion Popescu +3736xxxxxxx`", parse_mode="Markdown")
        await c.answer()

    @dp.message(F.text)
    async def contact(m: Message):
        sess = sessions.get(m.from_user.id) or {}
        if "slot_id" not in sess:
            await m.answer("Folosește /start")
            return
        parts = m.text.strip().rsplit(" ", 1)
        if len(parts) != 2:
            await m.answer("Format: Nume Telefon")
            return
        name, phone = parts
        try:
            res = await api_post(
                "/v1/bookings",
                {
                    "slot_id": sess["slot_id"],
                    "student_name": name,
                    "student_phone": phone,
                    "source": "telegram",
                    "lang": "ro",
                },
                idem=f"tg-{m.from_user.id}-{sess['slot_id']}",
            )
            b = res["booking"]
            await m.answer(f"✅ Programat #{b['id']}\n{b['instructor_name']}\n{b['starts_at']}")
            sessions.pop(m.from_user.id, None)
        except Exception as e:
            await m.answer(f"Eroare: {e}")

    print("Telegram bot polling…")
    await dp.start_polling(bot)


def main() -> None:
    if DRY:
        asyncio.run(dry_run_demo())
    else:
        asyncio.run(live_bot())


if __name__ == "__main__":
    main()
