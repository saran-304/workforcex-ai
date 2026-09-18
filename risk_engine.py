"""
WORKFORCEX AI
Operational Risk & SLA Intelligence Engine

Purpose:
    Detect real workforce operational risks from database state.

This engine does NOT use an LLM for calculations.

It analyzes:
    - employee workload
    - capacity
    - availability
    - SLA deadlines
    - project priority
    - task dependencies
    - skill shortages
    - deadline concentration
    - overloaded teams
    - assignment instability

All results are deterministic and reproducible.

AI/Copilot can later explain these results, but this engine
remains functional even when Gemini/Grok is unavailable.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import (
    Employee,
    EmployeeSkill,
    Skill,
    Task,
    Assignment,
    SLA,
    TaskDependency,
    Project,
)


# ============================================================
# CONSTANTS
# ============================================================

CRITICAL_HOURS = 6
HIGH_RISK_HOURS = 12
MEDIUM_RISK_HOURS = 24

WORKLOAD_HIGH = 80
WORKLOAD_CRITICAL = 95

UTILIZATION_HIGH = 85
UTILIZATION_CRITICAL = 95


# ============================================================
# BASIC HELPERS
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
    """Keep a number inside a fixed range."""

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def priority_value(
    priority: Optional[str],
) -> int:
    """
    Convert business priority into a numerical value.
    """

    values = {
        "Critical": 4,
        "High": 3,
        "Medium": 2,
        "Low": 1,
    }

    return values.get(
        priority or "Low",
        1,
    )


def risk_level(
    score: float,
) -> str:
    """
    Convert numerical risk into a readable level.
    """

    if score >= 80:
        return "Critical"

    if score >= 60:
        return "High"

    if score >= 35:
        return "Medium"

    return "Low"


# ============================================================
# EMPLOYEE WORKLOAD RISK
# ============================================================

def calculate_employee_workload_risk(
    employee: Employee,
) -> dict:
    """
    Calculate operational workload pressure for one employee.

    This is an operational capacity metric only.

    It is NOT a medical, psychological or mental-health metric.
    """

    workload = float(
        employee.current_workload_percent
        or 0
    )

    capacity = float(
        employee.capacity_percent
        or 0
    )

    performance = float(
        employee.historical_performance
        or 0.70
    )

    pressure = 0.0

    if capacity > 0:
        pressure = (
            workload / capacity
        ) * 100

    overload = max(
        0,
        workload - capacity,
    )

    score = (
        min(workload, 100) * 0.60
        +
        min(pressure, 150) * 0.25
        +
        min(overload, 50) * 0.10
        +
        (1 - performance) * 100 * 0.05
    )

    if (
        employee.availability_status
        == "Unavailable"
    ):
        score += 15

    elif (
        employee.availability_status
        == "Partial"
    ):
        score += 5

    score = clamp(
        score
    )

    reasons = []

    if workload >= WORKLOAD_CRITICAL:
        reasons.append(
            "Employee workload is at critical level."
        )

    elif workload >= WORKLOAD_HIGH:
        reasons.append(
            "Employee workload is high."
        )

    if overload > 0:
        reasons.append(
            f"Workload exceeds capacity by "
            f"{round(overload, 1)}%."
        )

    if (
        employee.availability_status
        == "Unavailable"
    ):
        reasons.append(
            "Employee is currently unavailable."
        )

    elif (
        employee.availability_status
        == "Partial"
    ):
        reasons.append(
            "Employee has partial availability."
        )

    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "employee_name": employee.name,
        "workload_percent": workload,
        "capacity_percent": capacity,
        "remaining_capacity": max(
            0,
            capacity - workload,
        ),
        "utilization_percent": round(
            pressure,
            2,
        ),
        "pressure_score": round(
            score,
            2,
        ),
        "risk_level": risk_level(
            score
        ),
        "availability": (
            employee.availability_status
        ),
        "reasons": reasons,
    }


# ============================================================
# ALL EMPLOYEE RISKS
# ============================================================

def detect_employee_workload_risks(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Detect overloaded or operationally pressured employees.
    """

    employees = (
        db.query(Employee)
        .filter(
            Employee.organization_id
            == organization_id,
            Employee.is_active.is_(True),
        )
        .all()
    )

    risks = []

    for employee in employees:

        result = (
            calculate_employee_workload_risk(
                employee
            )
        )

        if result["pressure_score"] >= 35:

            risks.append(
                result
            )

    risks.sort(
        key=lambda item: item[
            "pressure_score"
        ],
        reverse=True,
    )

    return risks


# ============================================================
# SLA ANALYSIS
# ============================================================

def calculate_sla_risk(
    db: Session,
    task: Task,
) -> Optional[dict]:
    """
    Calculate SLA exposure for one task.
    """

    sla = (
        db.query(SLA)
        .filter(
            SLA.task_id == task.id
        )
        .first()
    )

    if not sla:
        return None

    now = datetime.utcnow()

    seconds_remaining = (
        sla.deadline - now
    ).total_seconds()

    hours_remaining = (
        seconds_remaining / 3600
    )

    if hours_remaining <= 0:

        score = 100
        status = "Breached"
        level = "Critical"

    elif hours_remaining <= CRITICAL_HOURS:

        score = 90
        status = "At Risk"
        level = "Critical"

    elif hours_remaining <= HIGH_RISK_HOURS:

        score = 75
        status = "At Risk"
        level = "High"

    elif hours_remaining <= MEDIUM_RISK_HOURS:

        score = 50
        status = "Watch"
        level = "Medium"

    else:

        score = 15
        status = "On Track"
        level = "Low"

    # Critical/high priority tasks get additional urgency.
    if task.priority == "Critical":

        score += 10

    elif task.priority == "High":

        score += 5

    score = clamp(
        score
    )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "project_id": task.project_id,
        "deadline": sla.deadline.isoformat(),
        "hours_remaining": round(
            hours_remaining,
            2,
        ),
        "status": status,
        "risk_level": level,
        "risk_score": round(
            score,
            2,
        ),
        "priority": task.priority,
    }


# ============================================================
# ALL SLA RISKS
# ============================================================

def detect_sla_risks(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Detect all tasks with SLA exposure.
    """

    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id
            == organization_id,
            Task.status != "Completed",
        )
        .all()
    )

    results = []

    for task in tasks:

        result = calculate_sla_risk(
            db,
            task,
        )

        if result is not None:

            if result["risk_score"] >= 50:

                results.append(
                    result
                )

    results.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# TASK ASSIGNMENT RISK
# ============================================================

def calculate_task_assignment_risk(
    db: Session,
    task: Task,
) -> dict:
    """
    Determine whether the current assignment of a task
    creates operational risk.
    """

    assignment = (
        db.query(Assignment)
        .filter(
            Assignment.task_id
            == task.id,
            Assignment.status
            == "Active",
        )
        .first()
    )

    if not assignment:

        return {
            "task_id": task.id,
            "assigned": False,
            "risk_score": 80,
            "risk_level": "High",
            "reasons": [
                "Task has no active assignment."
            ],
        }

    employee = (
        db.query(Employee)
        .filter(
            Employee.id
            == assignment.employee_id
        )
        .first()
    )

    if not employee:

        return {
            "task_id": task.id,
            "assigned": False,
            "risk_score": 100,
            "risk_level": "Critical",
            "reasons": [
                "Assignment references a missing employee."
            ],
        }

    workload_result = (
        calculate_employee_workload_risk(
            employee
        )
    )

    sla_result = (
        calculate_sla_risk(
            db,
            task,
        )
    )

    score = (
        workload_result[
            "pressure_score"
        ] * 0.50
    )

    reasons = []

    if workload_result[
        "pressure_score"
    ] >= 60:

        score += 20

        reasons.append(
            "Assigned employee has high workload pressure."
        )

    if (
        employee.availability_status
        == "Unavailable"
    ):

        score += 30

        reasons.append(
            "Assigned employee is unavailable."
        )

    elif (
        employee.availability_status
        == "Partial"
    ):

        score += 10

        reasons.append(
            "Assigned employee is partially available."
        )

    if sla_result:

        score += (
            sla_result[
                "risk_score"
            ] * 0.25
        )

        if sla_result[
            "risk_score"
        ] >= 75:

            reasons.append(
                "Task has significant SLA exposure."
            )

    score = clamp(
        score
    )

    if not reasons:
        reasons.append(
            "Current assignment has no major detected operational risk."
        )

    return {
        "task_id": task.id,
        "task_title": task.title,
        "assigned": True,
        "employee_id": employee.id,
        "employee_name": employee.name,
        "risk_score": round(
            score,
            2,
        ),
        "risk_level": risk_level(
            score
        ),
        "workload_risk": workload_result,
        "sla_risk": sla_result,
        "reasons": reasons,
    }


# ============================================================
# TASK DEPENDENCY RISK
# ============================================================

def calculate_dependency_risk(
    db: Session,
    task: Task,
) -> dict:
    """
    Analyze dependency pressure around a task.
    """

    upstream = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.successor_task_id
            == task.id
        )
        .all()
    )

    downstream = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.predecessor_task_id
            == task.id
        )
        .all()
    )

    upstream_count = len(
        upstream
    )

    downstream_count = len(
        downstream
    )

    critical_downstream = 0

    for dependency in downstream:

        child_task = (
            db.query(Task)
            .filter(
                Task.id
                == dependency.successor_task_id
            )
            .first()
        )

        if child_task and (
            child_task.priority
            in {
                "Critical",
                "High",
            }
        ):
            critical_downstream += 1

    score = (
        downstream_count * 15
        +
        critical_downstream * 20
        +
        upstream_count * 5
    )

    score = clamp(
        score
    )

    return {
        "task_id": task.id,
        "upstream_dependencies": upstream_count,
        "downstream_dependencies": downstream_count,
        "critical_downstream_tasks": (
            critical_downstream
        ),
        "risk_score": round(
            score,
            2,
        ),
        "risk_level": risk_level(
            score
        ),
    }


# ============================================================
# SKILL SHORTAGE DETECTION
# ============================================================

def detect_skill_shortages(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Compare required task skills against available employee
    skills.

    Produces real skill shortage information.
    """

    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id
            == organization_id,
            Task.status != "Completed",
        )
        .all()
    )

    employees = (
        db.query(Employee)
        .filter(
            Employee.organization_id
            == organization_id,
            Employee.is_active.is_(True),
        )
        .all()
    )

    # --------------------------------------------------------
    # Build employee skill availability map.
    # --------------------------------------------------------

    available_skills = {}

    for employee in employees:

        if (
            employee.availability_status
            == "Unavailable"
        ):
            continue

        rows = (
            db.query(
                EmployeeSkill,
                Skill,
            )
            .join(
                Skill,
                EmployeeSkill.skill_id
                == Skill.id,
            )
            .filter(
                EmployeeSkill.employee_id
                == employee.id
            )
            .all()
        )

        for employee_skill, skill in rows:

            if skill.name not in available_skills:

                available_skills[
                    skill.name
                ] = {
                    "employees": [],
                    "strong_employees": [],
                }

            available_skills[
                skill.name
            ][
                "employees"
            ].append(
                employee.id
            )

            if (
                employee_skill.proficiency
                >= 4
            ):

                available_skills[
                    skill.name
                ][
                    "strong_employees"
                ].append(
                    employee.id
                )

    # --------------------------------------------------------
    # Count demand.
    # --------------------------------------------------------

    demand = {}

    for task in tasks:

        if not task.required_skill_id:
            continue

        skill = (
            db.query(Skill)
            .filter(
                Skill.id
                == task.required_skill_id
            )
            .first()
        )

        if not skill:
            continue

        if skill.name not in demand:

            demand[
                skill.name
            ] = {
                "task_count": 0,
                "critical_tasks": 0,
                "high_tasks": 0,
            }

        demand[
            skill.name
        ][
            "task_count"
        ] += 1

        if task.priority == "Critical":

            demand[
                skill.name
            ][
                "critical_tasks"
            ] += 1

        elif task.priority == "High":

            demand[
                skill.name
            ][
                "high_tasks"
            ] += 1

    results = []

    for skill_name, demand_data in demand.items():

        supply_data = available_skills.get(
            skill_name,
            {
                "employees": [],
                "strong_employees": [],
            },
        )

        available_count = len(
            supply_data["employees"]
        )

        strong_count = len(
            supply_data["strong_employees"]
        )

        demand_count = demand_data[
            "task_count"
        ]

        shortage = max(
            0,
            demand_count
            - available_count,
        )

        if shortage > 0:

            score = min(
                100,
                (
                    shortage
                    / max(
                        demand_count,
                        1,
                    )
                )
                * 100,
            )

            if demand_data[
                "critical_tasks"
            ] > 0:

                score += 20

            score = clamp(
                score
            )

            results.append(
                {
                    "skill": skill_name,
                    "task_demand": demand_count,
                    "critical_tasks": (
                        demand_data[
                            "critical_tasks"
                        ]
                    ),
                    "high_priority_tasks": (
                        demand_data[
                            "high_tasks"
                        ]
                    ),
                    "available_employees": (
                        available_count
                    ),
                    "strong_skill_employees": (
                        strong_count
                    ),
                    "shortage_count": shortage,
                    "risk_score": round(
                        score,
                        2,
                    ),
                    "risk_level": risk_level(
                        score
                    ),
                }
            )

    results.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# DEADLINE CONCENTRATION
# ============================================================

def detect_deadline_concentration(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Detect periods where many tasks have deadlines close
    together.

    This identifies operational deadline concentration.
    """

    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id
            == organization_id,
            Task.status != "Completed",
        )
        .all()
    )

    deadlines = []

    for task in tasks:

        sla = (
            db.query(SLA)
            .filter(
                SLA.task_id
                == task.id
            )
            .first()
        )

        if sla:
            deadlines.append(
                (
                    task,
                    sla.deadline,
                )
            )

    results = []

    for task, deadline in deadlines:

        nearby_tasks = []

        for other_task, other_deadline in deadlines:

            if (
                other_task.id
                == task.id
            ):
                continue

            difference = abs(
                (
                    other_deadline
                    - deadline
                ).total_seconds()
            ) / 3600

            if difference <= 24:

                nearby_tasks.append(
                    other_task.id
                )

        concentration = len(
            nearby_tasks
        )

        if concentration >= 3:

            score = min(
                100,
                concentration * 15,
            )

            results.append(
                {
                    "task_id": task.id,
                    "deadline": deadline.isoformat(),
                    "nearby_task_count": concentration,
                    "nearby_task_ids": nearby_tasks,
                    "risk_score": round(
                        score,
                        2,
                    ),
                    "risk_level": risk_level(
                        score
                    ),
                }
            )

    results.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# TEAM CAPACITY RISK
# ============================================================

def detect_team_capacity_risks(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Detect teams where total workload is approaching or
    exceeding available capacity.
    """

    employees = (
        db.query(Employee)
        .filter(
            Employee.organization_id
            == organization_id,
            Employee.is_active.is_(True),
        )
        .all()
    )

    teams = {}

    for employee in employees:

        team_id = employee.team_id

        if team_id is None:
            continue

        if team_id not in teams:

            teams[team_id] = {
                "employee_count": 0,
                "capacity": 0.0,
                "workload": 0.0,
                "unavailable": 0,
            }

        teams[
            team_id
        ][
            "employee_count"
        ] += 1

        teams[
            team_id
        ][
            "capacity"
        ] += float(
            employee.capacity_percent
            or 0
        )

        teams[
            team_id
        ][
            "workload"
        ] += float(
            employee.current_workload_percent
            or 0
        )

        if (
            employee.availability_status
            == "Unavailable"
        ):

            teams[
                team_id
            ][
                "unavailable"
            ] += 1

    results = []

    for team_id, data in teams.items():

        capacity = data[
            "capacity"
        ]

        workload = data[
            "workload"
        ]

        utilization = (
            workload / capacity * 100
            if capacity > 0
            else 100
        )

        score = 0

        if utilization >= UTILIZATION_CRITICAL:

            score = 95

        elif utilization >= UTILIZATION_HIGH:

            score = 70

        elif utilization >= 70:

            score = 40

        if data["unavailable"] > 0:

            score += (
                data["unavailable"]
                * 10
            )

        score = clamp(
            score
        )

        if score >= 35:

            results.append(
                {
                    "team_id": team_id,
                    "employee_count": data[
                        "employee_count"
                    ],
                    "capacity": round(
                        capacity,
                        2,
                    ),
                    "workload": round(
                        workload,
                        2,
                    ),
                    "utilization_percent": round(
                        utilization,
                        2,
                    ),
                    "unavailable_employees": data[
                        "unavailable"
                    ],
                    "remaining_capacity": round(
                        max(
                            0,
                            capacity
                            - workload,
                        ),
                        2,
                    ),
                    "risk_score": round(
                        score,
                        2,
                    ),
                    "risk_level": risk_level(
                        score
                    ),
                }
            )

    results.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# UNSTABLE ASSIGNMENT DETECTION
# ============================================================

def detect_unstable_assignments(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Detect operationally unstable assignments.

    If an assignment points to an unavailable employee,
    it becomes a high-priority reallocation candidate.
    """

    assignments = (
        db.query(Assignment)
        .filter(
            Assignment.organization_id
            == organization_id,
            Assignment.status
            == "Active",
        )
        .all()
    )

    results = []

    for assignment in assignments:

        employee = (
            db.query(Employee)
            .filter(
                Employee.id
                == assignment.employee_id
            )
            .first()
        )

        task = (
            db.query(Task)
            .filter(
                Task.id
                == assignment.task_id
            )
            .first()
        )

        if not employee or not task:
            continue

        reasons = []

        score = 0

        if (
            employee.availability_status
            == "Unavailable"
        ):

            score += 90

            reasons.append(
                "Assigned employee is unavailable."
            )

        elif (
            employee.availability_status
            == "Partial"
        ):

            score += 40

            reasons.append(
                "Assigned employee is partially available."
            )

        workload = float(
            employee.current_workload_percent
            or 0
        )

        capacity = float(
            employee.capacity_percent
            or 0
        )

        if workload > capacity:

            score += 30

            reasons.append(
                "Employee workload exceeds capacity."
            )

        elif workload >= 90:

            score += 20

            reasons.append(
                "Employee workload is critically high."
            )

        if score >= 40:

            results.append(
                {
                    "assignment_id": assignment.id,
                    "task_id": task.id,
                    "task_title": task.title,
                    "employee_id": employee.id,
                    "employee_name": employee.name,
                    "risk_score": clamp(
                        score
                    ),
                    "risk_level": risk_level(
                        score
                    ),
                    "reasons": reasons,
                }
            )

    results.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return results


# ============================================================
# CRITICAL TASK DETECTION
# ============================================================

def detect_critical_tasks(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Return active Critical/High tasks with their current
    assignment and risk state.
    """

    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id
            == organization_id,
            Task.status != "Completed",
            Task.priority.in_(
                [
                    "Critical",
                    "High",
                ]
            ),
        )
        .all()
    )

    results = []

    for task in tasks:

        assignment = (
            db.query(Assignment)
            .filter(
                Assignment.task_id
                == task.id,
                Assignment.status
                == "Active",
            )
            .first()
        )

        employee = None

        if assignment:

            employee = (
                db.query(Employee)
                .filter(
                    Employee.id
                    == assignment.employee_id
                )
                .first()
            )

        sla = calculate_sla_risk(
            db,
            task,
        )

        results.append(
            {
                "task_id": task.id,
                "task_title": task.title,
                "priority": task.priority,
                "status": task.status,
                "assigned": bool(
                    assignment
                ),
                "employee_id": (
                    employee.id
                    if employee
                    else None
                ),
                "employee_name": (
                    employee.name
                    if employee
                    else None
                ),
                "sla_risk": sla,
            }
        )

    return results


# ============================================================
# ORGANIZATION RISK SUMMARY
# ============================================================

def calculate_organization_risk_summary(
    db: Session,
    organization_id: int,
) -> dict:
    """
    Build one complete risk summary for the dashboard.

    This is the primary endpoint/service used by the
    Command Center.
    """

    employee_risks = (
        detect_employee_workload_risks(
            db,
            organization_id,
        )
    )

    sla_risks = (
        detect_sla_risks(
            db,
            organization_id,
        )
    )

    skill_shortages = (
        detect_skill_shortages(
            db,
            organization_id,
        )
    )

    deadline_risks = (
        detect_deadline_concentration(
            db,
            organization_id,
        )
    )

    team_risks = (
        detect_team_capacity_risks(
            db,
            organization_id,
        )
    )

    unstable_assignments = (
        detect_unstable_assignments(
            db,
            organization_id,
        )
    )

    critical_tasks = (
        detect_critical_tasks(
            db,
            organization_id,
        )
    )

    # --------------------------------------------------------
    # Overall score
    # --------------------------------------------------------

    risk_scores = []

    risk_scores.extend(
        [
            item["pressure_score"]
            for item in employee_risks
        ]
    )

    risk_scores.extend(
        [
            item["risk_score"]
            for item in sla_risks
        ]
    )

    risk_scores.extend(
        [
            item["risk_score"]
            for item in skill_shortages
        ]
    )

    risk_scores.extend(
        [
            item["risk_score"]
            for item in team_risks
        ]
    )

    risk_scores.extend(
        [
            item["risk_score"]
            for item in unstable_assignments
        ]
    )

    if risk_scores:

        overall_risk = (
            sum(risk_scores)
            / len(risk_scores)
        )

        # Critical events should have stronger influence.
        highest_risk = max(
            risk_scores
        )

        overall_risk = (
            overall_risk * 0.60
            +
            highest_risk * 0.40
        )

    else:

        overall_risk = 0.0

    overall_risk = clamp(
        overall_risk
    )

    return {
        "organization_id": organization_id,

        "overall_risk_score": round(
            overall_risk,
            2,
        ),

        "overall_risk_level": risk_level(
            overall_risk
        ),

        "employee_workload_risks": employee_risks,

        "sla_risks": sla_risks,

        "skill_shortages": skill_shortages,

        "deadline_concentration": deadline_risks,

        "team_capacity_risks": team_risks,

        "unstable_assignments": unstable_assignments,

        "critical_tasks": critical_tasks,

        "counts": {
            "employee_workload_risks": len(
                employee_risks
            ),
            "sla_risks": len(
                sla_risks
            ),
            "skill_shortages": len(
                skill_shortages
            ),
            "deadline_risks": len(
                deadline_risks
            ),
            "team_capacity_risks": len(
                team_risks
            ),
            "unstable_assignments": len(
                unstable_assignments
            ),
            "critical_tasks": len(
                critical_tasks
            ),
        },

        "generated_at": (
            datetime.utcnow().isoformat()
        ),
    }


# ============================================================
# TOP RISKS
# ============================================================

def get_top_risks(
    db: Session,
    organization_id: int,
    limit: int = 10,
) -> List[dict]:
    """
    Return a unified list of the most important risks.
    """

    summary = (
        calculate_organization_risk_summary(
            db,
            organization_id,
        )
    )

    risks = []

    # --------------------------------------------------------
    # Employee risks
    # --------------------------------------------------------

    for item in summary[
        "employee_workload_risks"
    ]:

        risks.append(
            {
                "type": "Workload Pressure",
                "resource_id": item[
                    "employee_id"
                ],
                "resource_name": item[
                    "employee_name"
                ],
                "risk_score": item[
                    "pressure_score"
                ],
                "risk_level": item[
                    "risk_level"
                ],
                "reason": "; ".join(
                    item["reasons"]
                ),
            }
        )

    # --------------------------------------------------------
    # SLA risks
    # --------------------------------------------------------

    for item in summary[
        "sla_risks"
    ]:

        risks.append(
            {
                "type": "SLA Exposure",
                "resource_id": item[
                    "task_id"
                ],
                "resource_name": item[
                    "task_title"
                ],
                "risk_score": item[
                    "risk_score"
                ],
                "risk_level": item[
                    "risk_level"
                ],
                "reason": (
                    f"{item['status']}; "
                    f"{item['hours_remaining']} "
                    "hours remaining."
                ),
            }
        )

    # --------------------------------------------------------
    # Skill shortage risks
    # --------------------------------------------------------

    for item in summary[
        "skill_shortages"
    ]:

        risks.append(
            {
                "type": "Skill Shortage",
                "resource_id": None,
                "resource_name": item[
                    "skill"
                ],
                "risk_score": item[
                    "risk_score"
                ],
                "risk_level": item[
                    "risk_level"
                ],
                "reason": (
                    f"{item['shortage_count']} "
                    f"more capable resource(s) "
                    "may be required."
                ),
            }
        )

    # --------------------------------------------------------
    # Unstable assignments
    # --------------------------------------------------------

    for item in summary[
        "unstable_assignments"
    ]:

        risks.append(
            {
                "type": "Assignment Instability",
                "resource_id": item[
                    "task_id"
                ],
                "resource_name": item[
                    "task_title"
                ],
                "risk_score": item[
                    "risk_score"
                ],
                "risk_level": item[
                    "risk_level"
                ],
                "reason": "; ".join(
                    item["reasons"]
                ),
            }
        )

    risks.sort(
        key=lambda item: item[
            "risk_score"
        ],
        reverse=True,
    )

    return risks[:limit]


# ============================================================
# RISK RECOMMENDATIONS
# ============================================================

def generate_risk_recommendations(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Convert detected risks into actionable recommendations.

    This does NOT execute any action.
    """

    summary = (
        calculate_organization_risk_summary(
            db,
            organization_id,
        )
    )

    recommendations = []

    # --------------------------------------------------------
    # SLA recommendations
    # --------------------------------------------------------

    for risk in summary[
        "sla_risks"
    ]:

        if risk[
            "risk_level"
        ] in {
            "Critical",
            "High",
        }:

            recommendations.append(
                {
                    "type": "SLA",
                    "priority": risk[
                        "risk_level"
                    ],
                    "task_id": risk[
                        "task_id"
                    ],
                    "recommendation": (
                        "Review task allocation "
                        "and consider reallocation "
                        "or controlled reprioritization."
                    ),
                    "reason": (
                        f"{risk['hours_remaining']} "
                        "hours remain before SLA "
                        "deadline."
                    ),
                }
            )

    # --------------------------------------------------------
    # Workload recommendations
    # --------------------------------------------------------

    for risk in summary[
        "employee_workload_risks"
    ]:

        if risk[
            "risk_level"
        ] in {
            "Critical",
            "High",
        }:

            recommendations.append(
                {
                    "type": "Capacity",
                    "priority": risk[
                        "risk_level"
                    ],
                    "employee_id": risk[
                        "employee_id"
                    ],
                    "recommendation": (
                        "Review workload and "
                        "consider reallocating "
                        "lower-priority work."
                    ),
                    "reason": "; ".join(
                        risk["reasons"]
                    ),
                }
            )

    # --------------------------------------------------------
    # Skill shortage recommendations
    # --------------------------------------------------------

    for risk in summary[
        "skill_shortages"
    ]:

        if risk[
            "risk_level"
        ] in {
            "Critical",
            "High",
        }:

            recommendations.append(
                {
                    "type": "Skill",
                    "priority": risk[
                        "risk_level"
                    ],
                    "skill": risk[
                        "skill"
                    ],
                    "recommendation": (
                        "Identify adjacent-skilled "
                        "employees, external capacity, "
                        "or future hiring/training needs."
                    ),
                    "reason": (
                        f"Demand exceeds available "
                        f"skill supply by "
                        f"{risk['shortage_count']}."
                    ),
                }
            )

    # --------------------------------------------------------
    # Assignment instability recommendations
    # --------------------------------------------------------

    for risk in summary[
        "unstable_assignments"
    ]:

        recommendations.append(
            {
                "type": "Reallocation",
                "priority": risk[
                    "risk_level"
                ],
                "task_id": risk[
                    "task_id"
                ],
                "recommendation": (
                    "Generate replacement "
                    "candidate analysis and "
                    "run a simulation before "
                    "reassignment."
                ),
                "reason": "; ".join(
                    risk["reasons"]
                ),
            }
        )

    recommendations.sort(
        key=lambda item: (
            {
                "Critical": 0,
                "High": 1,
                "Medium": 2,
                "Low": 3,
            }.get(
                item["priority"],
                4,
            )
        ),
    )

    return recommendations
