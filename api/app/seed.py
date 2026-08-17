"""Seed 100 Chișinău instructors + users + open slots (14 days).

Slots: sequential 90 min starting 07:00, last ends ≤ 21:00.
  07:00–08:30, 08:30–10:00, 10:00–11:30, 11:30–13:00,
  13:00–14:30, 14:30–16:00, 16:00–17:30, 17:30–19:00,
  19:00–20:30, 20:30–21:00 (last 30 min is partial).

Users: admin, supervisor, 100 instructors.
"""
import asyncio, datetime, os, random, sys
from pathlib import Path
from typing import Optional

import asyncpg
from dotenv import load_dotenv

from app.config import asyncpg_kwargs
from app.services import hash_password

load_dotenv()  # picks up .env for DRIVEBOOK_SUPERVISOR_USERNAME/PASSWORD; no-op if absent

ROOT = Path(__file__).resolve().parent
MIGRATIONS = ROOT / "migrations"
TZ = datetime.timezone(datetime.timedelta(hours=2))  # Europe/Chisinau EET

INSTRUCTOR_NAMES_RO = [
    "Ion Popescu", "Maria Ionescu", "Andrei Moraru", "Elena Ceban",
    "Victor Stoica", "Ana Radu", "Dmitri Corneanu", "Svetlana Cernat",
    "Sergiu Grosu", "Tatiana Ursu", "Alexandru Zaharia", "Olga Natar",
    "Dorian Busuioc", "Irina Barbat", "Gheorghe Munteanu", "Natalia Lupu",
    "Valeriu Cebotari", "Cristina Rusu", "Mihai Gavat", "Alina Fros",
    "Boris Cernătescu", "Daniela Morari", "Eduard Furtună", "Gabriela Pîrlog",
    "Ionel Sîrbu", "Luminița Tudor", "Marian Cărare", "Oxana Dumitru",
    "Petru Rusu", "Rodica Stan", "Ștefan Bostan", "Tania Leuşenco",
    "Ulruţa Băicuş", "Valentina Pascari", "Wiktor Dragnea", "Xenia Cojocaru",
    "Yaroslav Popov", "Zinaida Gherman", "Adrian Bădic", "Carmen Gînsari",
    "Doina Hanganu", "Florin Lupaşcu", "Gheorghe Rusnac", "Iuliana Ţurcanu",
    "Jurii Bîrsan", "Larisa Moroz", "Mihail Şaryp", "Nina Şaptefat",
    "Oleg Cernavşci", "Petruța Dabija", "Radu Fărcășan", "Svetlana Juc",
    "Tudor Munteanu", "Una Brega", "Vasile Ciobanu", "Wanda Dragu",
    "Xavier Lungan", "Yveta Prodan", "Zoran Lupascu", "Aurora Gherman",
    "Boris Cebotari", "Cristina Furtună", "Dan Băicuş", "Elena Morar",
    "Florin Juc", "Gabi Pascari", "Horia Sârbu", "Irina Cernătescu",
    "Julian Bostan", "Kira Ţurcan", "Liviu Rusnac", "Maria Dragu",
    "Nicolae Lungan", "Oksana Prodan", "Paul Lupascu", "Raluca Gherman",
    "Sergiu Cebotari", "Tamara Furtună", "Uspenu Băicuş", "Valentina Morar",
    "Werner Juc", "Xenia Pascari", "Yuri Sârbu", "Zinaida Cernătescu",
    "Andrei Bostan", "Carmen Ţurcan", "Dorian Rusnac", "Elena Dragu",
    "Florin Lungan", "Gabi Prodan", "Horia Lupascu", "Irina Gherman",
    "Julian Cebotari", "Kira Furtună", "Liviu Băicuş", "Maria Morar",
    "Nicolae Juc", "Oksana Pascari", "Paul Sârbu", "Raluca Cernătescu",
]

# ---------- helpers ----------


def _now():
    return datetime.datetime.now(datetime.timezone.utc)


async def _run(mig_path: Path, conn: asyncpg.Connection):
    sql = mig_path.read_text(encoding="utf-8")
    await conn.executescript(sql)
    print(f"  ✓ {mig_path.name}")


# ---------- seed ----------

async def seed(force: bool = False, db_url: Optional[str] = None):
    # db_url=None -> settings.database_url, which honours the DATABASE_URL env
    # var (Neon/Render) with a local fallback. sslmode is handled centrally.
    pool = await asyncpg.create_pool(**asyncpg_kwargs(db_url))
    async with pool.acquire() as conn:
        # run all migrations
        print("Running migrations…")
        migs = sorted(MIGRATIONS.glob("*.sql"))
        for m in migs:
            await _run(m, conn)

        count = await conn.fetchval("SELECT count(*) FROM schools")
        if count and not force:
            print("Database already seeded. Re-run with --force to overwrite.")
            return
        if count and force:
            print("Force mode: truncating existing data…")
            await conn.execute("TRUNCATE bookings, slots, instructors, schools CASCADE")

        print("Seeding schools…")
        await conn.execute(
            """
            INSERT INTO schools (slug, name, default_lang, deposit_required, grace_minutes, slot_minutes)
            VALUES ('chisinau', 'АвтоСтарт — DriveBook', 'ro', FALSE, 15, 90)
            ON CONFLICT (slug) DO NOTHING
            """,
        )

        # ---------- users ----------
        print("Seeding users…")

        # admin/admin is a deliberate weak bootstrap password — the login
        # flow forces a change on first use, so it's fine to hardcode.
        users = [
            ("admin", "admin", "admin", True),
        ]

        # Supervisor is a real account, not a demo one — no hardcoded
        # fallback. Set DRIVEBOOK_SUPERVISOR_USERNAME/PASSWORD (see
        # .env.example) or this account is skipped entirely.
        sup_user = os.environ.get("DRIVEBOOK_SUPERVISOR_USERNAME")
        sup_pw = os.environ.get("DRIVEBOOK_SUPERVISOR_PASSWORD")
        if sup_user and sup_pw:
            # Rename any previously-seeded supervisor account to the
            # currently configured username (handles the username changing
            # between sessions without leaving an orphaned duplicate row).
            await conn.execute(
                "UPDATE users SET username = $1 WHERE role = 'supervisor' AND username <> $1",
                sup_user,
            )
            users.append((sup_user, sup_pw, "supervisor", False))
        else:
            print("  DRIVEBOOK_SUPERVISOR_USERNAME/PASSWORD not set — skipping supervisor account (see .env.example)")

        for username, pw, role, must_change in users:
            await conn.execute(
                """
                INSERT INTO users (username, password_hash, role, must_change_password, created_at)
                VALUES ($1, $2, $3, $4, now())
                ON CONFLICT (username) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    role = EXCLUDED.role,
                    must_change_password = EXCLUDED.must_change_password
                """,
                username, hash_password(pw), role, must_change,
            )

        # ---------- 100 instructors ----------
        print("Seeding 100 instructors…")
        districts = [
            "Centru", "Buiucani", "Rîşcani", "Chişinău Noi",
            " Botanica", "Cricova", "Durlești", "Sîngera",
            "Ivanovca", "Carpинка",
        ]
        cars = [
            "Dacia Logan MT", "Dacia Logan AT", "Renault Sandero MT",
            "Renault Sandero AT", "Skoda Fabia MT", "Skoda Fabia AT",
            "VW Golf MT", "VW Golf AT",
        ]
        trans = ["manual", "automatic", "both"]
        base_time = _now().replace(hour=0, minute=0, second=0, microsecond=0)

        for i in range(1, 101):
            name = INSTRUCTOR_NAMES_RO[i - 1] if i - 1 < len(INSTRUCTOR_NAMES_RO) else f"Инструктор #{i}"
            district = random.choice(districts)
            car = random.choice(cars)
            transmission = random.choice(trans)
            rating = round(random.uniform(3.5, 5.0), 1)
            exp = random.randint(1, 15)
            await conn.execute(
                """
                INSERT INTO instructors (id, name, active, district, car,
                                         transmission, rating, languages, bio, experience_years, created_at)
                VALUES ($1, $2, TRUE, $3, $4, $5, $6, 'ro,ru', '', $7, $8)
                ON CONFLICT (id) DO NOTHING
                """,
                i, name, district, car, transmission, rating, exp, base_time,
            )
            # create instructor user
            await conn.execute(
                """
                INSERT INTO users (username, password_hash, role, instructor_id, created_at)
                VALUES ($1, $2, 'instructor', $3, $4)
                ON CONFLICT (username) DO NOTHING
                """,
                f"instructor_{i:03d}", hash_password("instructor"),
                i, base_time,
            )

        # ---------- slots: 07:00 → 21:00, sequential ----------
        print("Seeding slots (07:00–21:00)…")
        # 10 slots per day per instructor:
        # 07:00-08:30, 08:30-10:00, 10:00-11:30, 11:30-13:00,
        # 13:00-14:30, 14:30-16:00, 16:00-17:30, 17:30-19:00,
        # 19:00-20:30, 20:30-21:00
        start_times = [
            (7, 0), (8, 30), (10, 0), (11, 30),
            (13, 0), (14, 30), (16, 0), (17, 30),
            (19, 0), (20, 30),
        ]
        end_times = [
            (8, 30), (10, 0), (11, 30), (13, 0),
            (14, 30), (16, 0), (17, 30), (19, 0),
            (20, 30), (21, 0),
        ]

        num_days = 14
        day_idx = 0
        for day_idx in range(num_days):
            day = base_time + datetime.timedelta(days=day_idx)
            # skip weekends (Sat=5, Sun=6)
            if day.weekday() >= 5:
                continue
            for inst_id in range(1, 101):
                for (sh, sm), (eh, em) in zip(start_times, end_times):
                    starts = day.replace(hour=sh, minute=sm, tzinfo=TZ)
                    ends = day.replace(hour=eh, minute=em, tzinfo=TZ)
                    if ends > base_time.replace(hour=21, minute=0, tzinfo=TZ) and day_idx > 0:
                        # last slot on day wraps: cap at 21:00
                        pass  # we already cap at 21:00 in seed
                    await conn.execute(
                        """
                        INSERT INTO slots (instructor_id, starts_at, ends_at, status,
                                           is_hidden, created_at)
                        VALUES ($1, $2, $3, 'open', FALSE, now())
                        ON CONFLICT DO NOTHING
                        """,
                        inst_id, starts, ends,
                    )

        print(f"Seeding complete. (days={num_days}, instructors=100)")

    await pool.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--db-url", default=None)
    args = parser.parse_args()
    asyncio.run(seed(force=args.force, db_url=args.db_url))
