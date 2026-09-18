"""
WORKFORCEX AI
FastAPI Shared Dependencies

Centralizes:
- Database sessions
- Current authenticated user
- Role checks
- Permission checks
- Organization/tenant validation
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import (
    get_current_user,
    has_permission,
    require_roles,
)
from database import get_db
from models import User


# ============================================================
# DATABASE
# ============================================================

def database_session(
    db: Session = Depends(get_db),
) -> Session:
    """
    Shared database dependency.

    Usage:

        db: Session = Depends(database_session)
    """

    return db


# ============================================================
# CURRENT USER
# ============================================================

def authenticated_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Require an authenticated user.
    """

    return user


# ============================================================
# ORGANIZATION ID
# ============================================================

def current_organization_id(
    user: User = Depends(authenticated_user),
) -> int:
    """
    Return the authenticated user's organization ID.
    """

    if not user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not associated with an organization.",
        )

    return user.organization_id


# ============================================================
# ROLE DEPENDENCIES
# ============================================================

def organization_admin(
    user: User = Depends(authenticated_user),
) -> User:
    """
    Organization Admin only.
    """

    if user.role != "Organization Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization Admin role required.",
        )

    return user


def workforce_manager(
    user: User = Depends(authenticated_user),
) -> User:
    """
    Organization Admin or Workforce Manager.
    """

    allowed_roles = {
        "Organization Admin",
        "Workforce Manager",
    }

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Organization Admin or Workforce Manager "
                "role required."
            ),
        )

    return user


def project_manager(
    user: User = Depends(authenticated_user),
) -> User:
    """
    Organization Admin, Workforce Manager or Project Manager.
    """

    allowed_roles = {
        "Organization Admin",
        "Workforce Manager",
        "Project Manager",
    }

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Project Manager level access required."
            ),
        )

    return user


def team_lead(
    user: User = Depends(authenticated_user),
) -> User:
    """
    Organization Admin, Workforce Manager, Project Manager
    or Team Lead.
    """

    allowed_roles = {
        "Organization Admin",
        "Workforce Manager",
        "Project Manager",
        "Team Lead",
    }

    if user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Team Lead level access required.",
        )

    return user


# ============================================================
# PERMISSION FACTORY
# ============================================================

def permission_dependency(
    permission: str,
):
    """
    Create a FastAPI dependency requiring a specific
    WORKFORCEX permission.

    Example:

        Depends(permission_dependency("allocate"))
    """

    def dependency(
        user: User = Depends(authenticated_user),
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

    return dependency


# ============================================================
# COMMON PERMISSIONS
# ============================================================

def can_view_workforce(
    user: User = Depends(
        permission_dependency("view_workforce")
    ),
) -> User:
    return user


def can_manage_employees(
    user: User = Depends(
        permission_dependency("manage_employees")
    ),
) -> User:
    return user


def can_manage_skills(
    user: User = Depends(
        permission_dependency("manage_skills")
    ),
) -> User:
    return user


def can_manage_projects(
    user: User = Depends(
        permission_dependency("manage_projects")
    ),
) -> User:
    return user


def can_manage_tasks(
    user: User = Depends(
        permission_dependency("manage_tasks")
    ),
) -> User:
    return user


def can_allocate(
    user: User = Depends(
        permission_dependency("allocate")
    ),
) -> User:
    return user


def can_reallocate(
    user: User = Depends(
        permission_dependency("reallocate")
    ),
) -> User:
    return user


def can_simulate(
    user: User = Depends(
        permission_dependency("simulate")
    ),
) -> User:
    return user


def can_crisis(
    user: User = Depends(
        permission_dependency("crisis")
    ),
) -> User:
    return user


def can_approve(
    user: User = Depends(
        permission_dependency("approve")
    ),
) -> User:
    return user


def can_view_audit(
    user: User = Depends(
        permission_dependency("view_audit")
    ),
) -> User:
    return user


def can_use_copilot(
    user: User = Depends(
        permission_dependency("copilot")
    ),
) -> User:
    return user


# ============================================================
# RESOURCE TENANT VALIDATION
# ============================================================

def ensure_same_organization(
    user: User,
    organization_id: int,
) -> None:
    """
    Ensure a resource belongs to the logged-in user's
    organization.

    This is a critical tenant-isolation check.
    """

    if user.organization_id != organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-organization access denied.",
        )


def ensure_resource_access(
    user: User,
    resource,
) -> None:
    """
    Validate access to any SQLAlchemy resource containing
    organization_id.
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
                "Resource cannot be validated because "
                "organization_id is missing."
            ),
        )

    ensure_same_organization(
        user,
        resource_org_id,
    )


# ============================================================
# RESOURCE LOOKUP HELPERS
# ============================================================

def get_user_organization(
    user: User = Depends(authenticated_user),
) -> int:
    """
    Return the organization associated with the user.
    """

    return user.organization_id


# ============================================================
# ACTIVE USER CHECK
# ============================================================

def active_user(
    user: User = Depends(authenticated_user),
) -> User:
    """
    Additional protection for endpoints that require
    an active account.
    """

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive.",
        )

    return user
