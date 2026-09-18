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
    }
