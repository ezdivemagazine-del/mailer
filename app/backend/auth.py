from passlib.hash import pbkdf2_sha256
import jwt
import os
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

SECRET = os.environ.get("SECRET_KEY", "yichian-mailer-default-secret-change-me")
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 12

bearer_scheme = HTTPBearer()


def hash_password(plain: str) -> str:
    return pbkdf2_sha256.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pbkdf2_sha256.verify(plain, hashed)


def create_token(user_id: int, username: str, role: str) -> str:
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="登入已過期，請重新登入")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="無效的登入憑證")


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(bearer_scheme)) -> dict:
    return decode_token(credentials.credentials)


def require_admin(user: dict = Security(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="此功能需要管理員權限")
    return user
