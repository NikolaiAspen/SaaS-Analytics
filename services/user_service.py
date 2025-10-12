"""
User management service
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User, AppVersion, EmailLog
from datetime import datetime


class UserService:
    """Service for managing users"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = "user",
        is_active: bool = True,
        receive_notifications: bool = True
    ) -> User:
        """Create a new user"""
        # Check if user already exists
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            raise ValueError(f"User with email {email} already exists")

        # Create new user
        user = User(
            email=email,
            full_name=full_name,
            role=role,
            is_active=is_active,
            receive_notifications=receive_notifications
        )
        user.set_password(password)

        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_all_users(self) -> List[User]:
        """Get all users"""
        result = await self.session.execute(select(User))
        return result.scalars().all()

    async def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        receive_notifications: Optional[bool] = None,
        password: Optional[str] = None
    ) -> Optional[User]:
        """Update user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        if email is not None:
            # Check if email is already taken by another user
            existing = await self.get_user_by_email(email)
            if existing and existing.id != user_id:
                raise ValueError(f"Email {email} is already taken")
            user.email = email

        if full_name is not None:
            user.full_name = full_name
        if role is not None:
            user.role = role
        if is_active is not None:
            user.is_active = is_active
        if receive_notifications is not None:
            user.receive_notifications = receive_notifications
        if password is not None:
            user.set_password(password)

        user.updated_at = datetime.utcnow()

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, user_id: int) -> bool:
        """Delete user"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False

        await self.session.delete(user)
        await self.session.commit()
        return True

    async def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """Authenticate user by email and password"""
        user = await self.get_user_by_email(email)
        if not user:
            return None

        if not user.is_active:
            return None

        if not user.verify_password(password):
            return None

        # Update last login
        user.last_login = datetime.utcnow()
        await self.session.commit()

        return user

    async def create_version_release(
        self,
        version: str,
        release_notes: str,
        created_by: str
    ) -> AppVersion:
        """Create a new version release"""
        # Check if version already exists
        result = await self.session.execute(
            select(AppVersion).where(AppVersion.version == version)
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise ValueError(f"Version {version} already exists")

        version_release = AppVersion(
            version=version,
            release_notes=release_notes,
            created_by=created_by,
            notifications_sent=False
        )

        self.session.add(version_release)
        await self.session.commit()
        await self.session.refresh(version_release)
        return version_release

    async def get_latest_version(self) -> Optional[AppVersion]:
        """Get the latest version"""
        result = await self.session.execute(
            select(AppVersion).order_by(AppVersion.released_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def log_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        email_type: str,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> EmailLog:
        """Log sent email"""
        log = EmailLog(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            email_type=email_type,
            success=success,
            error_message=error_message
        )

        self.session.add(log)
        await self.session.commit()
        await self.session.refresh(log)
        return log
