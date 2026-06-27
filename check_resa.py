import asyncio
import asyncpg
import os
from dotenv import load_dotenv
load_dotenv()

async def check():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    rows = await conn.fetch("SELECT id, date, heure_debut, statut FROM reservations ORDER BY created_at DESC LIMIT 10")
    for r in rows:
        print(dict(r))
    await conn.close()

asyncio.run(check())