from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    can_manage_users,
    create_access_token,
    get_current_user,
    hash_password,
    require_account_manager,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    CreateManagedUserRequest,
    LoginRequest,
    ProfileUpdateRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.can_manage_users = can_manage_users(user)
    return out


@router.get("/config")
def auth_config():
    return {"allow_registration": settings.allow_registration}


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="注册已关闭，请联系管理员开通账号")
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname or body.username,
        is_admin=db.query(User).count() == 0,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _user_out(user)


@router.get("/users")
def list_managed_users(
    _: User = Depends(require_account_manager),
    db: Session = Depends(get_db),
):
    users = db.query(User).order_by(User.created_at).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nickname": u.nickname,
            "created_at": u.created_at,
        }
        for u in users
    ]


@router.post("/users", response_model=UserOut)
def create_managed_user(
    body: CreateManagedUserRequest,
    _: User = Depends(require_account_manager),
    db: Session = Depends(get_db),
):
    username = body.username.strip()
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=username,
        password_hash=hash_password(body.password),
        nickname=(body.nickname or username).strip()[:64],
        is_admin=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_out(user)


@router.put("/profile", response_model=UserOut)
def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.nickname is not None:
        user.nickname = body.nickname.strip()[:64]
    db.commit()
    db.refresh(user)
    return _user_out(user)
