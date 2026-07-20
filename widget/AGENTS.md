# widget/ — Shadow DOM booking embed + hosted page

## Scope
Standalone booking UI. No React. Embed must not leak host CSS.

## Rules
- Shadow DOM for embed (`embed.js`)
- No city step — Chișinău only
- Bilingual ro/ru
- BSM-like airy palette: orange CTA `#F9812A`, dark `#2E2E36`, white/air
- Talks only to DriveBook API (`/v1/*`)
- Sources via `?source=` / `data-source`

## Files
- `embed.js` — loader
- `widget.js` — logic (used by hosted + shadow root); ro/ru strings live inline in `STR`
- `widget.css` — styles
- `book.html` — hosted full page
