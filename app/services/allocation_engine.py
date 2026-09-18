from typing import Any, Dict, List, Optional


class AllocationEngine:
    """
    Deterministic workforce allocation engine.

    The engine does not use an LLM to decide assignments.
    It evaluates employees using measurable factors such as:

    - Skill match
    - Skill proficiency
    - Available capacity
    - Current workload
    - Task priority
    - SLA urgency
    - Location compatibility
    - Historical performance

    The returned result can then be explained by the AI Copilot.
    """

    DEFAULT_WEIGHTS = {
        "skill_match": 0.30,
        "proficiency": 0.15,
        "capacity": 0.20,
        "workload": 0.10,
        "priority": 0.10,
        "sla": 0.10,
        "performance": 0.05,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._validate_weights()

    def _validate_weights(self) -> None:
        required = set(self.DEFAULT_WEIGHTS.keys())

        if set(self.weights.keys()) != required:
            raise ValueError(
                f"Weights must contain exactly: {sorted(required)}"
            )

        total = sum(self.weights.values())

        if total <= 0:
            raise ValueError("Allocation weights must have a positive total.")

        # Normalize weights automatically.
        for key in self.weights:
            self.weights[key] = self.weights[key] / total

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def rank_candidates(
        self,
        task: Dict[str, Any],
        employees: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Rank all eligible employees for a task.

        Returns candidates sorted by descending score.
        """

        results = []

        for employee in employees:
            evaluation = self.evaluate_candidate(task, employee)

            if evaluation["eligible"]:
                results.append(evaluation)

        results.sort(
            key=lambda item: item["overall_score"],
            reverse=True,
        )

        for index, result in enumerate(results, start=1):
            result["rank"] = index

        return results

    def find_best_candidate(
        self,
        task: Dict[str, Any],
        employees: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Return the highest-scoring eligible employee.
        """

        candidates = self.rank_candidates(task, employees)

        if not candidates:
            return None

        return candidates[0]

    def evaluate_candidate(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate one employee against one task.
        """

        eligibility = self._check_eligibility(task, employee)

        skill_match = self._calculate_skill_match(task, employee)
        proficiency = self._calculate_proficiency(task, employee)
        capacity = self._calculate_capacity(employee)
        workload = self._calculate_workload(employee)
        priority = self._calculate_priority(task)
        sla = self._calculate_sla(task)
        performance = self._calculate_performance(employee)

        score = (
            skill_match * self.weights["skill_match"]
            + proficiency * self.weights["proficiency"]
            + capacity * self.weights["capacity"]
            + workload * self.weights["workload"]
            + priority * self.weights["priority"]
            + sla * self.weights["sla"]
            + performance * self.weights["performance"]
        )

        reasons = self._generate_reasons(
            task=task,
            employee=employee,
            skill_match=skill_match,
            proficiency=proficiency,
            capacity=capacity,
            workload=workload,
            priority=priority,
            sla=sla,
            performance=performance,
        )

        rejection_reasons = []

        if not eligibility["eligible"]:
            rejection_reasons.extend(eligibility["reasons"])

        predicted_risk = self._calculate_predicted_risk(
            task=task,
            employee=employee,
            capacity=capacity,
            workload=workload,
            skill_match=skill_match,
            sla=sla,
        )

        return {
            "employee_id": employee.get("id"),
            "employee_name": employee.get(
                "name",
                f"Employee {employee.get('id', 'Unknown')}",
            ),
            "eligible": eligibility["eligible"],
            "overall_score": round(score, 2),
            "skill_match": round(skill_match, 2),
            "proficiency": round(proficiency, 2),
            "available_capacity": round(capacity, 2),
            "workload_score": round(workload, 2),
            "priority_score": round(priority, 2),
            "sla_score": round(sla, 2),
            "performance_score": round(performance, 2),
            "predicted_risk": predicted_risk,
            "reasons": reasons,
            "rejection_reasons": rejection_reasons,
        }

    # ------------------------------------------------------------------
    # ELIGIBILITY
    # ------------------------------------------------------------------

    def _check_eligibility(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
    ) -> Dict[str, Any]:
        reasons = []

        if not employee.get("available", True):
            reasons.append("Employee is currently unavailable.")

        capacity = self._get_number(
            employee,
            "available_capacity",
            employee.get("capacity", 100),
        )

        if capacity <= 0:
            reasons.append("Employee has no available capacity.")

        required_skill = task.get("required_skill")

        if required_skill:
            skills = employee.get("skills", {})

            if isinstance(skills, list):
                skill_names = [
                    str(item.get("name", "")).lower()
                    if isinstance(item, dict)
                    else str(item).lower()
                    for item in skills
                ]

                if required_skill.lower() not in skill_names:
                    reasons.append(
                        f"Required skill '{required_skill}' is not available."
                    )

            elif isinstance(skills, dict):
                if required_skill.lower() not in {
                    str(key).lower() for key in skills.keys()
                }:
                    reasons.append(
                        f"Required skill '{required_skill}' is not available."
                    )

        return {
            "eligible": len(reasons) == 0,
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # SKILL MATCH
    # ------------------------------------------------------------------

    def _calculate_skill_match(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
    ) -> float:
        required_skill = task.get("required_skill")

        if not required_skill:
            return 100.0

        skills = employee.get("skills", {})

        if isinstance(skills, list):
            normalized = {}

            for skill in skills:
                if isinstance(skill, dict):
                    name = str(skill.get("name", "")).lower()
                    level = skill.get("level", skill.get("proficiency", 1))
                    normalized[name] = level
                else:
                    normalized[str(skill).lower()] = 3

            skills = normalized

        if not isinstance(skills, dict):
            return 0.0

        skill_keys = {
            str(key).lower(): value
            for key, value in skills.items()
        }

        required = required_skill.lower()

        # Exact match.
        if required in skill_keys:
            return 100.0

        # Adjacent/related skills.
        related_skills = {
            "python": [
                "fastapi",
                "django",
                "flask",
                "data science",
                "machine learning",
            ],
            "fastapi": [
                "python",
                "backend",
                "api development",
            ],
            "javascript": [
                "typescript",
                "react",
                "node.js",
                "frontend",
            ],
            "typescript": [
                "javascript",
                "react",
                "node.js",
            ],
            "react": [
                "javascript",
                "typescript",
                "frontend",
            ],
            "sql": [
                "postgresql",
                "mysql",
                "database",
                "data engineering",
            ],
            "postgresql": [
                "sql",
                "database",
            ],
            "aws": [
                "cloud",
                "devops",
                "azure",
                "gcp",
            ],
            "docker": [
                "devops",
                "kubernetes",
                "cloud",
            ],
            "embedded systems": [
                "iot",
                "esp32",
                "microcontrollers",
                "electronics",
            ],
            "iot": [
                "embedded systems",
                "esp32",
                "electronics",
            ],
        }

        related = related_skills.get(required, [])

        for skill in related:
            if skill.lower() in skill_keys:
                return 65.0

        return 0.0

    def _calculate_proficiency(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
    ) -> float:
        required_skill = task.get("required_skill")

        if not required_skill:
            return 100.0

        skills = employee.get("skills", {})

        if isinstance(skills, list):
            converted = {}

            for skill in skills:
                if isinstance(skill, dict):
                    converted[
                        str(skill.get("name", "")).lower()
                    ] = skill.get(
                        "level",
                        skill.get("proficiency", 3),
                    )
                else:
                    converted[str(skill).lower()] = 3

            skills = converted

        if not isinstance(skills, dict):
            return 0.0

        level = skills.get(required_skill)

        if level is None:
            # Case-insensitive lookup.
            for name, value in skills.items():
                if str(name).lower() == required_skill.lower():
                    level = value
                    break

        if level is None:
            return 40.0

        try:
            level = float(level)
        except (TypeError, ValueError):
            level = 3.0

        # Accept both 1–5 and 0–100 proficiency systems.
        if level <= 5:
            return min(100.0, max(0.0, level / 5 * 100))

        return min(100.0, max(0.0, level))

    # ------------------------------------------------------------------
    # CAPACITY / WORKLOAD
    # ------------------------------------------------------------------

    def _calculate_capacity(
        self,
        employee: Dict[str, Any],
    ) -> float:
        available = self._get_number(
            employee,
            "available_capacity",
            employee.get("capacity", 100),
        )

        return max(0.0, min(100.0, available))

    def _calculate_workload(
        self,
        employee: Dict[str, Any],
    ) -> float:
        workload = self._get_number(
            employee,
            "workload",
            employee.get("utilization", 0),
        )

        # Lower workload is better.
        return max(0.0, min(100.0, 100.0 - workload))

    # ------------------------------------------------------------------
    # PRIORITY / SLA
    # ------------------------------------------------------------------

    def _calculate_priority(
        self,
        task: Dict[str, Any],
    ) -> float:
        priority = str(
            task.get("priority", "medium")
        ).lower()

        mapping = {
            "critical": 100.0,
            "urgent": 95.0,
            "high": 80.0,
            "medium": 60.0,
            "low": 30.0,
        }

        return mapping.get(priority, 50.0)

    def _calculate_sla(
        self,
        task: Dict[str, Any],
    ) -> float:
        """
        Higher score means the task requires faster/surer allocation.
        """

        if task.get("sla_at_risk") is True:
            return 100.0

        sla_hours = task.get("sla_hours")

        if sla_hours is not None:
            try:
                sla_hours = float(sla_hours)

                if sla_hours <= 4:
                    return 100.0
                if sla_hours <= 8:
                    return 90.0
                if sla_hours <= 24:
                    return 75.0
                if sla_hours <= 48:
                    return 60.0
                if sla_hours <= 72:
                    return 45.0

                return 25.0
            except (TypeError, ValueError):
                pass

        return 50.0

    # ------------------------------------------------------------------
    # PERFORMANCE
    # ------------------------------------------------------------------

    def _calculate_performance(
        self,
        employee: Dict[str, Any],
    ) -> float:
        performance = employee.get(
            "historical_performance",
            employee.get("performance", 70),
        )

        try:
            performance = float(performance)
        except (TypeError, ValueError):
            performance = 70.0

        return max(0.0, min(100.0, performance))

    # ------------------------------------------------------------------
    # RISK
    # ------------------------------------------------------------------

    def _calculate_predicted_risk(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
        capacity: float,
        workload: float,
        skill_match: float,
        sla: float,
    ) -> str:
        risk_score = 0.0

        current_workload = self._get_number(
            employee,
            "workload",
            employee.get("utilization", 0),
        )

        risk_score += current_workload * 0.35

        risk_score += max(0.0, 100.0 - capacity) * 0.25

        risk_score += max(0.0, 100.0 - skill_match) * 0.20

        if task.get("sla_at_risk"):
            risk_score += 15.0

        risk_score += sla * 0.10

        if risk_score >= 75:
            return "critical"

        if risk_score >= 55:
            return "high"

        if risk_score >= 30:
            return "medium"

        return "low"

    # ------------------------------------------------------------------
    # EXPLANATIONS
    # ------------------------------------------------------------------

    def _generate_reasons(
        self,
        task: Dict[str, Any],
        employee: Dict[str, Any],
        skill_match: float,
        proficiency: float,
        capacity: float,
        workload: float,
        priority: float,
        sla: float,
        performance: float,
    ) -> List[str]:
        reasons = []

        if skill_match >= 95:
            reasons.append("Exact required-skill match.")
        elif skill_match >= 60:
            reasons.append("Adjacent skill match; ramp-up may be required.")
        else:
            reasons.append("Weak skill match.")

        if proficiency >= 80:
            reasons.append("Strong skill proficiency.")
        elif proficiency >= 60:
            reasons.append("Moderate skill proficiency.")

        if capacity >= 70:
            reasons.append(
                f"Good available capacity ({capacity:.0f}%)."
            )
        elif capacity >= 40:
            reasons.append(
                f"Moderate available capacity ({capacity:.0f}%)."
            )
        else:
            reasons.append(
                f"Limited available capacity ({capacity:.0f}%)."
            )

        if workload >= 70:
            reasons.append("Current workload is relatively low.")
        elif workload < 30:
            reasons.append("Current workload is high.")

        if sla >= 80:
            reasons.append("Task has significant SLA urgency.")

        if priority >= 80:
            reasons.append("Task has high business priority.")

        if performance >= 85:
            reasons.append("Strong historical performance.")

        return reasons

    # ------------------------------------------------------------------
    # UTILITIES
    # ------------------------------------------------------------------

    @staticmethod
    def _get_number(
        data: Dict[str, Any],
        key: str,
        default: Any = 0,
    ) -> float:
        value = data.get(key, default)

        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default or 0)


# ----------------------------------------------------------------------
# CONVENIENCE FUNCTION
# ----------------------------------------------------------------------

def calculate_allocation(
    task: Dict[str, Any],
    employees: List[Dict[str, Any]],
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Simple function for API/service usage.

    Example:

        result = calculate_allocation(
            task,
            employees,
        )
    """

    engine = AllocationEngine(weights=weights)

    candidates = engine.rank_candidates(
        task=task,
        employees=employees,
    )

    best = candidates[0] if candidates else None

    return {
        "task_id": task.get("id"),
        "recommended_candidate": best,
        "candidates": candidates,
        "candidate_count": len(candidates),
        "allocation_available": best is not None,
    }from copy import deepcopy
from typing import Any, Dict, List, Optional


class SimulationEngine:
    """
    Workforce What-If Simulation Engine.

    IMPORTANT:
    This engine never modifies the original workforce state.

    It creates an isolated copy of the current state and evaluates
    different workforce strategies against that copy.

    Supported scenarios:
        - employee_unavailable
        - multiple_employees_unavailable
        - urgent_task
        - capacity_reduction
        - deadline_acceleration
        - workload_increase
        - skill_shortage

    Supported strategies:
        A - Keep current assignments
        B - Reallocate suitable employees
        C - Reallocate and delay lower-priority work
    """

    PRIORITY_VALUES = {
        "critical": 5,
        "urgent": 5,
        "high": 4,
        "medium": 3,
        "low": 1,
    }

    def __init__(self, allocation_engine=None):
        self.allocation_engine = allocation_engine

    # ================================================================
    # PUBLIC API
    # ================================================================

    def run_simulation(
        self,
        workforce_state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Run a complete simulation.

        The input workforce_state is never mutated.
        """

        baseline = deepcopy(workforce_state)

        scenario_state = deepcopy(workforce_state)

        scenario_type = scenario.get("type", "employee_unavailable")

        changes = self._apply_scenario(
            scenario_state,
            scenario,
        )

        baseline_metrics = self.calculate_metrics(
            baseline
        )

        scenario_metrics = self.calculate_metrics(
            scenario_state
        )

        strategies = []

        strategies.append(
            self._strategy_keep_current(
                baseline,
                scenario_state,
            )
        )

        strategies.append(
            self._strategy_reallocate(
                baseline,
                scenario_state,
            )
        )

        strategies.append(
            self._strategy_reallocate_and_delay(
                baseline,
                scenario_state,
            )
        )

        recommended = self._select_strategy(
            strategies
        )

        return {
            "simulation_id": self._generate_simulation_id(
                scenario
            ),
            "scenario": scenario,
            "scenario_type": scenario_type,
            "changes_applied": changes,
            "baseline": baseline_metrics,
            "scenario_state": scenario_metrics,
            "impact": self._calculate_impact(
                baseline_metrics,
                scenario_metrics,
            ),
            "strategies": strategies,
            "recommended_strategy": recommended,
            "affected_employees": self._find_affected_employees(
                baseline,
                scenario_state,
            ),
            "affected_tasks": self._find_affected_tasks(
                baseline,
                scenario_state,
            ),
            "affected_projects": self._find_affected_projects(
                baseline,
                scenario_state,
            ),
            "simulation_safe": True,
            "production_state_modified": False,
        }

    # ================================================================
    # SCENARIO APPLICATION
    # ================================================================

    def _apply_scenario(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        scenario_type = scenario.get("type")
        changes = []

        if scenario_type == "employee_unavailable":
            changes.extend(
                self._employee_unavailable(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "multiple_employees_unavailable":
            changes.extend(
                self._multiple_employees_unavailable(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "urgent_task":
            changes.extend(
                self._urgent_task(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "capacity_reduction":
            changes.extend(
                self._capacity_reduction(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "deadline_acceleration":
            changes.extend(
                self._deadline_acceleration(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "workload_increase":
            changes.extend(
                self._workload_increase(
                    state,
                    scenario,
                )
            )

        elif scenario_type == "skill_shortage":
            changes.extend(
                self._skill_shortage(
                    state,
                    scenario,
                )
            )

        else:
            changes.append(
                {
                    "type": "unknown_scenario",
                    "message": (
                        f"Unknown scenario type: {scenario_type}"
                    ),
                }
            )

        return changes

    # ================================================================
    # EMPLOYEE UNAVAILABLE
    # ================================================================

    def _employee_unavailable(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        employee_id = scenario.get("employee_id")

        if employee_id is None:
            return [
                {
                    "type": "validation_error",
                    "message": "employee_id is required.",
                }
            ]

        employee = self._find_employee(
            state,
            employee_id,
        )

        if not employee:
            return [
                {
                    "type": "employee_not_found",
                    "employee_id": employee_id,
                }
            ]

        employee["available"] = False

        duration = scenario.get(
            "duration_days"
        )

        if duration is not None:
            employee["unavailable_for_days"] = duration

        return [
            {
                "type": "employee_unavailable",
                "employee_id": employee_id,
                "employee_name": employee.get("name"),
                "duration_days": duration,
            }
        ]

    # ================================================================
    # MULTIPLE EMPLOYEES UNAVAILABLE
    # ================================================================

    def _multiple_employees_unavailable(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        employee_ids = scenario.get(
            "employee_ids",
            [],
        )

        changes = []

        for employee_id in employee_ids:

            employee = self._find_employee(
                state,
                employee_id,
            )

            if not employee:
                continue

            employee["available"] = False

            changes.append(
                {
                    "type": "employee_unavailable",
                    "employee_id": employee_id,
                    "employee_name": employee.get("name"),
                }
            )

        return changes

    # ================================================================
    # URGENT TASK
    # ================================================================

    def _urgent_task(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        task = {
            "id": scenario.get(
                "task_id",
                "SIM-URGENT-001",
            ),
            "title": scenario.get(
                "title",
                "Emergency Priority Task",
            ),
            "priority": "critical",
            "required_skill": scenario.get(
                "required_skill"
            ),
            "estimated_hours": scenario.get(
                "estimated_hours",
                8,
            ),
            "sla_hours": scenario.get(
                "sla_hours",
                4,
            ),
            "sla_at_risk": True,
            "status": "unassigned",
            "project_id": scenario.get(
                "project_id"
            ),
        }

        state.setdefault(
            "tasks",
            []
        ).append(task)

        return [
            {
                "type": "urgent_task_created",
                "task_id": task["id"],
                "priority": "critical",
                "required_skill": task["required_skill"],
            }
        ]

    # ================================================================
    # CAPACITY REDUCTION
    # ================================================================

    def _capacity_reduction(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        employee_id = scenario.get("employee_id")

        reduction = float(
            scenario.get(
                "reduction_percent",
                20,
            )
        )

        employee = self._find_employee(
            state,
            employee_id,
        )

        if not employee:
            return [
                {
                    "type": "employee_not_found",
                    "employee_id": employee_id,
                }
            ]

        current_capacity = self._number(
            employee.get(
                "available_capacity",
                employee.get(
                    "capacity",
                    100,
                ),
            ),
            100,
        )

        new_capacity = max(
            0,
            current_capacity - reduction,
        )

        employee[
            "available_capacity"
        ] = new_capacity

        return [
            {
                "type": "capacity_reduced",
                "employee_id": employee_id,
                "old_capacity": current_capacity,
                "new_capacity": new_capacity,
            }
        ]

    # ================================================================
    # DEADLINE ACCELERATION
    # ================================================================

    def _deadline_acceleration(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        project_id = scenario.get(
            "project_id"
        )

        project = self._find_by_id(
            state.get("projects", []),
            project_id,
        )

        if not project:
            return [
                {
                    "type": "project_not_found",
                    "project_id": project_id,
                }
            ]

        old_deadline = project.get(
            "deadline"
        )

        new_deadline = scenario.get(
            "new_deadline"
        )

        if new_deadline:
            project["deadline"] = new_deadline

        return [
            {
                "type": "deadline_accelerated",
                "project_id": project_id,
                "old_deadline": old_deadline,
                "new_deadline": new_deadline,
            }
        ]

    # ================================================================
    # WORKLOAD INCREASE
    # ================================================================

    def _workload_increase(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        employee_id = scenario.get(
            "employee_id"
        )

        increase = float(
            scenario.get(
                "increase_percent",
                20,
            )
        )

        employee = self._find_employee(
            state,
            employee_id,
        )

        if not employee:
            return [
                {
                    "type": "employee_not_found",
                    "employee_id": employee_id,
                }
            ]

        old_workload = self._number(
            employee.get(
                "workload",
                employee.get(
                    "utilization",
                    0,
                ),
            ),
            0,
        )

        new_workload = min(
            100,
            old_workload + increase,
        )

        employee["workload"] = new_workload

        capacity = max(
            0,
            100 - new_workload,
        )

        employee[
            "available_capacity"
        ] = capacity

        return [
            {
                "type": "workload_increased",
                "employee_id": employee_id,
                "old_workload": old_workload,
                "new_workload": new_workload,
            }
        ]

    # ================================================================
    # SKILL SHORTAGE
    # ================================================================

    def _skill_shortage(
        self,
        state: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        skill = scenario.get(
            "skill"
        )

        unavailable_ids = scenario.get(
            "employee_ids",
            [],
        )

        changes = []

        for employee_id in unavailable_ids:

            employee = self._find_employee(
                state,
                employee_id,
            )

            if not employee:
                continue

            employee["available"] = False

            changes.append(
                {
                    "type": "skill_capacity_removed",
                    "employee_id": employee_id,
                    "skill": skill,
                }
            )

        return changes

    # ================================================================
    # STRATEGY A
    # ================================================================

    def _strategy_keep_current(
        self,
        baseline: Dict[str, Any],
        scenario_state: Dict[str, Any],
    ) -> Dict[str, Any]:

        state = deepcopy(
            scenario_state
        )

        metrics = self.calculate_metrics(
            state
        )

        return {
            "strategy": "A",
            "name": "Keep Current Assignments",
            "description": (
                "Do not change existing assignments."
            ),
            "state": metrics,
            "affected_assignments": self._find_invalid_assignments(
                state
            ),
            "risk_level": self._overall_risk(
                metrics
            ),
            "score": self._strategy_score(
                metrics
            ),
        }

    # ================================================================
    # STRATEGY B
    # ================================================================

    def _strategy_reallocate(
        self,
        baseline: Dict[str, Any],
        scenario_state: Dict[str, Any],
    ) -> Dict[str, Any]:

        state = deepcopy(
            scenario_state
        )

        changes = []

        unavailable_ids = {
            employee.get("id")
            for employee in state.get(
                "employees",
                []
            )
            if not employee.get(
                "available",
                True,
            )
        }

        assignments = state.get(
            "assignments",
            []
        )

        affected = [
            assignment
            for assignment in assignments
            if assignment.get(
                "employee_id"
            ) in unavailable_ids
        ]

        employees = state.get(
            "employees",
            []
        )

        for assignment in affected:

            task = self._find_by_id(
                state.get("tasks", []),
                assignment.get(
                    "task_id"
                ),
            )

            if not task:
                continue

            candidates = self._find_reallocation_candidates(
                task,
                employees,
                unavailable_ids,
            )

            if not candidates:
                continue

            candidate = candidates[0]

            old_employee = assignment.get(
                "employee_id"
            )

            assignment[
                "employee_id"
            ] = candidate.get(
                "id"
            )

            changes.append(
                {
                    "task_id": task.get("id"),
                    "from_employee_id": old_employee,
                    "to_employee_id": candidate.get(
                        "id"
                    ),
                    "to_employee_name": candidate.get(
                        "name"
                    ),
                    "reason": candidate.get(
                        "reason",
                        "Best available candidate.",
                    ),
                }
            )

        metrics = self.calculate_metrics(
            state
        )

        return {
            "strategy": "B",
            "name": "Reallocate Suitable Employees",
            "description": (
                "Move affected work to available "
                "and suitable employees."
            ),
            "state": metrics,
            "changes": changes,
            "unresolved_assignments": len(
                affected
            ) - len(changes),
            "risk_level": self._overall_risk(
                metrics
            ),
            "score": self._strategy_score(
                metrics
            ),
        }

    # ================================================================
    # STRATEGY C
    # ================================================================

    def _strategy_reallocate_and_delay(
        self,
        baseline: Dict[str, Any],
        scenario_state: Dict[str, Any],
    ) -> Dict[str, Any]:

        state = deepcopy(
            scenario_state
        )

        changes = []

        unavailable_ids = {
            employee.get("id")
            for employee in state.get(
                "employees",
                []
            )
            if not employee.get(
                "available",
                True,
            )
        }

        assignments = state.get(
            "assignments",
            []
        )

        affected = [
            assignment
            for assignment in assignments
            if assignment.get(
                "employee_id"
            ) in unavailable_ids
        ]

        employees = state.get(
            "employees",
            []
        )

        for assignment in affected:

            task = self._find_by_id(
                state.get("tasks", []),
                assignment.get(
                    "task_id"
                ),
            )

            if not task:
                continue

            candidates = self._find_reallocation_candidates(
                task,
                employees,
                unavailable_ids,
            )

            if candidates:
                candidate = candidates[0]

                old_employee = assignment.get(
                    "employee_id"
                )

                assignment[
                    "employee_id"
                ] = candidate.get(
                    "id"
                )

                changes.append(
                    {
                        "type": "reallocation",
                        "task_id": task.get("id"),
                        "from_employee_id": old_employee,
                        "to_employee_id": candidate.get(
                            "id"
                        ),
                    }
                )

            else:
                priority = str(
                    task.get(
                        "priority",
                        "medium",
                    )
                ).lower()

                if priority in {
                    "low",
                    "medium",
                }:
                    task[
                        "status"
                    ] = "delayed"

                    task[
                        "simulation_delayed"
                    ] = True

                    changes.append(
                        {
                            "type": "delay",
                            "task_id": task.get(
                                "id"
                            ),
                            "reason": (
                                "No suitable available "
                                "employee found."
                            ),
                        }
                    )

        metrics = self.calculate_metrics(
            state
        )

        return {
            "strategy": "C",
            "name": (
                "Reallocate + Delay Lower Priority Work"
            ),
            "description": (
                "Protect critical work by reallocating "
                "resources and delaying lower-priority tasks "
                "when required."
            ),
            "state": metrics,
            "changes": changes,
            "risk_level": self._overall_risk(
                metrics
            ),
            "score": self._strategy_score(
                metrics
            ),
        }

    # ================================================================
    # CANDIDATE DISCOVERY
    # ================================================================

    def _find_reallocation_candidates(
        self,
        task: Dict[str, Any],
        employees: List[Dict[str, Any]],
        unavailable_ids: set,
    ) -> List[Dict[str, Any]]:

        candidates = []

        required_skill = str(
            task.get(
                "required_skill",
                ""
            )
        ).lower()

        for employee in employees:

            employee_id = employee.get(
                "id"
            )

            if employee_id in unavailable_ids:
                continue

            if not employee.get(
                "available",
                True,
            ):
                continue

            capacity = self._number(
                employee.get(
                    "available_capacity",
                    employee.get(
                        "capacity",
                        0,
                    ),
                ),
                0,
            )

            if capacity <= 0:
                continue

            skills = employee.get(
                "skills",
                {}
            )

            skill_score = 0

            if isinstance(skills, dict):

                normalized = {
                    str(key).lower()
                    for key in skills.keys()
                }

                if required_skill in normalized:
                    skill_score = 100

            elif isinstance(skills, list):

                for skill in skills:

                    if isinstance(
                        skill,
                        dict,
                    ):
                        name = str(
                            skill.get(
                                "name",
                                ""
                            )
                        ).lower()
                    else:
                        name = str(
                            skill
                        ).lower()

                    if name == required_skill:
                        skill_score = 100
                        break

            if required_skill == "":
                skill_score = 70

            workload = self._number(
                employee.get(
                    "workload",
                    employee.get(
                        "utilization",
                        0,
                    ),
                ),
                0,
            )

            score = (
                skill_score * 0.55
                + capacity * 0.30
                + (100 - workload) * 0.15
            )

            candidates.append(
                {
                    "id": employee_id,
                    "name": employee.get(
                        "name"
                    ),
                    "score": round(
                        score,
                        2,
                    ),
                    "capacity": capacity,
                    "skill_score": skill_score,
                    "workload": workload,
                    "reason": (
                        "Suitable available "
                        "capacity and skill match."
                    ),
                }
            )

        candidates.sort(
            key=lambda item: item["score"],
            reverse=True,
        )

        return candidates

    # ================================================================
    # METRICS
    # ================================================================

    def calculate_metrics(
        self,
        state: Dict[str, Any],
    ) -> Dict[str, Any]:

        employees = state.get(
            "employees",
            []
        )

        tasks = state.get(
            "tasks",
            []
        )

        assignments = state.get(
            "assignments",
            []
        )

        total_employees = len(
            employees
        )

        available_employees = sum(
            1
            for employee in employees
            if employee.get(
                "available",
                True,
            )
        )

        workloads = []

        for employee in employees:

            workload = self._number(
                employee.get(
                    "workload",
                    employee.get(
                        "utilization",
                        0,
                    ),
                ),
                0,
            )

            workloads.append(
                max(
                    0,
                    min(
                        100,
                        workload,
                    ),
                )
            )

        average_utilization = (
            sum(workloads) / len(workloads)
            if workloads
            else 0
        )

        overloaded_employees = sum(
            1
            for workload in workloads
            if workload >= 85
        )

        unassigned_tasks = 0

        for task in tasks:

            task_id = task.get(
                "id"
            )

            has_assignment = any(
                assignment.get(
                    "task_id"
                ) == task_id
                for assignment in assignments
            )

            if not has_assignment:
                unassigned_tasks += 1

        sla_risk_tasks = sum(
            1
            for task in tasks
            if task.get(
                "sla_at_risk",
                False,
            )
            or str(
                task.get(
                    "status",
                    ""
                )
            ).lower()
            in {
                "at_risk",
                "critical",
            }
        )

        critical_tasks = sum(
            1
            for task in tasks
            if str(
                task.get(
                    "priority",
                    ""
                )
            ).lower()
            in {
                "critical",
                "urgent",
            }
        )

        invalid_assignments = len(
            self._find_invalid_assignments(
                state
            )
        )

        risk_score = (
            overloaded_employees * 8
            + unassigned_tasks * 6
            + sla_risk_tasks * 10
            + invalid_assignments * 12
        )

        risk_score = min(
            100,
            risk_score,
        )

        return {
            "total_employees": total_employees,
            "available_employees": available_employees,
            "unavailable_employees": (
                total_employees
                - available_employees
            ),
            "average_utilization": round(
                average_utilization,
                2,
            ),
            "overloaded_employees": (
                overloaded_employees
            ),
            "total_tasks": len(tasks),
            "assigned_tasks": (
                len(assignments)
            ),
            "unassigned_tasks": (
                unassigned_tasks
            ),
            "critical_tasks": (
                critical_tasks
            ),
            "sla_risk_tasks": (
                sla_risk_tasks
            ),
            "invalid_assignments": (
                invalid_assignments
            ),
            "operational_risk_score": round(
                risk_score,
                2,
            ),
        }

    # ================================================================
    # IMPACT
    # ================================================================

    def _calculate_impact(
        self,
        baseline: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> Dict[str, Any]:

        return {
            "utilization_change": round(
                scenario["average_utilization"]
                - baseline["average_utilization"],
                2,
            ),
            "available_employee_change": (
                scenario["available_employees"]
                - baseline["available_employees"]
            ),
            "unassigned_task_change": (
                scenario["unassigned_tasks"]
                - baseline["unassigned_tasks"]
            ),
            "sla_risk_change": (
                scenario["sla_risk_tasks"]
                - baseline["sla_risk_tasks"]
            ),
            "operational_risk_change": round(
                scenario["operational_risk_score"]
                - baseline["operational_risk_score"],
                2,
            ),
        }

    # ================================================================
    # STRATEGY SELECTION
    # ================================================================

    def _select_strategy(
        self,
        strategies: List[Dict[str, Any]],
    ) -> Dict[str, Any]:

        if not strategies:
            return {}

        ranked = sorted(
            strategies,
            key=lambda item: item.get(
                "score",
                999,
            ),
        )

        selected = ranked[0]

        return {
            "strategy": selected.get(
                "strategy"
            ),
            "name": selected.get(
                "name"
            ),
            "reason": (
                "Selected based on the lowest "
                "simulated operational risk while "
                "preserving available workforce capacity."
            ),
            "risk_level": selected.get(
                "risk_level"
            ),
            "score": selected.get(
                "score"
            ),
        }

    def _strategy_score(
        self,
        metrics: Dict[str, Any],
    ) -> float:

        risk = metrics.get(
            "operational_risk_score",
            0,
        )

        unassigned = metrics.get(
            "unassigned_tasks",
            0,
        )

        sla = metrics.get(
            "sla_risk_tasks",
            0,
        )

        return round(
            risk
            + unassigned * 2
            + sla * 3,
            2,
        )

    def _overall_risk(
        self,
        metrics: Dict[str, Any],
    ) -> str:

        score = metrics.get(
            "operational_risk_score",
            0,
        )

        if score >= 75:
            return "critical"

        if score >= 50:
            return "high"

        if score >= 25:
            return "medium"

        return "low"

    # ================================================================
    # AFFECTED RESOURCES
    # ================================================================

    def _find_affected_employees(
        self,
        baseline: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        baseline_map = {
            employee.get("id"): employee
            for employee in baseline.get(
                "employees",
                [],
            )
        }

        affected = []

        for employee in scenario.get(
            "employees",
            [],
        ):

            employee_id = employee.get(
                "id"
            )

            before = baseline_map.get(
                employee_id
            )

            if not before:
                affected.append(
                    employee
                )
                continue

            if (
                before.get("available", True)
                != employee.get("available", True)
                or before.get(
                    "workload",
                    before.get(
                        "utilization",
                        0,
                    ),
                )
                != employee.get(
                    "workload",
                    employee.get(
                        "utilization",
                        0,
                    ),
                )
            ):
                affected.append(
                    employee
                )

        return affected

    def _find_affected_tasks(
        self,
        baseline: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        baseline_tasks = {
            task.get("id"): task
            for task in baseline.get(
                "tasks",
                [],
            )
        }

        affected = []

        for task in scenario.get(
            "tasks",
            [],
        ):

            task_id = task.get(
                "id"
            )

            before = baseline_tasks.get(
                task_id
            )

            if not before:
                affected.append(
                    task
                )
                continue

            if before != task:
                affected.append(
                    task
                )

        return affected

    def _find_affected_projects(
        self,
        baseline: Dict[str, Any],
        scenario: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        baseline_projects = {
            project.get("id"): project
            for project in baseline.get(
                "projects",
                [],
            )
        }

        affected = []

        for project in scenario.get(
            "projects",
            [],
        ):

            project_id = project.get(
                "id"
            )

            before = baseline_projects.get(
                project_id
            )

            if not before:
                affected.append(
                    project
                )
                continue

            if before != project:
                affected.append(
                    project
                )

        return affected

    # ================================================================
    # INVALID ASSIGNMENTS
    # ================================================================

    def _find_invalid_assignments(
        self,
        state: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        employees = {
            employee.get("id"): employee
            for employee in state.get(
                "employees",
                [],
            )
        }

        invalid = []

        for assignment in state.get(
            "assignments",
            [],
        ):

            employee_id = assignment.get(
                "employee_id"
            )

            employee = employees.get(
                employee_id
            )

            if not employee:
                invalid.append(
                    assignment
                )
                continue

            if not employee.get(
                "available",
                True,
            ):
                invalid.append(
                    assignment
                )

        return invalid

    # ================================================================
    # HELPERS
    # ================================================================

    @staticmethod
    def _find_employee(
        state: Dict[str, Any],
        employee_id: Any,
    ) -> Optional[Dict[str, Any]]:

        for employee in state.get(
            "employees",
            [],
        ):

            if employee.get(
                "id"
            ) == employee_id:

                return employee

        return None

    @staticmethod
    def _find_by_id(
        items: List[Dict[str, Any]],
        item_id: Any,
    ) -> Optional[Dict[str, Any]]:

        for item in items:

            if item.get(
                "id"
            ) == item_id:

                return item

        return None

    @staticmethod
    def _number(
        value: Any,
        default: float = 0,
    ) -> float:

        try:
            return float(value)
        except (
            TypeError,
            ValueError,
        ):
            return float(default)

    @staticmethod
    def _generate_simulation_id(
        scenario: Dict[str, Any],
    ) -> str:

        scenario_type = str(
            scenario.get(
                "type",
                "simulation",
            )
        ).upper()

        # Deterministic ID suitable for demo/testing.
        return (
            f"SIM-{scenario_type[:12]}"
        )


# ====================================================================
# CONVENIENCE FUNCTION
# ====================================================================

def run_simulation(
    workforce_state: Dict[str, Any],
    scenario: Dict[str, Any],
    allocation_engine=None,
) -> Dict[str, Any]:
    """
    Convenience wrapper for API/service usage.
    """

    engine = SimulationEngine(
        allocation_engine=allocation_engine
    )

    return engine.run_simulation(
        workforce_state=workforce_state,
        scenario=scenario,
    )
