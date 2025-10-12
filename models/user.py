from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Boolean
from passlib.context import CryptContext
from models.subscription import Base

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class User(Base):
    """Model for storing user accounts"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="user")  # "admin" or "user"
    is_active = Column(Boolean, default=True)
    receive_notifications = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        """Hash and set password"""
        self.password_hash = pwd_context.hash(password)

    def verify_password(self, password: str) -> bool:
        """Verify password against hash"""
        return pwd_context.verify(password, self.password_hash)


class AppVersion(Base):
    """Model for tracking application versions and releases"""
    __tablename__ = "app_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String, unique=True, nullable=False, index=True)  # e.g., "1.2.0"
    release_notes = Column(String, nullable=True)  # Norwegian release notes
    released_at = Column(DateTime, default=datetime.utcnow)
    notifications_sent = Column(Boolean, default=False)
    created_by = Column(String, nullable=True)  # Email of admin who created release

    created_at = Column(DateTime, default=datetime.utcnow)


class EmailLog(Base):
    """Model for logging sent emails"""
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    recipient_email = Column(String, nullable=False, index=True)
    subject = Column(String, nullable=False)
    body = Column(String, nullable=True)
    email_type = Column(String, nullable=False)  # "version_release", "password_reset", etc.
    sent_at = Column(DateTime, default=datetime.utcnow)
    success = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
