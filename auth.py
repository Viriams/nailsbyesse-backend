from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import settings
from database import get_conn, release_conn

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalide ou expiré",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    conn = await get_conn()
    try:
        admin = await conn.fetchrow("SELECT * FROM admins WHERE email=$1", email)
        if admin is None:
            raise credentials_exception
        return admin
    finally:
        await release_conn(conn)

async def init_admin():
    """Crée le compte admin par défaut si il n'existe pas"""
    conn = await get_conn()
    try:
        existing = await conn.fetchrow("SELECT id FROM admins WHERE email=$1", settings.ADMIN_EMAIL)
        if not existing:
            hashed = hash_password(settings.ADMIN_PASSWORD)
            await conn.execute(
                "INSERT INTO admins (email, hashed_password) VALUES ($1, $2)",
                settings.ADMIN_EMAIL, hashed
            )
            print(f"✅ Admin créé : {settings.ADMIN_EMAIL}")
    finally:
        await release_conn(conn)
