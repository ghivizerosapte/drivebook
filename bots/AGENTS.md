# bots/ — Channel adapters over DriveBook API

## Scope
Thin clients: Telegram bot + WhatsApp webhook. No business logic duplication.

## Rules
- Always call HTTP API (`DRIVEBOOK_API_URL`, default http://127.0.0.1:8100)
- Dry-run mode if tokens missing
- source=`telegram` / `whatsapp` on bookings

## Layout
```
bots/
  telegram/bot.py
  whatsapp/app.py
```
