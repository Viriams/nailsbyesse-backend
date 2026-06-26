import asyncio
import asyncpg
import os
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()
pwd = CryptContext(schemes=['bcrypt'], deprecated='auto')

async def reset():
    conn = await asyncpg.connect(os.environ['DATABASE_URL'])
    hashed = pwd.hash(os.environ['ADMIN_PASSWORD'])
    await conn.execute('UPDATE admins SET hashed_password=$1', hashed)
    await conn.close()
    print('Mot de passe mis à jour !')

asyncio.run(reset())