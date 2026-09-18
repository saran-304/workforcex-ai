"""
WORKFORCEX AI
SQLAlchemy Database Models

Core entities:
- Organization
- User
- Team
- Employee
- Skill
- EmployeeSkill
- Project
- Task
- TaskDependency
- Assignment
- Availability
- SLA
- Approval
- AuditLog
- Scenario
- ScenarioResult
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


# ============================================================
# ORGANIZATION
# ============================================================

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    industry = Column(String(100), default="IT/Software")
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    teams = relationship(
        "Team",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    employees = relationship(
        "Employee",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    skills = relationship(
        "Skill",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    projects = relationship(
        "Project",
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    tasks = relationship(
        "Task",
        back_populates="organization",
        cascade="all, delete-orphan",
    )


# ============================================================
# USER
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    username = Column(
        String(100),
        nullable=False,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )

    role = Column(
        String(50),
        nullable=False,
        default="Employee",
    )

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=True,
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="users",
    )

    employee = relationship(
        "Employee",
        foreign_keys=[employee_id],
    )


# ============================================================
# TEAM
# ============================================================

class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False,
    )

    department = Column(
        String(150),
        nullable=False,
    )

    location = Column(
        String(150),
        default="India",
    )

    manager_name = Column(
        String(150),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="teams",
    )

    employees = relationship(
        "Employee",
        back_populates="team",
    )

    projects = relationship(
        "Project",
        back_populates="team",
    )


# ============================================================
# EMPLOYEE
# ============================================================

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    team_id = Column(
        Integer,
        ForeignKey("teams.id"),
        nullable=True,
        index=True,
    )

    employee_code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False,
    )

    email = Column(
        String(200),
        nullable=False,
    )

    role = Column(
        String(150),
        nullable=False,
    )

    location = Column(
        String(150),
        default="India",
    )

    availability_status = Column(
        String(50),
        default="available",
    )

    weekly_capacity_hours = Column(
        Float,
        default=40.0,
    )

    current_workload_hours = Column(
        Float,
        default=0.0,
    )

    utilization = Column(
        Float,
        default=0.0,
    )

    performance_score = Column(
        Float,
        default=75.0,
    )

    years_experience = Column(
        Float,
        default=1.0,
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="employees",
    )

    team = relationship(
        "Team",
        back_populates="employees",
    )

    skills = relationship(
        "EmployeeSkill",
        back_populates="employee",
        cascade="all, delete-orphan",
    )

    assignments = relationship(
        "Assignment",
        back_populates="employee",
    )

    availabilities = relationship(
        "Availability",
        back_populates="employee",
        cascade="all, delete-orphan",
    )


# ============================================================
# SKILL
# ============================================================

class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String(150),
        nullable=False,
    )

    category = Column(
        String(100),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="skills",
    )

    employees = relationship(
        "EmployeeSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
    )

    required_by_tasks = relationship(
        "TaskSkill",
        back_populates="skill",
        cascade="all, delete-orphan",
    )


# ============================================================
# EMPLOYEE SKILL
# ============================================================

class EmployeeSkill(Base):
    __tablename__ = "employee_skills"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )

    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False,
        index=True,
    )

    proficiency = Column(
        Float,
        nullable=False,
        default=50.0,
    )

    years_experience = Column(
        Float,
        default=1.0,
    )

    last_used_year = Column(
        Integer,
        nullable=True,
    )

    employee = relationship(
        "Employee",
        back_populates="skills",
    )

    skill = relationship(
        "Skill",
        back_populates="employees",
    )

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "skill_id",
            name="uq_employee_skill",
        ),
    )


# ============================================================
# PROJECT
# ============================================================

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    team_id = Column(
        Integer,
        ForeignKey("teams.id"),
        nullable=True,
    )

    project_code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    priority = Column(
        String(50),
        default="medium",
    )

    priority_score = Column(
        Float,
        default=50.0,
    )

    status = Column(
        String(50),
        default="active",
    )

    start_date = Column(
        DateTime,
        nullable=True,
    )

    deadline = Column(
        DateTime,
        nullable=True,
    )

    budget_hours = Column(
        Float,
        default=100.0,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="projects",
    )

    team = relationship(
        "Team",
        back_populates="projects",
    )

    tasks = relationship(
        "Task",
        back_populates="project",
    )


# ============================================================
# TASK
# ============================================================

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        nullable=True,
        index=True,
    )

    task_code = Column(
        String(50),
        nullable=False,
        index=True,
    )

    title = Column(
        String(250),
        nullable=False,
    )

    description = Column(
        Text,
        nullable=True,
    )

    priority = Column(
        String(50),
        default="medium",
    )

    priority_score = Column(
        Float,
        default=50.0,
    )

    status = Column(
        String(50),
        default="unassigned",
    )

    complexity = Column(
        Float,
        default=50.0,
    )

    estimated_hours = Column(
        Float,
        default=8.0,
    )

    remaining_hours = Column(
        Float,
        default=8.0,
    )

    deadline = Column(
        DateTime,
        nullable=True,
    )

    location_required = Column(
        String(150),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    organization = relationship(
        "Organization",
        back_populates="tasks",
    )

    project = relationship(
        "Project",
        back_populates="tasks",
    )

    required_skills = relationship(
        "TaskSkill",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    assignments = relationship(
        "Assignment",
        back_populates="task",
    )

    dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )

    dependent_on = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.depends_on_task_id",
        back_populates="depends_on_task",
        cascade="all, delete-orphan",
    )

    sla = relationship(
        "SLA",
        back_populates="task",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ============================================================
# TASK REQUIRED SKILL
# ============================================================

class TaskSkill(Base):
    __tablename__ = "task_skills"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False,
        index=True,
    )

    required_proficiency = Column(
        Float,
        default=50.0,
    )

    importance = Column(
        Float,
        default=1.0,
    )

    task = relationship(
        "Task",
        back_populates="required_skills",
    )

    skill = relationship(
        "Skill",
        back_populates="required_by_tasks",
    )

    __table_args__ = (
        UniqueConstraint(
            "task_id",
            "skill_id",
            name="uq_task_skill",
        ),
    )


# ============================================================
# TASK DEPENDENCY
# ============================================================

class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    depends_on_task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    dependency_type = Column(
        String(50),
        default="finish_to_start",
    )

    criticality = Column(
        Float,
        default=50.0,
    )

    task = relationship(
        "Task",
        foreign_keys=[task_id],
        back_populates="dependencies",
    )

    depends_on_task = relationship(
        "Task",
        foreign_keys=[depends_on_task_id],
        back_populates="dependent_on",
    )


# ============================================================
# ASSIGNMENT
# ============================================================

class Assignment(Base):
    __tablename__ = "assignments"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        index=True,
    )

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )

    assigned_hours = Column(
        Float,
        default=8.0,
    )

    allocation_percentage = Column(
        Float,
        default=20.0,
    )

    status = Column(
        String(50),
        default="active",
    )

    assigned_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    completed_at = Column(
        DateTime,
        nullable=True,
    )

    assignment_reason = Column(
        Text,
        nullable=True,
    )

    score = Column(
        Float,
        nullable=True,
    )

    employee = relationship(
        "Employee",
        back_populates="assignments",
    )

    task = relationship(
        "Task",
        back_populates="assignments",
    )


# ============================================================
# AVAILABILITY
# ============================================================

class Availability(Base):
    __tablename__ = "availability"

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
        index=True,
    )

    start_date = Column(
        DateTime,
        nullable=False,
    )

    end_date = Column(
        DateTime,
        nullable=False,
    )

    status = Column(
        String(50),
        default="available",
    )

    available_hours = Column(
        Float,
        default=40.0,
    )

    reason = Column(
        String(250),
        nullable=True,
    )

    employee = relationship(
        "Employee",
        back_populates="availabilities",
    )


# ============================================================
# SLA
# ============================================================

class SLA(Base):
    __tablename__ = "slas"

    id = Column(Integer, primary_key=True, index=True)

    task_id = Column(
        Integer,
        ForeignKey("tasks.id"),
        nullable=False,
        unique=True,
        index=True,
    )

    target_hours = Column(
        Float,
        default=24.0,
    )

    remaining_hours = Column(
        Float,
        default=24.0,
    )

    status = Column(
        String(50),
        default="healthy",
    )

    risk_score = Column(
        Float,
        default=0.0,
    )

    breach_at = Column(
        DateTime,
        nullable=True,
    )

    task = relationship(
        "Task",
        back_populates="sla",
    )


# ============================================================
# APPROVAL
# ============================================================

class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    requested_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    action_type = Column(
        String(100),
        nullable=False,
    )

    action_payload = Column(
        Text,
        nullable=False,
    )

    reason = Column(
        Text,
        nullable=True,
    )

    risk_before = Column(
        Float,
        default=0.0,
    )

    risk_after = Column(
        Float,
        default=0.0,
    )

    simulation_result = Column(
        Text,
        nullable=True,
    )

    affected_resources = Column(
        Text,
        nullable=True,
    )

    status = Column(
        String(50),
        default="pending",
    )

    reviewed_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    reviewed_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )


# ============================================================
# AUDIT LOG
# ============================================================

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    action = Column(
        String(150),
        nullable=False,
    )

    resource_type = Column(
        String(100),
        nullable=True,
    )

    resource_id = Column(
        String(100),
        nullable=True,
    )

    before_state = Column(
        Text,
        nullable=True,
    )

    decision_evidence = Column(
        Text,
        nullable=True,
    )

    ai_recommendation = Column(
        Text,
        nullable=True,
    )

    simulation_result = Column(
        Text,
        nullable=True,
    )

    approval_decision = Column(
        String(100),
        nullable=True,
    )

    after_state = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True,
    )


# ============================================================
# SCENARIO
# ============================================================

class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(
        Integer,
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    name = Column(
        String(200),
        nullable=False,
    )

    scenario_type = Column(
        String(100),
        nullable=False,
    )

    input_data = Column(
        Text,
        nullable=False,
    )

    status = Column(
        String(50),
        default="created",
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    results = relationship(
        "ScenarioResult",
        back_populates="scenario",
        cascade="all, delete-orphan",
    )


# ============================================================
# SCENARIO RESULT
# ============================================================

class ScenarioResult(Base):
    __tablename__ = "scenario_results"

    id = Column(Integer, primary_key=True, index=True)

    scenario_id = Column(
        Integer,
        ForeignKey("scenarios.id"),
        nullable=False,
        index=True,
    )

    strategy_name = Column(
        String(150),
        nullable=False,
    )

    baseline_data = Column(
        Text,
        nullable=False,
    )

    scenario_data = Column(
        Text,
        nullable=False,
    )

    risk_change = Column(
        Float,
        default=0.0,
    )

    capacity_change = Column(
        Float,
        default=0.0,
    )

    sla_change = Column(
        Float,
        default=0.0,
    )

    dependency_impact = Column(
        Text,
        nullable=True,
    )

    recommendation = Column(
        Text,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    scenario = relationship(
        "Scenario",
        back_populates="results",
    )
