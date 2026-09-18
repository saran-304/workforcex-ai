"""
WORKFORCEX AI
What-If Scenario & Workforce Simulation Engine

This module performs NON-DESTRUCTIVE simulations.

IMPORTANT:
    Simulation never modifies the production database.

It calculates:

    Baseline
        ↓
    Scenario
        ↓
    Candidate Reallocation
        ↓
    Capacity Impact
        ↓
    SLA Impact
        ↓
    Risk Impact
        ↓
    Strategy Comparison

Supported scenarios:

1. Employee unavailable
2. Multiple employees unavailable
3. Urgent task arrival
4. Employee capacity reduction
5. Deadline acceleration
6. Project priority change
7. Workload increase
8. Critical skill shortage

Strategies:

A. Keep current assignments
B. Reallocate suitable employees
C. Reallocate + delay lower-priority work

The deterministic allocation engine is used for candidate selection.

The AI layer can later explain these simulation results,
but it does NOT perform the calculations itself.
"""

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from models import (
    Employee,
    Task,
    Assignment,
    SLA,
    Project,
    EmployeeSkill,
    Skill,
)

from risk_engine import (
    calculate_employee_workload_risk,
    calculate_sla_risk,
    calculate_task_assignment_risk,
    calculate_dependency_risk,
)

try:
    from allocation_engine import (
        find_candidates,
        calculate_allocation,
    )
except ImportError:
    find_candidates = None
    calculate_allocation = None


# ============================================================
# CONSTANTS
# ============================================================

STRATEGY_KEEP_CURRENT = "keep_current"
STRATEGY_REALLOCATE = "reallocate"
STRATEGY_REALLOCATE_DELAY = "reallocate_and_delay"

SUPPORTED_SCENARIOS = {
    "employee_unavailable",
    "multiple_employees_unavailable",
    "urgent_task",
    "capacity_reduction",
    "deadline_acceleration",
    "priority_change",
    "workload_increase",
    "skill_shortage",
}


# ============================================================
# GENERAL HELPERS
# ============================================================

def clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 100.0,
) -> float:
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


def safe_float(
    value,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


# ============================================================
# WORKFORCE SNAPSHOT
# ============================================================

def create_workforce_snapshot(
    db: Session,
    organization_id: int,
) -> dict:
    """
    Capture the current workforce state.

    This is read-only.
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

    tasks = (
        db.query(Task)
        .filter(
            Task.organization_id
            == organization_id,
            Task.status != "Completed",
        )
        .all()
    )

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

    employee_data = {}

    for employee in employees:

        employee_data[
            employee.id
        ] = {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "name": employee.name,
            "team_id": employee.team_id,
            "capacity_percent": safe_float(
                employee.capacity_percent
            ),
            "workload_percent": safe_float(
                employee.current_workload_percent
            ),
            "availability_status": (
                employee.availability_status
            ),
            "location": employee.location,
            "historical_performance": safe_float(
                employee.historical_performance,
                0.70,
            ),
        }

    task_data = {}

    for task in tasks:

        task_data[
            task.id
        ] = {
            "id": task.id,
            "title": task.title,
            "project_id": task.project_id,
            "priority": task.priority,
            "status": task.status,
            "estimated_hours": safe_float(
                task.estimated_hours,
                1,
            ),
            "required_skill_id": (
                task.required_skill_id
            ),
        }

    assignment_data = {}

    for assignment in assignments:

        assignment_data[
            assignment.id
        ] = {
            "id": assignment.id,
            "employee_id": assignment.employee_id,
            "task_id": assignment.task_id,
            "status": assignment.status,
        }

    return {
        "organization_id": organization_id,
        "generated_at": datetime.utcnow().isoformat(),
        "employees": employee_data,
        "tasks": task_data,
        "assignments": assignment_data,
    }


# ============================================================
# SNAPSHOT STATISTICS
# ============================================================

def calculate_snapshot_metrics(
    snapshot: dict,
) -> dict:
    """
    Calculate aggregate workforce metrics from a snapshot.
    """

    employees = snapshot[
        "employees"
    ]

    tasks = snapshot[
        "tasks"
    ]

    assignments = snapshot[
        "assignments"
    ]

    total_capacity = sum(
        safe_float(
            employee[
                "capacity_percent"
            ]
        )
        for employee in employees.values()
    )

    total_workload = sum(
        safe_float(
            employee[
                "workload_percent"
            ]
        )
        for employee in employees.values()
    )

    available_employees = sum(
        1
        for employee in employees.values()
        if employee[
            "availability_status"
        ]
        != "Unavailable"
    )

    unavailable_employees = sum(
        1
        for employee in employees.values()
        if employee[
            "availability_status"
        ]
        == "Unavailable"
    )

    utilization = (
        (
            total_workload
            / total_capacity
        )
        * 100
        if total_capacity > 0
        else 0
    )

    return {
        "employee_count": len(
            employees
        ),
        "active_task_count": len(
            tasks
        ),
        "active_assignment_count": len(
            assignments
        ),
        "total_capacity": round(
            total_capacity,
            2,
        ),
        "total_workload": round(
            total_workload,
            2,
        ),
        "remaining_capacity": round(
            max(
                0,
                total_capacity
                - total_workload,
            ),
            2,
        ),
        "utilization_percent": round(
            utilization,
            2,
        ),
        "available_employees": (
            available_employees
        ),
        "unavailable_employees": (
            unavailable_employees
        ),
    }


# ============================================================
# BASELINE RISK
# ============================================================

def calculate_snapshot_risk(
    db: Session,
    snapshot: dict,
) -> dict:
    """
    Estimate operational risk from the current snapshot.

    The actual database remains untouched.
    """

    workload_scores = []

    for employee in snapshot[
        "employees"
    ].values():

        workload = safe_float(
            employee[
                "workload_percent"
            ]
        )

        capacity = safe_float(
            employee[
                "capacity_percent"
            ]
        )

        pressure = (
            workload / capacity * 100
            if capacity > 0
            else 100
        )

        score = min(
            100,
            pressure,
        )

        if (
            employee[
                "availability_status"
            ]
            == "Unavailable"
        ):
            score = max(
                score,
                90,
            )

        workload_scores.append(
            score
        )

    if workload_scores:

        workload_risk = (
            sum(workload_scores)
            / len(workload_scores)
        )

        max_workload_risk = max(
            workload_scores
        )

        workload_risk = (
            workload_risk * 0.65
            +
            max_workload_risk * 0.35
        )

    else:

        workload_risk = 0

    return {
        "workforce_risk_score": round(
            clamp(
                workload_risk
            ),
            2,
        ),
        "workforce_risk_level": (
            "Critical"
            if workload_risk >= 80
            else "High"
            if workload_risk >= 60
            else "Medium"
            if workload_risk >= 35
            else "Low"
        ),
    }


# ============================================================
# APPLY SCENARIO TO COPY
# ============================================================

def apply_scenario(
    snapshot: dict,
    scenario_type: str,
    parameters: Optional[dict] = None,
) -> dict:
    """
    Apply scenario changes to an in-memory copy.

    NEVER changes production state.
    """

    parameters = parameters or {}

    if scenario_type not in SUPPORTED_SCENARIOS:

        raise ValueError(
            f"Unsupported scenario: {scenario_type}"
        )

    scenario = deepcopy(
        snapshot
    )

    # --------------------------------------------------------
    # Employee unavailable
    # --------------------------------------------------------

    if scenario_type == "employee_unavailable":

        employee_id = parameters.get(
            "employee_id"
        )

        if employee_id not in scenario[
            "employees"
        ]:

            raise ValueError(
                "Employee not found in workforce."
            )

        scenario[
            "employees"
        ][
            employee_id
        ][
            "availability_status"
        ] = "Unavailable"

    # --------------------------------------------------------
    # Multiple employees unavailable
    # --------------------------------------------------------

    elif (
        scenario_type
        == "multiple_employees_unavailable"
    ):

        employee_ids = parameters.get(
            "employee_ids",
            [],
        )

        for employee_id in employee_ids:

            if employee_id in scenario[
                "employees"
            ]:

                scenario[
                    "employees"
                ][
                    employee_id
                ][
                    "availability_status"
                ] = "Unavailable"

    # --------------------------------------------------------
    # Urgent task
    # --------------------------------------------------------

    elif scenario_type == "urgent_task":

        task_id = parameters.get(
            "task_id"
        )

        if task_id:

            if task_id not in scenario[
                "tasks"
            ]:

                raise ValueError(
                    "Task not found."
                )

            scenario[
                "tasks"
            ][
                task_id
            ][
                "priority"
            ] = "Critical"

        else:

            new_task_id = (
                parameters.get(
                    "new_task_id",
                    "SIMULATED-URGENT",
                )
            )

            scenario[
                "tasks"
            ][
                new_task_id
            ] = {
                "id": new_task_id,
                "title": parameters.get(
                    "title",
                    "Simulated Urgent Task",
                ),
                "project_id": parameters.get(
                    "project_id"
                ),
                "priority": "Critical",
                "status": "Open",
                "estimated_hours": safe_float(
                    parameters.get(
                        "estimated_hours",
                        8,
                    ),
                    8,
                ),
                "required_skill_id": parameters.get(
                    "required_skill_id"
                ),
            }

    # --------------------------------------------------------
    # Capacity reduction
    # --------------------------------------------------------

    elif scenario_type == "capacity_reduction":

        employee_id = parameters.get(
            "employee_id"
        )

        reduction = safe_float(
            parameters.get(
                "reduction_percent",
                20,
            )
        )

        if employee_id not in scenario[
            "employees"
        ]:

            raise ValueError(
                "Employee not found."
            )

        employee = scenario[
            "employees"
        ][
            employee_id
        ]

        employee[
            "capacity_percent"
        ] = max(
            0,
            employee[
                "capacity_percent"
            ]
            - reduction,
        )

    # --------------------------------------------------------
    # Deadline acceleration
    # --------------------------------------------------------

    elif (
        scenario_type
        == "deadline_acceleration"
    ):

        task_ids = parameters.get(
            "task_ids",
            [],
        )

        hours_earlier = safe_float(
            parameters.get(
                "hours_earlier",
                24,
            ),
            24,
        )

        scenario[
            "deadline_change"
        ] = {
            "task_ids": task_ids,
            "hours_earlier": hours_earlier,
        }

    # --------------------------------------------------------
    # Priority change
    # --------------------------------------------------------

    elif scenario_type == "priority_change":

        task_id = parameters.get(
            "task_id"
        )

        new_priority = parameters.get(
            "new_priority",
            "High",
        )

        if task_id not in scenario[
            "tasks"
        ]:

            raise ValueError(
                "Task not found."
            )

        scenario[
            "tasks"
        ][
            task_id
        ][
            "priority"
        ] = new_priority

    # --------------------------------------------------------
    # Workload increase
    # --------------------------------------------------------

    elif scenario_type == "workload_increase":

        increase = safe_float(
            parameters.get(
                "increase_percent",
                20,
            ),
            20,
        )

        employee_ids = parameters.get(
            "employee_ids"
        )

        if employee_ids is None:

            employee_ids = list(
                scenario[
                    "employees"
                ].keys()
            )

        for employee_id in employee_ids:

            if employee_id not in scenario[
                "employees"
            ]:
                continue

            employee = scenario[
                "employees"
            ][
                employee_id
            ]

            employee[
                "workload_percent"
            ] = min(
                150,
                employee[
                    "workload_percent"
                ]
                + increase,
            )

    # --------------------------------------------------------
    # Skill shortage
    # --------------------------------------------------------

    elif scenario_type == "skill_shortage":

        employee_ids = parameters.get(
            "employee_ids",
            [],
        )

        for employee_id in employee_ids:

            if employee_id in scenario[
                "employees"
            ]:

                scenario[
                    "employees"
                ][
                    employee_id
                ][
                    "availability_status"
                ] = "Unavailable"

        scenario[
            "skill_shortage"
        ] = {
            "skill_id": parameters.get(
                "skill_id"
            ),
            "employee_ids": employee_ids,
        }

    return scenario


# ============================================================
# AFFECTED RESOURCES
# ============================================================

def find_affected_resources(
    baseline: dict,
    scenario: dict,
) -> dict:
    """
    Identify what changed between baseline and scenario.
    """

    affected_employees = []

    baseline_employees = baseline[
        "employees"
    ]

    scenario_employees = scenario[
        "employees"
    ]

    for employee_id in scenario_employees:

        if employee_id not in baseline_employees:
            continue

        before = baseline_employees[
            employee_id
        ]

        after = scenario_employees[
            employee_id
        ]

        if (
            before[
                "availability_status"
            ]
            != after[
                "availability_status"
            ]
            or
            before[
                "capacity_percent"
            ]
            != after[
                "capacity_percent"
            ]
            or
            before[
                "workload_percent"
            ]
            != after[
                "workload_percent"
            ]
        ):

            affected_employees.append(
                {
                    "employee_id": employee_id,
                    "employee_name": after[
                        "name"
                    ],
                    "before": before,
                    "after": after,
                }
            )

    affected_tasks = []

    baseline_tasks = baseline[
        "tasks"
    ]

    scenario_tasks = scenario[
        "tasks"
    ]

    for task_id in scenario_tasks:

        if task_id not in baseline_tasks:

            affected_tasks.append(
                {
                    "task_id": task_id,
                    "change": "Added",
                    "after": scenario_tasks[
                        task_id
                    ],
                }
            )

            continue

        before = baseline_tasks[
            task_id
        ]

        after = scenario_tasks[
            task_id
        ]

        if (
            before["priority"]
            != after["priority"]
        ):

            affected_tasks.append(
                {
                    "task_id": task_id,
                    "change": "Priority Changed",
                    "before": before,
                    "after": after,
                }
            )

    return {
        "employees": affected_employees,
        "tasks": affected_tasks,
    }


# ============================================================
# CURRENT ASSIGNMENTS AFFECTED
# ============================================================

def find_affected_assignments(
    baseline: dict,
    scenario: dict,
) -> List[dict]:
    """
    Find assignments associated with changed/unavailable
    employees.
    """

    changed_employee_ids = {
        item["employee_id"]
        for item in find_affected_resources(
            baseline,
            scenario,
        )[
            "employees"
        ]
    }

    results = []

    for assignment in baseline[
        "assignments"
    ].values():

        employee_id = assignment[
            "employee_id"
        ]

        if employee_id in changed_employee_ids:

            task_id = assignment[
                "task_id"
            ]

            task = baseline[
                "tasks"
            ].get(
                task_id
            )

            results.append(
                {
                    "assignment_id": assignment[
                        "id"
                    ],
                    "employee_id": employee_id,
                    "task_id": task_id,
                    "task_title": (
                        task["title"]
                        if task
                        else None
                    ),
                    "task_priority": (
                        task["priority"]
                        if task
                        else None
                    ),
                }
            )

    return results


# ============================================================
# CANDIDATE SEARCH
# ============================================================

def find_simulation_candidates(
    db: Session,
    organization_id: int,
    task_id: int,
    excluded_employee_ids: Optional[List[int]] = None,
) -> List[dict]:
    """
    Use the deterministic allocation engine to find
    replacement candidates.

    If the allocation engine is unavailable, use a safe
    fallback capacity-based candidate calculation.
    """

    excluded_employee_ids = (
        excluded_employee_ids
        or []
    )

    # --------------------------------------------------------
    # Preferred real allocation engine
    # --------------------------------------------------------

    if find_candidates is not None:

        try:

            result = find_candidates(
                db=db,
                organization_id=organization_id,
                task_id=task_id,
            )

            if isinstance(
                result,
                list,
            ):

                return [
                    item
                    for item in result
                    if item.get(
                        "employee_id"
                    )
                    not in excluded_employee_ids
                ]

        except TypeError:
            pass

        except Exception:
            pass

    # --------------------------------------------------------
    # Fallback deterministic calculation
    # --------------------------------------------------------

    task = (
        db.query(Task)
        .filter(
            Task.id == task_id,
            Task.organization_id
            == organization_id,
        )
        .first()
    )

    if not task:
        return []

    employees = (
        db.query(Employee)
        .filter(
            Employee.organization_id
            == organization_id,
            Employee.is_active.is_(True),
        )
        .all()
    )

    candidates = []

    for employee in employees:

        if employee.id in excluded_employee_ids:
            continue

        if (
            employee.availability_status
            == "Unavailable"
        ):
            continue

        capacity = safe_float(
            employee.capacity_percent
        )

        workload = safe_float(
            employee.current_workload_percent
        )

        remaining = max(
            0,
            capacity - workload,
        )

        if remaining <= 0:
            continue

        score = min(
            100,
            remaining,
        )

        if (
            employee.availability_status
            == "Partial"
        ):
            score -= 10

        candidates.append(
            {
                "employee_id": employee.id,
                "employee_name": employee.name,
                "score": round(
                    max(
                        0,
                        score,
                    ),
                    2,
                ),
                "remaining_capacity": round(
                    remaining,
                    2,
                ),
                "reason": (
                    "Available capacity "
                    "supports potential reassignment."
                ),
            }
        )

    candidates.sort(
        key=lambda item: item[
            "score"
        ],
        reverse=True,
    )

    return candidates


# ============================================================
# STRATEGY A — KEEP CURRENT
# ============================================================

def simulate_keep_current(
    baseline: dict,
    scenario: dict,
) -> dict:
    """
    Strategy A:

    Do not change assignments.

    This establishes the impact of doing nothing.
    """

    affected = find_affected_resources(
        baseline,
        scenario,
    )

    employees = scenario[
        "employees"
    ]

    task_assignments = scenario[
        "assignments"
    ]

    blocked_tasks = []

    for assignment in task_assignments.values():

        employee = employees.get(
            assignment[
                "employee_id"
            ]
        )

        if not employee:
            continue

        if (
            employee[
                "availability_status"
            ]
            == "Unavailable"
        ):

            blocked_tasks.append(
                {
                    "task_id": assignment[
                        "task_id"
                    ],
                    "employee_id": assignment[
                        "employee_id"
                    ],
                    "reason": (
                        "Assigned employee "
                        "is unavailable."
                    ),
                }
            )

    metrics = calculate_snapshot_metrics(
        scenario
    )

    base_metrics = calculate_snapshot_metrics(
        baseline
    )

    blocked_count = len(
        blocked_tasks
    )

    risk = (
        calculate_snapshot_risk(
            None,
            scenario,
        )[
            "workforce_risk_score"
        ]
    )

    risk += blocked_count * 8

    risk = clamp(
        risk
    )

    return {
        "strategy": STRATEGY_KEEP_CURRENT,
        "name": "Keep Current Assignments",
        "description": (
            "Maintain the current workforce "
            "allocation without intervention."
        ),
        "metrics": metrics,
        "baseline_metrics": base_metrics,
        "risk_score": round(
            risk,
            2,
        ),
        "risk_level": (
            "Critical"
            if risk >= 80
            else "High"
            if risk >= 60
            else "Medium"
            if risk >= 35
            else "Low"
        ),
        "blocked_tasks": blocked_tasks,
        "affected_resources": affected,
        "reassignments": [],
        "delayed_tasks": [],
        "sla_impact": (
            "Potential SLA exposure on "
            f"{blocked_count} affected task(s)."
            if blocked_count
            else "No immediate assignment blockage detected."
        ),
    }


# ============================================================
# STRATEGY B — REALLOCATE
# ============================================================

def simulate_reallocation(
    db: Session,
    organization_id: int,
    baseline: dict,
    scenario: dict,
) -> dict:
    """
    Strategy B:

    Reallocate affected tasks to available candidates.

    IMPORTANT:
        This only changes the in-memory simulation.
        Production assignments remain untouched.
    """

    simulated = deepcopy(
        scenario
    )

    affected_assignments = (
        find_affected_assignments(
            baseline,
            scenario,
        )
    )

    reassignments = []

    blocked_tasks = []

    for affected in affected_assignments:

        task_id = affected[
            "task_id"
        ]

        old_employee_id = affected[
            "employee_id"
        ]

        candidates = find_simulation_candidates(
            db,
            organization_id,
            task_id,
            excluded_employee_ids=[
                old_employee_id
            ],
        )

        if not candidates:

            blocked_tasks.append(
                {
                    "task_id": task_id,
                    "task_title": affected[
                        "task_title"
                    ],
                    "reason": (
                        "No suitable available "
                        "replacement candidate found."
                    ),
                }
            )

            continue

        selected = candidates[
            0
        ]

        new_employee_id = selected[
            "employee_id"
        ]

        assignment_id = affected[
            "assignment_id"
        ]

        if assignment_id in simulated[
            "assignments"
        ]:

            simulated[
                "assignments"
            ][
                assignment_id
            ][
                "employee_id"
            ] = new_employee_id

        # ----------------------------------------------------
        # Simulated workload transfer.
        # ----------------------------------------------------

        task = simulated[
            "tasks"
        ].get(
            task_id
        )

        if task:

            task_hours = safe_float(
                task[
                    "estimated_hours"
                ],
                1,
            )

            # Small normalized workload impact.
            workload_impact = min(
                20,
                task_hours * 2,
            )

            old_employee = simulated[
                "employees"
            ].get(
                old_employee_id
            )

            new_employee = simulated[
                "employees"
            ].get(
                new_employee_id
            )

            if old_employee:

                old_employee[
                    "workload_percent"
                ] = max(
                    0,
                    old_employee[
                        "workload_percent"
                    ]
                    - workload_impact,
                )

            if new_employee:

                new_employee[
                    "workload_percent"
                ] = min(
                    150,
                    new_employee[
                        "workload_percent"
                    ]
                    + workload_impact,
                )

        reassignments.append(
            {
                "task_id": task_id,
                "task_title": affected[
                    "task_title"
                ],
                "from_employee_id": old_employee_id,
                "to_employee_id": new_employee_id,
                "to_employee_name": selected.get(
                    "employee_name"
                ),
                "candidate_score": selected.get(
                    "score",
                    selected.get(
                        "overall_score"
                    ),
                ),
                "reason": selected.get(
                    "reason",
                    "Highest available deterministic candidate.",
                ),
            }
        )

    metrics = calculate_snapshot_metrics(
        simulated
    )

    risk = calculate_snapshot_risk(
        None,
        simulated,
    )[
        "workforce_risk_score"
    ]

    # Penalty for tasks that could not be reassigned.
    risk += len(
        blocked_tasks
    ) * 8

    risk = clamp(
        risk
    )

    return {
        "strategy": STRATEGY_REALLOCATE,
        "name": "Reallocate Suitable Employees",
        "description": (
            "Move affected work to available "
            "employees using deterministic "
            "candidate scoring."
        ),
        "metrics": metrics,
        "risk_score": round(
            risk,
            2,
        ),
        "risk_level": (
            "Critical"
            if risk >= 80
            else "High"
            if risk >= 60
            else "Medium"
            if risk >= 35
            else "Low"
        ),
        "reassignments": reassignments,
        "blocked_tasks": blocked_tasks,
        "delayed_tasks": [],
        "affected_resources": find_affected_resources(
            baseline,
            simulated,
        ),
        "sla_impact": (
            f"{len(blocked_tasks)} task(s) "
            "remain without a replacement."
            if blocked_tasks
            else (
                "Affected assignments have "
                "available replacement candidates."
            )
        ),
        "simulated_state": simulated,
    }


# ============================================================
# STRATEGY C — REALLOCATE + DELAY
# ============================================================

def simulate_reallocation_and_delay(
    db: Session,
    organization_id: int,
    baseline: dict,
    scenario: dict,
) -> dict:
    """
    Strategy C:

    First attempt reallocation.

    If capacity is insufficient, lower-priority work
    is marked as delayed in the simulation.

    This does NOT modify production data.
    """

    result = simulate_reallocation(
        db,
        organization_id,
        baseline,
        scenario,
    )

    simulated = deepcopy(
        result.get(
            "simulated_state",
            scenario,
        )
    )

    blocked_tasks = result[
        "blocked_tasks"
    ]

    delayed_tasks = []

    # --------------------------------------------------------
    # Find low-priority tasks that can be delayed.
    # --------------------------------------------------------

    candidate_tasks = []

    for task_id, task in simulated[
        "tasks"
    ].items():

        if task["priority"] in {
            "Low",
            "Medium",
        }:

            candidate_tasks.append(
                task
            )

    candidate_tasks.sort(
        key=lambda task: (
            priority_value(
                task["priority"]
            ),
            -safe_float(
                task[
                    "estimated_hours"
                ],
                1,
            ),
        )
    )

    # --------------------------------------------------------
    # Delay only as many tasks as needed.
    # --------------------------------------------------------

    delay_count = min(
        len(
            blocked_tasks
        ),
        len(
            candidate_tasks
        ),
    )

    for index in range(
        delay_count
    ):

        task = candidate_tasks[
            index
        ]

        task[
            "status"
        ] = "Delayed"

        delayed_tasks.append(
            {
                "task_id": task[
                    "id"
                ],
                "task_title": task[
                    "title"
                ],
                "priority": task[
                    "priority"
                ],
                "reason": (
                    "Lower-priority work delayed "
                    "to preserve higher-priority "
                    "operational capacity."
                ),
            }
        )

    remaining_blocked = max(
        0,
        len(
            blocked_tasks
        )
        - len(
            delayed_tasks
        ),
    )

    metrics = calculate_snapshot_metrics(
        simulated
    )

    risk = calculate_snapshot_risk(
        None,
        simulated,
    )[
        "workforce_risk_score"
    ]

    risk += (
        remaining_blocked * 8
    )

    # Delaying work reduces immediate operational risk,
    # but introduces backlog pressure.
    risk += (
        len(
            delayed_tasks
        )
        * 2
    )

    risk = clamp(
        risk
    )

    return {
        "strategy": STRATEGY_REALLOCATE_DELAY,
        "name": (
            "Reallocate + Delay Lower Priority Work"
        ),
        "description": (
            "Reallocate suitable employees and "
            "temporarily delay lower-priority work "
            "when required to protect critical work."
        ),
        "metrics": metrics,
        "risk_score": round(
            risk,
            2,
        ),
        "risk_level": (
            "Critical"
            if risk >= 80
            else "High"
            if risk >= 60
            else "Medium"
            if risk >= 35
            else "Low"
        ),
        "reassignments": result[
            "reassignments"
        ],
        "blocked_tasks": blocked_tasks[
            len(
                delayed_tasks
            ):
        ],
        "delayed_tasks": delayed_tasks,
        "affected_resources": find_affected_resources(
            baseline,
            simulated,
        ),
        "sla_impact": (
            "Some lower-priority work may "
            "experience planned delay."
        ),
        "simulated_state": simulated,
    }


# ============================================================
# STRATEGY COMPARISON
# ============================================================

def compare_strategies(
    strategies: List[dict],
) -> dict:
    """
    Compare strategy outcomes using measurable values.

    This function does NOT declare an absolute 'best'
    political/evaluative choice; it simply reports metrics
    and a transparent selection based on operational risk
    for the simulation engine.
    """

    if not strategies:

        return {
            "strategies": [],
            "lowest_risk_strategy": None,
            "comparison": [],
        }

    comparison = []

    for strategy in strategies:

        metrics = strategy.get(
            "metrics",
            {},
        )

        comparison.append(
            {
                "strategy": strategy[
                    "strategy"
                ],
                "name": strategy[
                    "name"
                ],
                "risk_score": strategy[
                    "risk_score"
                ],
                "risk_level": strategy[
                    "risk_level"
                ],
                "utilization_percent": metrics.get(
                    "utilization_percent"
                ),
                "remaining_capacity": metrics.get(
                    "remaining_capacity"
                ),
                "reassignment_count": len(
                    strategy.get(
                        "reassignments",
                        [],
                    )
                ),
                "delayed_task_count": len(
                    strategy.get(
                        "delayed_tasks",
                        [],
                    )
                ),
                "blocked_task_count": len(
                    strategy.get(
                        "blocked_tasks",
                        [],
                    )
                ),
            }
        )

    ordered = sorted(
        comparison,
        key=lambda item: (
            item["risk_score"],
            item["blocked_task_count"],
            item["delayed_task_count"],
        ),
    )

    return {
        "strategies": comparison,
        "lowest_risk_strategy": (
            ordered[0]["strategy"]
            if ordered
            else None
        ),
        "comparison": ordered,
    }


# ============================================================
# FULL SIMULATION
# ============================================================

def run_simulation(
    db: Session,
    organization_id: int,
    scenario_type: str,
    parameters: Optional[dict] = None,
) -> dict:
    """
    Main simulation entry point.

    Workflow:

        Current State
             ↓
        Apply Scenario
             ↓
        Keep Current
             ↓
        Reallocate
             ↓
        Reallocate + Delay
             ↓
        Compare
             ↓
        Return complete result

    No production database state is changed.
    """

    if scenario_type not in SUPPORTED_SCENARIOS:

        raise ValueError(
            f"Unsupported scenario '{scenario_type}'. "
            f"Supported scenarios: "
            f"{sorted(SUPPORTED_SCENARIOS)}"
        )

    baseline = create_workforce_snapshot(
        db,
        organization_id,
    )

    baseline_metrics = (
        calculate_snapshot_metrics(
            baseline
        )
    )

    baseline_risk = (
        calculate_snapshot_risk(
            db,
            baseline,
        )
    )

    scenario = apply_scenario(
        baseline,
        scenario_type,
        parameters,
    )

    scenario_metrics = (
        calculate_snapshot_metrics(
            scenario
        )
    )

    scenario_risk = (
        calculate_snapshot_risk(
            db,
            scenario,
        )
    )

    affected_resources = (
        find_affected_resources(
            baseline,
            scenario,
        )
    )

    keep_current = (
        simulate_keep_current(
            baseline,
            scenario,
        )
    )

    reallocate = (
        simulate_reallocation(
            db,
            organization_id,
            baseline,
            scenario,
        )
    )

    reallocate_delay = (
        simulate_reallocation_and_delay(
            db,
            organization_id,
            baseline,
            scenario,
        )
    )

    comparison = compare_strategies(
        [
            keep_current,
            reallocate,
            reallocate_delay,
        ]
    )

    # --------------------------------------------------------
    # Risk delta
    # --------------------------------------------------------

    risk_delta = (
        scenario_risk[
            "workforce_risk_score"
        ]
        -
        baseline_risk[
            "workforce_risk_score"
        ]
    )

    # --------------------------------------------------------
    # Capacity delta
    # --------------------------------------------------------

    capacity_delta = (
        scenario_metrics[
            "remaining_capacity"
        ]
        -
        baseline_metrics[
            "remaining_capacity"
        ]
    )

    utilization_delta = (
        scenario_metrics[
            "utilization_percent"
        ]
        -
        baseline_metrics[
            "utilization_percent"
        ]
    )

    return {
        "simulation_id": (
            f"SIM-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        ),
        "organization_id": organization_id,
        "scenario_type": scenario_type,
        "parameters": parameters or {},
        "created_at": datetime.utcnow().isoformat(),

        "baseline": {
            "metrics": baseline_metrics,
            "risk": baseline_risk,
        },

        "scenario": {
            "metrics": scenario_metrics,
            "risk": scenario_risk,
        },

        "impact": {
            "risk_delta": round(
                risk_delta,
                2,
            ),
            "capacity_delta": round(
                capacity_delta,
                2,
            ),
            "utilization_delta": round(
                utilization_delta,
                2,
            ),
            "affected_employees": len(
                affected_resources[
                    "employees"
                ]
            ),
            "affected_tasks": len(
                affected_resources[
                    "tasks"
                ]
            ),
        },

        "affected_resources": (
            affected_resources
        ),

        "strategies": {
            "keep_current": keep_current,
            "reallocate": reallocate,
            "reallocate_and_delay": (
                reallocate_delay
            ),
        },

        "comparison": comparison,

        "recommendation": {
            "strategy": comparison[
                "lowest_risk_strategy"
            ],
            "reason": (
                "Strategy comparison is based "
                "on simulated operational risk, "
                "blocked work and delayed work."
            ),
        },

        "production_state_changed": False,
    }


# ============================================================
# SPECIALIZED SCENARIOS
# ============================================================

def simulate_employee_unavailability(
    db: Session,
    organization_id: int,
    employee_id: int,
) -> dict:
    """
    Convenience function for the most important demo:

        Employee becomes unavailable.
    """

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type="employee_unavailable",
        parameters={
            "employee_id": employee_id,
        },
    )


def simulate_multiple_unavailability(
    db: Session,
    organization_id: int,
    employee_ids: List[int],
) -> dict:
    """
    Crisis simulation for multiple unavailable employees.
    """

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type=(
            "multiple_employees_unavailable"
        ),
        parameters={
            "employee_ids": employee_ids,
        },
    )


def simulate_urgent_task(
    db: Session,
    organization_id: int,
    title: str,
    estimated_hours: float,
    required_skill_id: Optional[int] = None,
    project_id: Optional[int] = None,
) -> dict:
    """
    Simulate arrival of a new urgent task.
    """

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type="urgent_task",
        parameters={
            "title": title,
            "estimated_hours": estimated_hours,
            "required_skill_id": required_skill_id,
            "project_id": project_id,
        },
    )


def simulate_capacity_reduction(
    db: Session,
    organization_id: int,
    employee_id: int,
    reduction_percent: float,
) -> dict:
    """
    Simulate reduced employee capacity.
    """

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type="capacity_reduction",
        parameters={
            "employee_id": employee_id,
            "reduction_percent": reduction_percent,
        },
    )


def simulate_workload_increase(
    db: Session,
    organization_id: int,
    increase_percent: float,
    employee_ids: Optional[List[int]] = None,
) -> dict:
    """
    Simulate a workforce-wide or team-level workload spike.
    """

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type="workload_increase",
        parameters={
            "increase_percent": increase_percent,
            "employee_ids": employee_ids,
        },
    )


def simulate_priority_change(
    db: Session,
    organization_id: int,
    task_id: int,
    new_priority: str,
) -> dict:
    """
    Simulate changing a task's business priority.
    """

    allowed = {
        "Critical",
        "High",
        "Medium",
        "Low",
    }

    if new_priority not in allowed:

        raise ValueError(
            "Invalid priority. "
            f"Use one of: {sorted(allowed)}"
        )

    return run_simulation(
        db=db,
        organization_id=organization_id,
        scenario_type="priority_change",
        parameters={
            "task_id": task_id,
            "new_priority": new_priority,
        },
    )


# ============================================================
# DEMO SCENARIO
# ============================================================

def run_demo_crisis_simulation(
    db: Session,
    organization_id: int,
    employee_ids: List[int],
) -> dict:
    """
    Five-minute hackathon demo helper.

    Example:

        3 critical employees unavailable
        ↓
        impact analysis
        ↓
        recovery strategy comparison

    Still completely non-destructive.
    """

    if not employee_ids:

        raise ValueError(
            "At least one employee is required."
        )

    return simulate_multiple_unavailability(
        db=db,
        organization_id=organization_id,
        employee_ids=employee_ids,
    )
