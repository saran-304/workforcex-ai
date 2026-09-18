"""
WORKFORCEX AI
Deterministic Workforce Allocation Engine

This is the CORE decision engine.

It calculates employee suitability for a task using:

1. Exact skill match
2. Skill proficiency
3. Adjacent/related skills
4. Available capacity
5. Current workload
6. Task urgency
7. SLA exposure
8. Project priority
9. Task complexity
10. Location compatibility
11. Historical performance
12. Workload pressure

IMPORTANT:

This engine does NOT use an LLM to decide assignments.

The LLM can explain or orchestrate the result, but the actual
candidate calculation is deterministic and reproducible.

Therefore the system continues working even when Gemini/Grok
is unavailable.
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from models import (
    Employee,
    EmployeeSkill,
    Skill,
    Task,
    Assignment,
    SLA,
    TaskDependency,
)


# ============================================================
# CONFIGURATION
# ============================================================

# All weights add up to 1.0.

WEIGHTS = {
    "skill_match": 0.25,
    "proficiency": 0.15,
    "capacity": 0.15,
    "workload": 0.10,
    "sla": 0.10,
    "project_priority": 0.05,
    "complexity": 0.05,
    "location": 0.03,
    "performance": 0.07,
    "availability": 0.05,
}


# ============================================================
# PRIORITY VALUES
# ============================================================

PRIORITY_SCORE = {
    "Critical": 1.00,
    "High": 0.80,
    "Medium": 0.55,
    "Low": 0.30,
}


# ============================================================
# AVAILABILITY VALUES
# ============================================================

AVAILABILITY_SCORE = {
    "Available": 1.00,
    "Partial": 0.50,
    "Unavailable": 0.00,
}


# ============================================================
# SKILL RELATIONSHIPS
# ============================================================
#
# These relationships allow the system to identify
# "Adjacent Skill Match".
#
# Example:
#
# Python -> FastAPI
# Python -> Data Engineering
#
# This does NOT mean the adjacent skill is treated as an
# exact match.
#

RELATED_SKILLS = {
    "Python": {
        "FastAPI",
        "Data Engineering",
        "Machine Learning",
    },

    "FastAPI": {
        "Python",
        "Backend Engineering",
    },

    "JavaScript": {
        "TypeScript",
        "React",
    },

    "React": {
        "JavaScript",
        "TypeScript",
    },

    "TypeScript": {
        "JavaScript",
        "React",
    },

    "SQL": {
        "PostgreSQL",
        "Data Engineering",
    },

    "PostgreSQL": {
        "SQL",
        "Data Engineering",
    },

    "Machine Learning": {
        "Python",
        "Data Engineering",
    },

    "Data Engineering": {
        "Python",
        "SQL",
        "PostgreSQL",
        "Machine Learning",
    },

    "AWS": {
        "Docker",
        "Kubernetes",
        "CI/CD",
    },

    "Docker": {
        "AWS",
        "Kubernetes",
        "CI/CD",
    },

    "Kubernetes": {
        "Docker",
        "AWS",
        "CI/CD",
    },

    "CI/CD": {
        "Docker",
        "AWS",
        "Kubernetes",
    },

    "Cybersecurity": {
        "Network Security",
    },

    "Network Security": {
        "Cybersecurity",
    },

    "Testing": {
        "Automation Testing",
    },

    "Automation Testing": {
        "Testing",
    },

    "Embedded Systems": {
        "IoT",
    },

    "IoT": {
        "Embedded Systems",
    },
}


# ============================================================
# BASIC HELPERS
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    """
    Keep a number inside a fixed range.
    """

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def normalize_percentage(
    value: Optional[float],
) -> float:
    """
    Convert percentage 0-100 to 0-1.
    """

    if value is None:
        return 0.0

    return clamp(
        float(value) / 100.0
    )


def get_priority_score(
    priority: Optional[str],
) -> float:
    """
    Convert task/project priority to a normalized value.
    """

    return PRIORITY_SCORE.get(
        priority or "Low",
        0.30,
    )


# ============================================================
# EMPLOYEE SKILL LOOKUP
# ============================================================

def get_employee_skill_map(
    db: Session,
    employee_id: int,
) -> Dict[str, dict]:
    """
    Return all skills belonging to an employee.

    Result:

        {
            "Python": {
                "skill_id": 1,
                "proficiency": 5,
                "years_experience": 4.5,
                "is_primary": True
            }
        }
    """

    rows = (
        db.query(
            EmployeeSkill,
            Skill,
        )
        .join(
            Skill,
            EmployeeSkill.skill_id == Skill.id,
        )
        .filter(
            EmployeeSkill.employee_id
            == employee_id
        )
        .all()
    )

    result = {}

    for employee_skill, skill in rows:

        result[skill.name] = {
            "skill_id": skill.id,
            "proficiency": (
                employee_skill.proficiency
            ),
            "years_experience": (
                employee_skill.years_experience
            ),
            "is_primary": (
                employee_skill.is_primary
            ),
        }

    return result


# ============================================================
# SKILL MATCH
# ============================================================

def calculate_skill_match(
    db: Session,
    employee: Employee,
    task: Task,
) -> dict:
    """
    Calculate exact/adjacent/missing skill match.

    Returns:

        match_score
        match_type
        employee_skill
        required_skill
        proficiency
        explanation
    """

    required_skill = (
        db.query(Skill)
        .filter(
            Skill.id
            == task.required_skill_id
        )
        .first()
    )

    if not required_skill:

        return {
            "match_score": 0.0,
            "match_type": "Missing Skill",
            "employee_skill": None,
            "required_skill": None,
            "proficiency": 0,
            "explanation": (
                "Required skill does not exist."
            ),
        }

    employee_skills = get_employee_skill_map(
        db,
        employee.id,
    )

    required_name = required_skill.name

    # --------------------------------------------------------
    # EXACT MATCH
    # --------------------------------------------------------

    if required_name in employee_skills:

        skill_data = employee_skills[
            required_name
        ]

        proficiency = skill_data[
            "proficiency"
        ]

        proficiency_score = (
            proficiency / 5.0
        )

        return {
            "match_score": 1.0,
            "match_type": "Exact Match",
            "employee_skill": required_name,
            "required_skill": required_name,
            "proficiency": proficiency,
            "proficiency_score": (
                proficiency_score
            ),
            "explanation": (
                f"Employee has the required "
                f"{required_name} skill."
            ),
        }

    # --------------------------------------------------------
    # ADJACENT MATCH
    # --------------------------------------------------------

    adjacent_skills = RELATED_SKILLS.get(
        required_name,
        set(),
    )

    for employee_skill_name in employee_skills:

        if employee_skill_name in adjacent_skills:

            skill_data = employee_skills[
                employee_skill_name
            ]

            proficiency = skill_data[
                "proficiency"
            ]

            proficiency_score = (
                proficiency / 5.0
            )

            return {
                "match_score": 0.55,
                "match_type": "Adjacent Skill Match",
                "employee_skill": employee_skill_name,
                "required_skill": required_name,
                "proficiency": proficiency,
                "proficiency_score": (
                    proficiency_score
                ),
                "explanation": (
                    f"Employee has adjacent skill "
                    f"{employee_skill_name}, "
                    f"which is related to "
                    f"{required_name}."
                ),
            }

    # --------------------------------------------------------
    # MISSING
    # --------------------------------------------------------

    return {
        "match_score": 0.0,
        "match_type": "Missing Skill",
        "employee_skill": None,
        "required_skill": required_name,
        "proficiency": 0,
        "proficiency_score": 0.0,
        "explanation": (
            f"Employee does not have "
            f"{required_name} or a configured "
            f"adjacent skill."
        ),
    }


# ============================================================
# PROFICIENCY
# ============================================================

def calculate_proficiency_score(
    skill_result: dict,
    task: Task,
) -> float:
    """
    Calculate proficiency suitability.

    Required proficiency is normally 1-5.

    Exact skill:
        proficiency / 5

    Adjacent skill:
        reduced score

    Missing:
        zero
    """

    proficiency = skill_result.get(
        "proficiency",
        0,
    )

    required_proficiency = getattr(
        task,
        "required_proficiency",
        3,
    )

    if skill_result.get(
        "match_type"
    ) == "Missing Skill":
        return 0.0

    raw = proficiency / 5.0

    # Penalize candidates below required proficiency.
    if proficiency < required_proficiency:

        raw *= 0.70

    # Adjacent skill receives a transferability discount.
    if skill_result.get(
        "match_type"
    ) == "Adjacent Skill Match":

        raw *= 0.75

    return clamp(raw)


# ============================================================
# CAPACITY
# ============================================================

def calculate_capacity_score(
    employee: Employee,
    task: Task,
) -> float:
    """
    Estimate whether the employee has enough remaining
    capacity.

    Formula:

        remaining_capacity =
            capacity - current_workload

    Then compare against estimated task effort.
    """

    capacity = float(
        employee.capacity_percent or 0
    )

    workload = float(
        employee.current_workload_percent or 0
    )

    remaining = max(
        0.0,
        capacity - workload,
    )

    # Convert task hours into an approximate capacity load.
    estimated_hours = float(
        task.estimated_hours or 8
    )

    # Assume approximately 40 productive hours/week.
    estimated_load = clamp(
        estimated_hours / 40.0
    )

    if remaining <= 0:
        return 0.0

    available_ratio = (
        remaining / 100.0
    )

    # Candidates should have enough room for the task.
    if available_ratio >= estimated_load:
        return clamp(
            available_ratio
            + 0.15
        )

    return clamp(
        available_ratio * 0.60
    )


# ============================================================
# WORKLOAD
# ============================================================

def calculate_workload_score(
    employee: Employee,
) -> float:
    """
    Lower workload = higher suitability.

    0% workload  -> 1.0
    100% workload -> 0.0
    """

    workload = normalize_percentage(
        employee.current_workload_percent
    )

    return clamp(
        1.0 - workload
    )


# ============================================================
# AVAILABILITY
# ============================================================

def calculate_availability_score(
    employee: Employee,
) -> float:
    """
    Convert availability status into a score.
    """

    return AVAILABILITY_SCORE.get(
        employee.availability_status,
        0.0,
    )


# ============================================================
# SLA SCORE
# ============================================================

def calculate_sla_score(
    db: Session,
    task: Task,
) -> Tuple[float, dict]:
    """
    Calculate how urgent the SLA situation is.

    A task approaching or exceeding its SLA gets a higher
    allocation urgency score.
    """

    sla = (
        db.query(SLA)
        .filter(
            SLA.task_id == task.id
        )
        .first()
    )

    if not sla:

        return (
            0.50,
            {
                "status": "Unknown",
                "hours_remaining": None,
                "risk": "Unknown",
            },
        )

    now = datetime.utcnow()

    seconds_remaining = (
        sla.deadline - now
    ).total_seconds()

    hours_remaining = (
        seconds_remaining / 3600
    )

    if hours_remaining <= 0:

        return (
            1.00,
            {
                "status": "Breached",
                "hours_remaining": round(
                    hours_remaining,
                    2,
                ),
                "risk": "Critical",
            },
        )

    if hours_remaining <= 6:

        return (
            0.95,
            {
                "status": "At Risk",
                "hours_remaining": round(
                    hours_remaining,
                    2,
                ),
                "risk": "Critical",
            },
        )

    if hours_remaining <= 12:

        return (
            0.80,
            {
                "status": "At Risk",
                "hours_remaining": round(
                    hours_remaining,
                    2,
                ),
                "risk": "High",
            },
        )

    if hours_remaining <= 24:

        return (
            0.60,
            {
                "status": "Watch",
                "hours_remaining": round(
                    hours_remaining,
                    2,
                ),
                "risk": "Medium",
            },
        )

    return (
        0.25,
        {
            "status": "On Track",
            "hours_remaining": round(
                hours_remaining,
                2,
            ),
            "risk": "Low",
        },
    )


# ============================================================
# PROJECT PRIORITY
# ============================================================

def calculate_project_priority_score(
    db: Session,
    task: Task,
) -> float:
    """
    Use the task's project priority.
    """

    project = getattr(
        task,
        "project",
        None,
    )

    if project is None:
        return 0.50

    return get_priority_score(
        project.priority
    )


# ============================================================
# COMPLEXITY
# ============================================================

def calculate_complexity_score(
    employee: Employee,
    task: Task,
) -> float:
    """
    Higher complexity should generally go to stronger
    employees.

    Historical performance and seniority are used as simple
    deterministic indicators.
    """

    complexity = float(
        task.complexity or 5
    )

    performance = float(
        employee.historical_performance
        or 0.70
    )

    # Normalize complexity.
    complexity_factor = (
        complexity / 10.0
    )

    # Experienced employees receive a higher score
    # for complex tasks.
    if complexity >= 8:
        return clamp(
            performance
            * 1.10
        )

    if complexity >= 5:
        return clamp(
            performance
        )

    return clamp(
        0.70
        + performance * 0.30
    )


# ============================================================
# LOCATION
# ============================================================

def calculate_location_score(
    employee: Employee,
    task: Task,
) -> float:
    """
    Location compatibility.

    If the task has a location field, compare it.

    If not, use a neutral value because location should not
    unfairly influence remote-compatible tasks.
    """

    task_location = getattr(
        task,
        "location",
        None,
    )

    if not task_location:
        return 0.75

    if employee.location == task_location:
        return 1.00

    return 0.50


# ============================================================
# PERFORMANCE
# ============================================================

def calculate_performance_score(
    employee: Employee,
) -> float:
    """
    Normalize historical performance.

    Example:
        0.85 -> 0.85
    """

    return clamp(
        float(
            employee.historical_performance
            or 0.70
        )
    )


# ============================================================
# DEPENDENCY IMPACT
# ============================================================

def calculate_dependency_impact(
    db: Session,
    task: Task,
) -> dict:
    """
    Determine whether this task has important dependencies.

    A task with many downstream dependencies receives greater
    operational importance.
    """

    downstream = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.predecessor_task_id
            == task.id
        )
        .all()
    )

    upstream = (
        db.query(TaskDependency)
        .filter(
            TaskDependency.successor_task_id
            == task.id
        )
        .all()
    )

    downstream_count = len(
        downstream
    )

    upstream_count = len(
        upstream
    )

    total = (
        downstream_count
        + upstream_count
    )

    if total == 0:

        return {
            "score": 0.20,
            "downstream_dependencies": 0,
            "upstream_dependencies": 0,
            "criticality": "Low",
        }

    if downstream_count >= 3:

        criticality = "Critical"

        score = 1.00

    elif downstream_count >= 2:

        criticality = "High"

        score = 0.80

    elif total >= 2:

        criticality = "Medium"

        score = 0.60

    else:

        criticality = "Low"

        score = 0.40

    return {
        "score": score,
        "downstream_dependencies": (
            downstream_count
        ),
        "upstream_dependencies": (
            upstream_count
        ),
        "criticality": criticality,
    }


# ============================================================
# WORKLOAD PRESSURE
# ============================================================

def calculate_workload_pressure(
    employee: Employee,
) -> float:
    """
    Operational workload pressure.

    This is NOT a health or psychological metric.

    It measures operational utilization pressure only.
    """

    workload = normalize_percentage(
        employee.current_workload_percent
    )

    capacity = normalize_percentage(
        employee.capacity_percent
    )

    if capacity <= 0:
        return 1.0

    pressure = (
        workload / capacity
    )

    return clamp(
        pressure
    )


# ============================================================
# CANDIDATE SCORE
# ============================================================

def calculate_candidate_score(
    db: Session,
    employee: Employee,
    task: Task,
) -> dict:
    """
    Calculate complete deterministic candidate score.

    Returns all individual components so the decision can
    be explained transparently.
    """

    skill_result = calculate_skill_match(
        db,
        employee,
        task,
    )

    proficiency_score = (
        calculate_proficiency_score(
            skill_result,
            task,
        )
    )

    capacity_score = (
        calculate_capacity_score(
            employee,
            task,
        )
    )

    workload_score = (
        calculate_workload_score(
            employee
        )
    )

    availability_score = (
        calculate_availability_score(
            employee
        )
    )

    sla_score, sla_data = (
        calculate_sla_score(
            db,
            task,
        )
    )

    project_priority_score = (
        calculate_project_priority_score(
            db,
            task,
        )
    )

    complexity_score = (
        calculate_complexity_score(
            employee,
            task,
        )
    )

    location_score = (
        calculate_location_score(
            employee,
            task,
        )
    )

    performance_score = (
        calculate_performance_score(
            employee
        )
    )

    dependency_data = (
        calculate_dependency_impact(
            db,
            task,
        )
    )

    workload_pressure = (
        calculate_workload_pressure(
            employee
        )
    )

    # --------------------------------------------------------
    # FINAL WEIGHTED SCORE
    # --------------------------------------------------------

    weighted_score = (

        WEIGHTS["skill_match"]
        * skill_result["match_score"]

        +

        WEIGHTS["proficiency"]
        * proficiency_score

        +

        WEIGHTS["capacity"]
        * capacity_score

        +

        WEIGHTS["workload"]
        * workload_score

        +

        WEIGHTS["sla"]
        * sla_score

        +

        WEIGHTS["project_priority"]
        * project_priority_score

        +

        WEIGHTS["complexity"]
        * complexity_score

        +

        WEIGHTS["location"]
        * location_score

        +

        WEIGHTS["performance"]
        * performance_score

        +

        WEIGHTS["availability"]
        * availability_score
    )

    # --------------------------------------------------------
    # AVAILABILITY HARD BLOCK
    # --------------------------------------------------------

    if (
        employee.availability_status
        == "Unavailable"
    ):
        weighted_score = 0.0

    # --------------------------------------------------------
    # CRITICAL SKILL HARD BLOCK
    # --------------------------------------------------------

    if (
        task.required_proficiency
        and skill_result.get(
            "proficiency",
            0,
        ) < 1
        and skill_result.get(
            "match_type"
        ) == "Missing Skill"
    ):
        weighted_score *= 0.10

    # --------------------------------------------------------
    # WORKLOAD PENALTY
    # --------------------------------------------------------

    if workload_pressure >= 1.0:

        weighted_score *= 0.45

    elif workload_pressure >= 0.90:

        weighted_score *= 0.70

    elif workload_pressure >= 0.80:

        weighted_score *= 0.85

    final_score = round(
        clamp(
            weighted_score
        ) * 100,
        2,
    )

    # --------------------------------------------------------
    # RISK ESTIMATE
    # --------------------------------------------------------

    risk_before = estimate_employee_risk(
        employee
    )

    risk_after = estimate_risk_after_assignment(
        employee,
        task,
    )

    # --------------------------------------------------------
    # REASONS
    # --------------------------------------------------------

    reasons = []

    if skill_result["match_type"] == "Exact Match":
        reasons.append(
            f"Exact {skill_result['required_skill']} "
            "skill match."
        )

    elif (
        skill_result["match_type"]
        == "Adjacent Skill Match"
    ):
        reasons.append(
            f"Adjacent skill "
            f"{skill_result['employee_skill']} "
            f"can support "
            f"{skill_result['required_skill']}."
        )

    else:
        reasons.append(
            "Required skill is missing."
        )

    if proficiency_score >= 0.80:
        reasons.append(
            "Strong proficiency."
        )

    elif proficiency_score >= 0.60:
        reasons.append(
            "Moderate proficiency."
        )

    else:
        reasons.append(
            "Limited proficiency."
        )

    if capacity_score >= 0.75:
        reasons.append(
            "Good available capacity."
        )

    elif capacity_score >= 0.50:
        reasons.append(
            "Moderate available capacity."
        )

    else:
        reasons.append(
            "Limited remaining capacity."
        )

    if workload_score >= 0.70:
        reasons.append(
            "Current workload is manageable."
        )

    elif workload_score < 0.30:
        reasons.append(
            "Employee is heavily loaded."
        )

    if availability_score == 0:
        reasons.append(
            "Employee is currently unavailable."
        )

    if sla_data["risk"] in {
        "Critical",
        "High",
    }:
        reasons.append(
            "Task has elevated SLA urgency."
        )

    if dependency_data["criticality"] in {
        "Critical",
        "High",
    }:
        reasons.append(
            "Task has significant dependency impact."
        )

    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "employee_name": employee.name,

        "overall_score": final_score,

        "skill_match": round(
            skill_result["match_score"] * 100,
            2,
        ),

        "match_type": skill_result[
            "match_type"
        ],

        "employee_skill": skill_result.get(
            "employee_skill"
        ),

        "required_skill": skill_result.get(
            "required_skill"
        ),

        "proficiency": skill_result.get(
            "proficiency",
            0,
        ),

        "proficiency_score": round(
            proficiency_score * 100,
            2,
        ),

        "capacity_score": round(
            capacity_score * 100,
            2,
        ),

        "current_workload": (
            employee.current_workload_percent
        ),

        "available_capacity": max(
            0,
            (
                employee.capacity_percent
                or 0
            )
            - (
                employee.current_workload_percent
                or 0
            ),
        ),

        "availability": (
            employee.availability_status
        ),

        "availability_score": round(
            availability_score * 100,
            2,
        ),

        "sla_score": round(
            sla_score * 100,
            2,
        ),

        "sla": sla_data,

        "project_priority_score": round(
            project_priority_score * 100,
            2,
        ),

        "complexity_score": round(
            complexity_score * 100,
            2,
        ),

        "location_score": round(
            location_score * 100,
            2,
        ),

        "performance_score": round(
            performance_score * 100,
            2,
        ),

        "historical_performance": (
            employee.historical_performance
        ),

        "workload_pressure": round(
            workload_pressure * 100,
            2,
        ),

        "dependency_impact": dependency_data,

        "risk_before": risk_before,

        "risk_after": risk_after,

        "risk_change": round(
            risk_after - risk_before,
            2,
        ),

        "reasons": reasons,

        "explanation": (
            "; ".join(reasons)
        ),
    }


# ============================================================
# RISK ESTIMATION
# ============================================================

def estimate_employee_risk(
    employee: Employee,
) -> float:
    """
    Estimate operational assignment risk before assigning
    another task.

    0 = low risk
    100 = high risk
    """

    workload = normalize_percentage(
        employee.current_workload_percent
    )

    capacity = normalize_percentage(
        employee.capacity_percent
    )

    performance = float(
        employee.historical_performance
        or 0.70
    )

    risk = (
        workload * 60
        +

        max(
            0,
            workload - capacity,
        )
        * 25

        +

        (1 - performance)
        * 15
    )

    if (
        employee.availability_status
        == "Unavailable"
    ):
        risk += 50

    elif (
        employee.availability_status
        == "Partial"
    ):
        risk += 15

    return round(
        clamp(
            risk / 100
        ) * 100,
        2,
    )


def estimate_risk_after_assignment(
    employee: Employee,
    task: Task,
) -> float:
    """
    Estimate operational risk after assigning the task.

    This is a deterministic estimate, not a machine-learning
    prediction.
    """

    base_risk = estimate_employee_risk(
        employee
    )

    estimated_hours = float(
        task.estimated_hours or 8
    )

    workload_increase = (
        estimated_hours / 40.0
    ) * 100

    projected_workload = (
        employee.current_workload_percent
        or 0
    ) + workload_increase

    projected_capacity = (
        employee.capacity_percent
        or 0
    )

    overload = max(
        0,
        projected_workload
        - projected_capacity,
    )

    projected_risk = (
        base_risk
        +

        workload_increase * 0.40

        +

        overload * 0.60
    )

    if task.priority == "Critical":
        projected_risk += 5

    elif task.priority == "High":
        projected_risk += 2

    return round(
        clamp(
            projected_risk / 100
        ) * 100,
        2,
    )


# ============================================================
# FIND CANDIDATES
# ============================================================

def find_candidates(
    db: Session,
    task: Task,
    limit: int = 10,
    include_unavailable: bool = False,
) -> List[dict]:
    """
    Calculate and rank all employees for a task.

    Returns highest-scoring candidates first.
    """

    query = (
        db.query(Employee)
        .filter(
            Employee.organization_id
            == task.organization_id,
            Employee.is_active.is_(True),
        )
    )

    if not include_unavailable:

        query = query.filter(
            Employee.availability_status
            != "Unavailable"
        )

    employees = query.all()

    results = []

    for employee in employees:

        result = calculate_candidate_score(
            db,
            employee,
            task,
        )

        results.append(
            result
        )

    results.sort(
        key=lambda item: item[
            "overall_score"
        ],
        reverse=True,
    )

    return results[:limit]


# ============================================================
# ALLOCATION DECISION
# ============================================================

def calculate_allocation(
    db: Session,
    task_id: int,
    limit: int = 10,
) -> dict:
    """
    Main allocation API/service function.

    Does NOT modify database state.

    It only calculates the recommendation.
    """

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:
        raise ValueError(
            f"Task {task_id} not found."
        )

    candidates = find_candidates(
        db,
        task,
        limit=limit,
    )

    if not candidates:

        return {
            "success": False,
            "task_id": task.id,
            "message": (
                "No suitable candidates found."
            ),
            "candidates": [],
        }

    selected = candidates[0]

    alternatives = candidates[1:]

    # --------------------------------------------------------
    # REJECTION REASONS
    # --------------------------------------------------------

    for candidate in alternatives:

        rejection_reasons = []

        if candidate["skill_match"] < 50:
            rejection_reasons.append(
                "Lower skill match."
            )

        if candidate[
            "available_capacity"
        ] < 10:
            rejection_reasons.append(
                "Limited available capacity."
            )

        if candidate[
            "workload_pressure"
        ] >= 90:
            rejection_reasons.append(
                "High workload pressure."
            )

        if candidate[
            "availability"
        ] == "Partial":
            rejection_reasons.append(
                "Partial availability."
            )

        if not rejection_reasons:
            rejection_reasons.append(
                "Lower overall deterministic score."
            )

        candidate[
            "rejection_reasons"
        ] = rejection_reasons

    explanation = (
        f"{selected['employee_name']} "
        f"was selected with a score of "
        f"{selected['overall_score']}%. "
        f"{selected['explanation']}"
    )

    return {
        "success": True,

        "task_id": task.id,

        "task_title": task.title,

        "selected_candidate": selected,

        "alternatives": alternatives,

        "candidate_count": len(
            candidates
        ),

        "algorithm": (
            "Deterministic weighted "
            "workforce allocation"
        ),

        "weights": WEIGHTS,

        "explanation": explanation,
    }


# ============================================================
# RECOMMENDATION WITHOUT EXECUTION
# ============================================================

def recommend_assignment(
    db: Session,
    task_id: int,
) -> dict:
    """
    Public helper used by API/Copilot.

    IMPORTANT:

    This function does not create an assignment.

    It only recommends one.
    """

    result = calculate_allocation(
        db,
        task_id,
        limit=10,
    )

    return result


# ============================================================
# REALLOCATION ANALYSIS
# ============================================================

def calculate_reallocation_options(
    db: Session,
    task_id: int,
    current_employee_id: Optional[int] = None,
    limit: int = 10,
) -> dict:
    """
    Find replacement candidates for a task.

    Used when:

    - employee becomes unavailable
    - workload changes
    - project priority changes
    - deadline changes
    """

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id
        )
        .first()
    )

    if not task:
        raise ValueError(
            f"Task {task_id} not found."
        )

    candidates = find_candidates(
        db,
        task,
        limit=limit,
    )

    if current_employee_id is not None:

        candidates = [
            candidate
            for candidate in candidates
            if candidate["employee_id"]
            != current_employee_id
        ]

    selected = (
        candidates[0]
        if candidates
        else None
    )

    return {
        "task_id": task.id,
        "current_employee_id": (
            current_employee_id
        ),
        "replacement_candidate": selected,
        "alternatives": (
            candidates[1:]
            if len(candidates) > 1
            else []
        ),
        "candidate_count": len(
            candidates
        ),
    }


# ============================================================
# BATCH ALLOCATION
# ============================================================

def allocate_unassigned_tasks(
    db: Session,
    organization_id: int,
    limit_per_task: int = 5,
) -> List[dict]:
    """
    Find currently unassigned tasks and calculate candidate
    recommendations.

    Does not modify assignments.
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

        existing_assignment = (
            db.query(Assignment)
            .filter(
                Assignment.task_id
                == task.id,
                Assignment.status
                == "Active",
            )
            .first()
        )

        if existing_assignment:
            continue

        recommendation = (
            calculate_allocation(
                db,
                task.id,
                limit=limit_per_task,
            )
        )

        results.append(
            recommendation
        )

    return results


# ============================================================
# TEAM CAPACITY SUMMARY
# ============================================================

def calculate_team_capacity_summary(
    db: Session,
    organization_id: int,
) -> List[dict]:
    """
    Produce a deterministic team-level workforce capacity
    summary.
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

        if team_id not in teams:

            teams[team_id] = {
                "team_id": team_id,
                "employee_count": 0,
                "total_capacity": 0.0,
                "total_workload": 0.0,
                "available_employees": 0,
                "unavailable_employees": 0,
            }

        summary = teams[team_id]

        summary[
            "employee_count"
        ] += 1

        summary[
            "total_capacity"
        ] += float(
            employee.capacity_percent
            or 0
        )

        summary[
            "total_workload"
        ] += float(
            employee.current_workload_percent
            or 0
        )

        if (
            employee.availability_status
            == "Available"
        ):

            summary[
                "available_employees"
            ] += 1

        elif (
            employee.availability_status
            == "Unavailable"
        ):

            summary[
                "unavailable_employees"
            ] += 1

    results = []

    for team_id, summary in teams.items():

        capacity = summary[
            "total_capacity"
        ]

        workload = summary[
            "total_workload"
        ]

        if capacity > 0:

            utilization = (
                workload / capacity
            ) * 100

        else:

            utilization = 100

        summary[
            "utilization_percent"
        ] = round(
            utilization,
            2,
        )

        summary[
            "remaining_capacity"
        ] = round(
            max(
                0,
                capacity - workload,
            ),
            2,
        )

        if utilization >= 95:

            summary[
                "pressure"
            ] = "Critical"

        elif utilization >= 85:

            summary[
                "pressure"
            ] = "High"

        elif utilization >= 70:

            summary[
                "pressure"
            ] = "Medium"

        else:

            summary[
                "pressure"
            ] = "Low"

        results.append(
            summary
        )

    results.sort(
        key=lambda item: item[
            "utilization_percent"
        ],
        reverse=True,
    )

    return results
