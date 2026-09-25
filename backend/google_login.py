"""Google Identity Services: verify ID tokens and link by immutable subject."""
import os
import re
import secrets
import time
from datetime import timedelta
from fastapi import APIRouter, Depends, Request, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.auth.exceptions import GoogleAuthError
from google.oauth2 import id_token
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from backend.db import GoogleIdentity, User, Session, now
from backend.main import Input, SECURE, db_session, digest, fail, passwords, user_of

router = APIRouter()


def google_client_id():
    return os.environ.get('GOOGLE_CLIENT_ID', '').strip()


@router.get('/api/auth/options')
def options():
    return {'google_client_id': google_client_id() or None}


@router.get('/api/google/nonce')
def nonce(response: Response):
    if not google_client_id():
        fail(503, 'Google sign-in is not configured yet.')
    value = secrets.token_urlsafe(32)
    response.set_cookie('lemon_google_nonce', value, httponly=True, secure=SECURE, samesite='strict', max_age=600, path='/api/google')
    return {'nonce': value}


class GoogleLogin(Input):
    credential: str = Field(min_length=20, max_length=12000)
    nonce: str = Field(min_length=20, max_length=200)


def verify_google(credential, audience):
    return id_token.verify_oauth2_token(credential, GoogleRequest(), audience)


@router.post('/api/google/sign-in')
def sign_in(data: GoogleLogin, request: Request, response: Response, db=Depends(db_session)):
    audience = google_client_id()
    if not audience:
        fail(503, 'Google sign-in is not configured yet.')
    if request.headers.get('origin') != os.environ.get('APP_ORIGIN', 'http://127.0.0.1:5178').rstrip('/'):
        fail(403, 'Sign in from the LemonCAD website.')
    cookie = request.cookies.get('lemon_google_nonce', '')
    if not cookie or not secrets.compare_digest(cookie, data.nonce):
        fail(401, 'Google sign-in expired. Close this dialog and try again.')
    try:
        claims = verify_google(data.credential, audience)
    except (ValueError, GoogleAuthError):
        fail(401, 'Google could not verify this sign-in. Please try again.')
    issued = claims.get('iat')
    if claims.get('iss') not in ('accounts.google.com', 'https://accounts.google.com') or claims.get('aud') != audience or claims.get('nonce') != cookie or not isinstance(issued, (int, float)) or not -60 <= time.time()-issued <= 600:
        fail(401, 'Google sign-in expired or is not intended for this application.')
    subject, email = claims.get('sub', ''), claims.get('email')
    email = email.strip().lower() if isinstance(email, str) else ''
    if not isinstance(subject, str) or not subject or len(subject)>255 or claims.get('email_verified') is not True or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email)>254:
        fail(401, 'Google must provide a verified email address.')
    current = user_of(request, db)
    identity = db.scalar(select(GoogleIdentity).where(GoogleIdentity.subject == subject))
    if identity:
        user = db.get(User, identity.user_id)
        if current and current.id != user.id:
            fail(409, 'This Google account belongs to another LemonCAD account. Sign out first.')
    else:
        user = db.scalar(select(User).where(User.email == email))
        if user and (not current or current.id != user.id):
            fail(409, 'This email already has an account. Sign in with your password, then choose Connect Google.')
        if current and (not user or user.id != current.id):
            fail(409, 'Choose the Google account with the same email as your signed-in account.')
        if current and db.scalar(select(GoogleIdentity).where(GoogleIdentity.user_id == current.id)):
            fail(409, 'Your account already has a different Google identity connected.')
        if not user:
            user = User(email=email, password_hash=passwords.hash(secrets.token_urlsafe(48)))
            db.add(user)
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                fail(409, 'The account changed during sign-in. Please try again.')
        db.add(GoogleIdentity(user_id=user.id, subject=subject))
    token = secrets.token_urlsafe(32)
    db.add(Session(token=digest(token), user_id=user.id, expires_at=now()+timedelta(days=30)))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        fail(409, 'The account changed during sign-in. Please try again.')
    response.delete_cookie('lemon_google_nonce', path='/api/google', secure=SECURE, httponly=True, samesite='strict')
    response.set_cookie('lemon_session', token, httponly=True, secure=SECURE, samesite='lax', max_age=2592000)
    return {'id': user.id, 'email': user.email}
