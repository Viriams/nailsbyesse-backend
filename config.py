from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = "change_this_secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    ADMIN_EMAIL: str = "nailsbyesse365@gmail.com"
    ADMIN_PASSWORD: str = "admin123"

    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "Nails By Esse <noreply@nailsbyesse.com>"

    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    FRONTEND_URL: str = "https://nailsbyesse.vercel.app"

    class Config:
        env_file = ".env"

settings = Settings()
