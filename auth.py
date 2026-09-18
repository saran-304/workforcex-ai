"""
WORKFORCEX AI
Authentication, Roles and Tenant Security

Prototype authentication system designed for:
- FastAPI
- SQLite
- PostgreSQL
- Streamlit
- Role-based access control
- Organization/tenant isolation

IMPORTANT:
This prototype uses SHA-256 password hashing to keep the
dependency list small. For a production SaaS deployment,
replace this with Argon2 or bcrypt and use a proper JWT/session
implementation.
"""

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User


# ============================================================
# CONFIGURATION
# ============================================================

SESSION_EXPIRE_HOURS = int(
    os.getenv("SESSION_EXPIRE_HOURS", "12")
)


# ============================================================
# IN-MEMORY SESSION STORE
# ============================================================
#
# This is intentionally simple for the hackathon prototype.
#
# Format:
#
# token -> {
#     "user_id": 1,
#     "created_at": datetime,
#     "expires_at": datetime
# }
#
# IMPORTANT:
# Restarting the backend invalidates active sessions.
#
# For production:
# use Redis/database-backed sessions or JWT.
#

SESSIONS = {}


# ============================================================
# PASSWORD HASHING
# ============================================================

def hash_password(password: str) -> str:
    """
    Hash a password using SHA-256 with a random salt.

    The stored format is:

        salt$hash

    Args:
        password: Plain-text password.

    Returns:
        Salted password hash.
    """

    if not password:
        raise ValueError("Password cannot be empty.")

    salt = secrets.token_hex(16)

    digest = hashlib.sha256(
        (salt + password).encode("utf-8")
    ).hexdigest()

    return f"{salt}${digest}"


def verify_password(
    password: str,
    stored_hash: str,
) -> bool:
    """
    Verify a password against the stored salted hash.
    """

    if not password or not stored_hash:
        return False

    try:
        salt, expected_hash = stored_hash.split(
            "$",
            1,
        )

        actual_hash = hashlib.sha256(
            (salt + password).encode("utf-8")
        ).hexdigest()

        return hmac.compare_digest(
            actual_hash,
            expected_hash,
        )

    except ValueError:
        return False


# ============================================================
# SESSION MANAGEMENT
# ============================================================

def create_session(user_id: int) -> str:
    """
    Create a secure random session token.
    """

    token = secrets.token_urlsafe(48)

    now = datetime.utcnow()

    SESSIONS[token] = {
        "user_id": user_id,
        "created_at": now,
        "expires_at": now + timedelta(
            hours=SESSION_EXPIRE_HOURS
        ),
    }

    return token


def delete_session(token: str) -> bool:
    """
    Delete a session.

    Returns:
        True if a session existed.
        False otherwise.
    """

    if token in SESSIONS:
        del SESSIONS[token]
        return True

    return False


def get_session(token: str) -> Optional[dict]:
    """
    Return an active session.

    Expired sessions are automatically removed.
    """

    if not token:
        return None

    session = SESSIONS.get(token)

    if not session:
        return None

    if datetime.utcnow() >= session["expires_at"]:
        del SESSIONS[token]
        return None

    return session


# ============================================================
# AUTHENTICATION
# ============================================================

def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> Optional[User]:
    """
    Authenticate a user using username/password.
    """

    user = (
        db.query(User)
        .filter(
            User.username == username,
            User.is_active.is_(True),
        )
        .first()
    )

    if not user:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user


def login_user(
    db: Session,
    username: str,
    password: str,
) -> Optional[dict]:
    """
    Authenticate a user and create a session.

    Returns a dictionary suitable for a login API response.
    """

    user = authenticate_user(
        db,
        username,
        password,
    )

    if not user:
        return None

    token = create_session(user.id)

    return {
        "success": True,
        "message": "Login successful.",
        "token": token,
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "organization_id": user.organization_id,
        "employee_id": user.employee_id,
    }


# ============================================================
# CURRENT USER
# ============================================================

def get_current_user(
    authorization: Optional[str] = Header(
        default=None
    ),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency for protected endpoints.

    Expected header:

        Authorization: Bearer <session-token>
    """

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if not authorization.lower().startswith(
        "bearer "
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header.",
        )

    token = authorization[7:].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing session token.",
        )

    session = get_session(token)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid.",
        )

    user = (
        db.query(User)
        .filter(
            User.id == session["user_id"],
            User.is_active.is_(True),
        )
        .first()
    )

    if not user:
        delete_session(token)

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or does not exist.",
        )

    return user


# ============================================================
# OPTIONAL USER DEPENDENCY
# ============================================================

def get_optional_user(
    authorization: Optional[str] = Header(
        default=None
    ),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Return the authenticated user if available.

    Unlike get_current_user(), this does not raise an error
    when no authentication header is provided.

    Useful for public health/demo endpoints.
    """

    if not authorization:
        return None

    if not authorization.lower().startswith(
        "bearer "
    ):
        return None

    token = authorization[7:].strip()

    if not token:
        return None

    session = get_session(token)

    if not session:
        return None

    user = (
        db.query(User)
        .filter(
            User.id == session["user_id"],
            User.is_active.is_(True),
        )
        .first()
    )

    return user


# ============================================================
# ROLE MANAGEMENT
# ============================================================

VALID_ROLES = {
    "Organization Admin",
    "Workforce Manager",
    "Project Manager",
    "Team Lead",
    "Employee",
}


def validate_role(role: str) -> bool:
    """
    Check whether a role is supported.
    """

    return role in VALID_ROLES


def require_roles(*allowed_roles: str):
    """
    Create a FastAPI dependency that allows only specified roles.

    Example:

        @router.get("/admin")
        def admin_route(
            user=Depends(
                require_roles("Organization Admin")
            )
        ):
            ...
    """

    invalid_roles = [
        role
        for role in allowed_roles
        if role not in VALID_ROLES
    ]

    if invalid_roles:
        raise ValueError(
            f"Invalid roles: {invalid_roles}"
        )

    def role_dependency(
        user: User = Depends(get_current_user),
    ) -> User:

        if user.role not in allowed_roles:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Insufficient permissions. "
                    f"Required role: "
                    f"{', '.join(allowed_roles)}."
                ),
            )

        return user

    return role_dependency


# ============================================================
# ORGANIZATION / TENANT ISOLATION
# ============================================================

def require_same_organization(
    user: User,
    organization_id: int,
) -> None:
    """
    Ensure the authenticated user can only access resources
    belonging to their organization.
    """

    if user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-organization access denied.",
        )


def verify_resource_organization(
    resource,
    user: User,
) -> None:
    """
    Generic organization validation for SQLAlchemy resources.

    The resource must have organization_id.
    """

    resource_org_id = getattr(
        resource,
        "organization_id",
        None,
    )

    if resource_org_id is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Resource does not contain "
                "organization information."
            ),
        )

    require_same_organization(
        user,
        resource_org_id,
    )


# ============================================================
# ACTION PERMISSIONS
# ============================================================

ROLE_PERMISSIONS = {
    "Organization Admin": {
        "view_workforce",
        "manage_employees",
        "manage_skills",
        "manage_projects",
        "manage_tasks",
        "allocate",
        "reallocate",
        "simulate",
        "crisis",
        "approve",
        "view_audit",
        "copilot",
    },

    "Workforce Manager": {
        "view_workforce",
        "manage_employees",
        "manage_skills",
        "manage_tasks",
        "allocate",
        "reallocate",
        "simulate",
        "crisis",
        "approve",
        "view_audit",
        "copilot",
    },

    "Project Manager": {
        "view_workforce",
        "manage_projects",
        "manage_tasks",
        "allocate",
        "simulate",
        "crisis",
        "copilot",
    },

    "Team Lead": {
        "view_workforce",
        "manage_tasks",
        "allocate",
        "reallocate",
        "simulate",
        "copilot",
    },

    "Employee": {
        "view_workforce",
        "simulate",
        "copilot",
    },
}


def has_permission(
    user: User,
    permission: str,
) -> bool:
    """
    Check whether a user has a specific permission.
    """

    permissions = ROLE_PERMISSIONS.get(
        user.role,
        set(),
    )

    return permission in permissions


def require_permission(
    permission: str,
):
    """
    FastAPI dependency for permission-based access control.
    """

    def permission_dependency(
        user: User = Depends(get_current_user),
    ) -> User:

        if not has_permission(
            user,
            permission,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission denied: {permission}"
                ),
            )

        return user

    return permission_dependency


# ============================================================
# HIGH-IMPACT ACTIONS
# ============================================================

HIGH_IMPACT_ACTIONS = {
    "bulk_reallocation",
    "critical_project_change",
    "large_workforce_change",
    "critical_sla_intervention",
    "crisis_execution",
}


def is_high_impact_action(
    action_type: str,
) -> bool:
    """
    Determine whether an action requires additional governance.
    """

    return action_type in HIGH_IMPACT_ACTIONS


# ============================================================
# AUTHORIZATION DECISION
# ============================================================

def authorize_action(
    user: User,
    action_type: str,
    permission: Optional[str] = None,
) -> dict:
    """
    Centralized authorization decision.

    Returns:

        {
            "allowed": True/False,
            "requires_approval": True/False,
            "reason": "..."
        }
    """

    if permission and not has_permission(
        user,
        permission,
    ):
        return {
            "allowed": False,
            "requires_approval": False,
            "reason": (
                f"User role '{user.role}' "
                f"does not have permission "
                f"'{permission}'."
            ),
        }

    requires_approval = is_high_impact_action(
        action_type
    )

    return {
        "allowed": True,
        "requires_approval": requires_approval,
        "reason": (
            "High-impact action requires human approval."
            if requires_approval
            else "Action permitted by current policy."
        ),
    }


# ============================================================
# LOGOUT
# ============================================================

def logout_token(
    authorization: Optional[str],
) -> bool:
    """
    Logout the current Bearer session.
    """

    if not authorization:
        return False

    if not authorization.lower().startswith(
        "bearer "
    ):
        return False

    token = authorization[7:].strip()

    if not token:
        return False

    return delete_session(token)
