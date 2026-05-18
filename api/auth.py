import os
import smtplib
import random
import string
import asyncio
import jwt
import bcrypt
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.connection import get_db
from database.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])

SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-please-change")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

EMAIL_ADDRESS = "ahmed.tbsje@gmail.com"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_otp():
    return "".join(random.choices(string.digits, k=6))

def send_verification_email(to_email: str, code: str):
    if not EMAIL_PASSWORD:
        print(f"WARNING: EMAIL_PASSWORD not set. Would have sent {code} to {to_email}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Your Verification Code"
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email

    html = f"""
    <html>
      <head></head>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f5; padding: 40px; text-align: center;">
        <div style="max-width: 500px; margin: 0 auto; background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
          <h2 style="color: #1f2937; font-size: 24px; margin-bottom: 24px;">Verify your email</h2>
          <p style="color: #4b5563; font-size: 16px; margin-bottom: 32px;">Please use the following 6-digit code to complete your registration:</p>
          <div style="background-color: #f3f4f6; border-radius: 8px; padding: 20px; margin-bottom: 32px;">
            <strong style="font-size: 32px; letter-spacing: 4px; color: #111827;">{code}</strong>
          </div>
          <p style="color: #9ca3af; font-size: 14px;">This code will expire in 10 minutes.</p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, "html"))

    # Always print OTP to console as a debug fallback
    print(f"[Auth] OTP for {to_email}: {code}")

    if not EMAIL_PASSWORD:
        print("[Auth] EMAIL_PASSWORD not set — skipping SMTP, use the OTP above.")
        return

    # Try port 465 (SSL) first — often not blocked when 587 is
    try:
        import ssl
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        print(f"[Auth] Email sent via port 465 to {to_email}")
        return
    except Exception as e:
        print(f"[Auth] Port 465 failed: {e} — trying port 587...")

    # Fallback: port 587 STARTTLS
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        server.quit()
        print(f"[Auth] Email sent via port 587 to {to_email}")
    except Exception as e:
        print(f"[Auth] Both ports failed for {to_email}: {e}")
        print(f"[Auth] *** USE THIS OTP MANUALLY: {code} ***")

class SignupRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str

class VerifyRequest(BaseModel):
    email: EmailStr
    code: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/signup")
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == req.email)
    result = await db.execute(query)
    existing_user = result.scalars().first()

    if existing_user:
        if existing_user.is_verified:
            raise HTTPException(status_code=400, detail="Email already registered")
        user = existing_user
    else:
        user = User(
            full_name=req.full_name,
            email=req.email,
        )
        db.add(user)

    user.hashed_password = get_password_hash(req.password)
    user.verification_code = generate_otp()
    user.code_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    user.is_verified = False

    await db.commit()
    await db.refresh(user)

    # Fire email in background thread — never blocks the event loop
    loop = asyncio.get_event_loop()
    otp_to_send = user.verification_code
    email_to = user.email
    loop.run_in_executor(None, send_verification_email, email_to, otp_to_send)

    return {"message": "Verification code sent successfully."}

@router.post("/verify-otp")
async def verify_otp(req: VerifyRequest, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == req.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_verified:
        return {"message": "User already verified"}
    if user.verification_code != req.code:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    if not user.code_expires_at or user.code_expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Verification code expired")

    user.is_verified = True
    user.verification_code = None
    user.code_expires_at = None
    await db.commit()

    return {"message": "Email verified successfully."}

@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.email == req.email)
    result = await db.execute(query)
    user = result.scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Email not verified")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "full_name": user.full_name}
