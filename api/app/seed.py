"""Seed 100 Chișinău instructors + open slots (14 days)."""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta, time, timezone
from zoneinfo import ZoneInfo

import asyncpg

from app.config import settings

TZ = ZoneInfo("Europe/Chisinau")
RNG = random.Random(42)

FIRST_RO = [
    "Andrei", "Ion", "Mihai", "Alexandru", "Vasile", "Gheorghe", "Nicolae",
    "Dumitru", "Sergiu", "Vlad", "Cristian", "Radu", "Daniel", "Adrian",
    "Elena", "Maria", "Ana", "Irina", "Natalia", "Oxana", "Tatiana", "Alina",
    "Victoria", "Diana", "Cristina", "Larisa", "Svetlana",
]
LAST_RO = [
    "Popescu", "Russo", "Ciobanu", "Munteanu", "Grosu", "Rotaru", "Lungu",
    "Ceban", "Spînu", "Moraru", "Balan", "Ungureanu", "Plămădeală", "Cojocaru",
    "Sîrbu", "Gheorghiu", "Cazacu", "Marin", "Toma", "Istrati",
]
SECTORS = [
    "Centru", "Buiucani", "Rîșcani", "Botanica", "Ciocana", "Telecentru",
    "Sculeni", "Malina Mică", "Poșta Veche",
]
CARS = [
    "Dacia Logan", "Volkswagen Polo", "Hyundai i20", "Toyota Yaris",
    "Skoda Fabia", "Renault Clio", "Kia Rio", "Seat Ibiza",
]
TX = ["manual", "automatic", "both"]
# 90-min lessons + 15-min grace → starts every 2 hours
HOURS = [8, 10, 12, 14, 16, 18]


async def seed(force: bool = False) -> dict:
    conn = await asyncpg.connect(settings.database_url)
    try:
        n = await conn.fetchval("SELECT COUNT(*) FROM instructors")
        if n and n >= 100 and not force:
            slots = await conn.fetchval("SELECT COUNT(*) FROM slots")
            return {"instructors": n, "slots": slots, "seeded": False}

        async with conn.transaction():
            if force:
                await conn.execute("DELETE FROM idempotency_records")
                await conn.execute("DELETE FROM bookings")
                await conn.execute("DELETE FROM slots")
                await conn.execute("DELETE FROM instructors")

            for i in range(1, 101):
                name = f"{RNG.choice(FIRST_RO)} {RNG.choice(LAST_RO)}"
                await conn.execute(
                    """
                    INSERT INTO instructors
                    (id, name, district, car, transmission, experience_years, rating, languages, bio, active)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,TRUE)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    i,
                    name,
                    RNG.choice(SECTORS),
                    RNG.choice(CARS),
                    RNG.choice(TX),
                    RNG.randint(2, 25),
                    round(RNG.uniform(4.4, 5.0), 2),
                    "ro,ru" if RNG.random() > 0.3 else "ro,ru,en",
                    "Instructor autorizat, Chișinău. Abordare calmă și individuală.",
                )
            # reset sequence
            await conn.execute(
                "SELECT setval(pg_get_serial_sequence('instructors','id'), (SELECT MAX(id) FROM instructors))"
            )

            today = datetime.now(TZ).date()
            rows = []
            for inst_id in range(1, 101):
                for day_off in range(14):
                    day = today + timedelta(days=day_off)
                    if day.weekday() == 6:
                        k = RNG.randint(2, 4)
                    elif day.weekday() == 5:
                        k = RNG.randint(3, 6)
                    else:
                        k = RNG.randint(5, 8)
                    for h in sorted(RNG.sample(HOURS, k=min(k, len(HOURS)))):
                        start = datetime.combine(day, time(h, 0), tzinfo=TZ)
                        if start <= datetime.now(TZ):
                            continue
                        end = start + timedelta(minutes=90)
                        rows.append((inst_id, start, end, "open"))

            await conn.copy_records_to_table(
                "slots",
                records=rows,
                columns=["instructor_id", "starts_at", "ends_at", "status"],
            )

        instructors = await conn.fetchval("SELECT COUNT(*) FROM instructors")
        slots = await conn.fetchval("SELECT COUNT(*) FROM slots")
        return {"instructors": instructors, "slots": slots, "seeded": True}
    finally:
        await conn.close()


def main() -> None:
    import sys
    force = "--force" in sys.argv
    print(asyncio.run(seed(force=force)))


if __name__ == "__main__":
    main()
