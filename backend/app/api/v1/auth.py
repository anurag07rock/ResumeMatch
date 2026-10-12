from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.core.security import (
    PasswordComplexityError,
    create_access_token,
    create_refresh_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Registers a new candidate/user account, validates password complexity, and securely hashes password.",
)
@limiter.limit(lambda: settings.AUTH_RATE_LIMIT)
async def register_user(
    request: Request,
    payload: UserRegisterRequest,
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    Register a new user account.
    - Validates minimum password complexity
    - Hashes password using bcrypt with rounds >= 12
    - Enforces uniqueness of user email
    - Persists user strictly through UserRepository
    """
    try:
        validate_password_strength(payload.password)
    except PasswordComplexityError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    user_repo = UserRepository(session)
    existing_user = await user_repo.get_by_email(payload.email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    hashed_pw = hash_password(payload.password)
    new_user = User(
        email=payload.email.lower().strip(),
        hashed_password=hashed_pw,
        full_name=payload.full_name,
        is_active=True,
        is_superuser=False,
    )
    created_user = await user_repo.create(new_user)
    return created_user


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user and issue JWT tokens",
    description="Verifies user credentials, validates bcrypt password hash, and returns access and refresh JWT tokens.",
)
@limiter.limit(lambda: settings.AUTH_RATE_LIMIT)
async def login_user(
    request: Request,
    payload: UserLoginRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate user credentials and return cryptographically signed tokens.
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_email(payload.email)
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current user profile",
    description="Returns the profile information of the currently authenticated user.",
)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Protected endpoint retrieving authenticated user identity.
    """
    return current_user
