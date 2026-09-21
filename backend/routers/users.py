from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from datetime import datetime, timedelta, timezone
import secrets
import re
import os
import smtplib
from email.message import EmailMessage
from database import get_db
import models, schemas, auth

router = APIRouter(prefix="/users", tags=["Users"])

DEMO_ACCOUNTS = {
    "aanya@gmail.com": ("citizen", "Aanya Demo"),
    "airauni@gmail.com": ("university", "Aira University Demo"),
    "ravi.expert@gmail.com": ("expert", "Ravi Expert Demo"),
    "officer@education.gov.in": ("govt", "Government Officer Demo"),
    "contact1@example.com": ("industry", "Industry Partner Demo"),
}


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _issue_token(user: models.User) -> str:
    return auth.create_access_token(data={"sub": user.email, "role": user.role})


def _send_otp_email(recipient: str, otp: str) -> bool:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("SMTP_FROM", smtp_user or "")
    if not smtp_host or not smtp_user or not smtp_password or not sender:
        return False

    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_SSL", "false").lower() == "true" or smtp_port == 465
    message = EmailMessage()
    message["Subject"] = "Your CollabX verification code"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        f"Your CollabX verification code is {otp}.\n\n"
        "This code expires in 5 minutes. If you did not request this code, "
        "you can safely ignore this email."
    )

    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=15) as server:
        if not use_ssl:
            server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(message)
    return True


# ---------- REGISTER ----------
@router.post("/register", response_model=schemas.UserOut, status_code=201)
def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if email exists
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Validate role
    valid_roles = ["citizen", "university", "industry", "govt", "expert", "admin"]
    if user.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {valid_roles}")

    new_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=auth.hash_password(user.password),
        role=user.role,
        organization=user.organization,
        primary_sector=user.primary_sector,
        expertise=user.expertise,
        support=user.support,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


# ---------- LOGIN ----------
@router.post("/login", response_model=schemas.Token)
def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    identifier = credentials.email.strip()
    user = db.query(models.User).filter(
        or_(
            func.lower(models.User.email) == identifier.lower(),
            func.lower(models.User.name) == identifier.lower(),
        )
    ).first()
    if not user or not auth.verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email, username, or password")

    token = _issue_token(user)
    return {"access_token": token, "token_type": "bearer"}


@router.post("/demo-login", response_model=schemas.Token)
def demo_login(payload: schemas.DemoLoginRequest, db: Session = Depends(get_db)):
    email = str(payload.email).strip().lower()
    demo = DEMO_ACCOUNTS.get(email)
    if not demo:
        raise HTTPException(status_code=403, detail="Demo account is not available")
    role, name = demo
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        user = models.User(
            name=name,
            email=email,
            password_hash=auth.hash_password(secrets.token_urlsafe(32)),
            role=role,
            organization=name if role in {"university", "industry"} else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    elif user.role != role:
        raise HTTPException(status_code=409, detail="Demo account role is misconfigured")
    return {"access_token": _issue_token(user), "token_type": "bearer"}


# ---------- CITIZEN EMAIL OTP ----------
@router.post("/send-otp")
def send_otp(payload: schemas.OTPSendRequest, db: Session = Depends(get_db)):
    email = _normalize_email(str(payload.email))
    otp = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    existing = db.query(models.OTPStore).filter(models.OTPStore.email == email).first()
    if existing:
        existing.otp = otp
        existing.expires_at = expires_at
    else:
        db.add(models.OTPStore(email=email, otp=otp, expires_at=expires_at))
    db.commit()

    try:
        delivered = _send_otp_email(email, otp)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print(f"[OTP EMAIL ERROR] {email}: {error}")
        raise HTTPException(status_code=503, detail="OTP email delivery is unavailable. Please try again later.")

    if delivered:
        print(f"[OTP SENT] {email} (expires in 5 minutes)")
        return {"success": True, "message": "OTP sent"}

    # Offline/demo fallback when SMTP environment variables are not configured.
    print(f"[OTP DEMO] {email}: {otp} (expires in 5 minutes)")
    return {"success": True, "message": "OTP generated in demo mode", "demo_otp": otp}


@router.post("/verify-otp")
def verify_otp(payload: schemas.OTPVerifyRequest, db: Session = Depends(get_db)):
    email = _normalize_email(str(payload.email))
    otp = payload.otp.strip()
    if not re.fullmatch(r"\d{6}", otp):
        raise HTTPException(status_code=400, detail="OTP must be a 6-digit code")

    stored = db.query(models.OTPStore).filter(models.OTPStore.email == email).first()
    if not stored or stored.otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")

    now = datetime.now(timezone.utc)
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        db.delete(stored)
        db.commit()
        raise HTTPException(status_code=400, detail="OTP has expired. Please request a new code.")

    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        display_name = (payload.name or "").strip() or email.split("@", 1)[0]
        user = models.User(
            name=display_name[:100],
            email=email,
            password_hash=auth.hash_password(secrets.token_urlsafe(32)),
            role="citizen",
            organization=None,
        )
        db.add(user)
        db.flush()

    db.delete(stored)
    db.commit()
    db.refresh(user)
    return {
        "access_token": _issue_token(user),
        "token_type": "bearer",
        "user": schemas.UserOut.model_validate(user).model_dump(mode="json"),
    }


# ---------- GET MY PROFILE ----------
@router.get("/me", response_model=schemas.UserOut)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.patch("/me", response_model=schemas.UserOut)
def update_me(
    payload: schemas.UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    for field in ("name", "phone", "organization", "district"):
        value = getattr(payload, field)
        if value is not None:
            setattr(current_user, field, value.strip() or None)
    db.commit()
    db.refresh(current_user)
    return current_user