"""
Simple Basic Authentication for SaaS Analytics Dashboard
"""
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from config import settings

security = HTTPBasic()


def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    """
    Verify Basic Auth credentials.
    Returns username if valid, raises HTTPException if invalid.
    """
    # Get credentials from environment variables
    correct_username = settings.auth_username
    correct_password = settings.auth_password

    # If auth is disabled (no credentials set), allow access
    if not correct_username or not correct_password:
        return "guest"

    # Compare credentials using constant-time comparison to prevent timing attacks
    username_correct = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        correct_username.encode("utf-8")
    )
    password_correct = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        correct_password.encode("utf-8")
    )

    if not (username_correct and password_correct):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Feil brukernavn eller passord",
            headers={"WWW-Authenticate": "Basic"},
        )

    return credentials.username
