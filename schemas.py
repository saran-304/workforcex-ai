"""
WORKFORCEX AI
Pydantic API Schemas

These schemas define validated request/response objects used by
the FastAPI backend and Streamlit frontend.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# COMMON
# ============================================================

class APIResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[Any] = None


# ============================================================
# AUTHENTICATION
# ============================================================

class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class LoginResponse(BaseModel):
    success: bool
    message: str
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    organization_id: Optional[int] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    organization_id: int
    employee_id: Optional[int] = None
    is_active: bool


# ============================================================
# ORGANIZATION
# ============================================================

class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    industry: str


# ============================================================
# TEAM
# ============================================================

class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    department: str
    location: str
    manager_name: Optional[str] = None


# ============================================================
# SKILLS
# ============================================================

class SkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    name: str
    category: str
    description: Optional[str] = None


class EmployeeSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    skill_id: int
    proficiency: float
    years_experience: float
    last_used_year: Optional[int] = None


class RequiredSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    skill_id: int
    required_proficiency: float
    importance: float


# ============================================================
# EMPLOYEES
# ============================================================

class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    team_id: Optional[int] = None
    employee_code: str
    name: str
    email: str
    role: str
    location: str
    availability_status: str
    weekly_capacity_hours: float
    current_workload_hours: float
    utilization: float
    performance_score: float
    years_experience: float
    is_active: bool


class EmployeeDetailResponse(EmployeeResponse):
    skills: List[EmployeeSkillResponse] = []


class EmployeeUpdateRequest(BaseModel):
    availability_status: Optional[str] = None
    weekly_capacity_hours: Optional[float] = Field(
        default=None,
        ge=0,
        le=168,
    )
    current_workload_hours: Optional[float] = Field(
        default=None,
        ge=0,
    )
    location: Optional[str] = None
    is_active: Optional[bool] = None


# ============================================================
# PROJECTS
# ============================================================

class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    team_id: Optional[int] = None
    project_code: str
    name: str
    description: Optional[str] = None
    priority: str
    priority_score: float
    status: str
    start_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    budget_hours: float


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = None
    priority: str = "medium"
    priority_score: float = Field(
        default=50,
        ge=0,
        le=100,
    )
    team_id: Optional[int] = None
    deadline: Optional[datetime] = None
    budget_hours: float = Field(
        default=100,
        gt=0,
    )


class ProjectUpdateRequest(BaseModel):
    priority: Optional[str] = None
    priority_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )
    status: Optional[str] = None
    deadline: Optional[datetime] = None


# ============================================================
# TASKS
# ============================================================

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    project_id: Optional[int] = None
    task_code: str
    title: str
    description: Optional[str] = None
    priority: str
    priority_score: float
    status: str
    complexity: float
    estimated_hours: float
    remaining_hours: float
    deadline: Optional[datetime] = None
    location_required: Optional[str] = None


class TaskCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=250)
    description: Optional[str] = None
    project_id: Optional[int] = None

    priority: str = "medium"

    priority_score: float = Field(
        default=50,
        ge=0,
        le=100,
    )

    complexity: float = Field(
        default=50,
        ge=0,
        le=100,
    )

    estimated_hours: float = Field(
        default=8,
        gt=0,
        le=1000,
    )

    remaining_hours: Optional[float] = Field(
        default=None,
        ge=0,
    )

    deadline: Optional[datetime] = None

    location_required: Optional[str] = None

    required_skills: List["TaskRequiredSkillInput"] = []


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=250,
    )

    priority: Optional[str] = None

    priority_score: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    status: Optional[str] = None

    complexity: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
    )

    remaining_hours: Optional[float] = Field(
        default=None,
        ge=0,
    )

    deadline: Optional[datetime] = None


class TaskRequiredSkillInput(BaseModel):
    skill_id: int = Field(gt=0)

    required_proficiency: float = Field(
        default=50,
        ge=0,
        le=100,
    )

    importance: float = Field(
        default=1.0,
        gt=0,
        le=10,
    )


# ============================================================
# ASSIGNMENTS
# ============================================================

class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    employee_id: int
    assigned_hours: float
    allocation_percentage: float
    status: str
    assigned_at: datetime
    completed_at: Optional[datetime] = None
    assignment_reason: Optional[str] = None
    score: Optional[float] = None


class AssignmentRequest(BaseModel):
    task_id: int = Field(gt=0)
    employee_id: int = Field(gt=0)

    assigned_hours: Optional[float] = Field(
        default=None,
        gt=0,
    )


# ============================================================
# AVAILABILITY
# ============================================================

class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    start_date: datetime
    end_date: datetime
    status: str
    available_hours: float
    reason: Optional[str] = None


class AvailabilityUpdateRequest(BaseModel):
    employee_id: int = Field(gt=0)

    start_date: datetime
    end_date: datetime

    status: str

    available_hours: float = Field(
        default=40,
        ge=0,
        le=168,
    )

    reason: Optional[str] = None


# ============================================================
# SLA
# ============================================================

class SLAResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    target_hours: float
    remaining_hours: float
    status: str
    risk_score: float
    breach_at: Optional[datetime] = None


# ============================================================
# ALLOCATION ENGINE
# ============================================================

class CandidateScore(BaseModel):
    employee_id: int
    employee_name: str
    employee_code: str

    overall_score: float

    skill_match_score: float
    proficiency_score: float
    capacity_score: float
    workload_score: float
    urgency_score: float
    sla_score: float
    project_priority_score: float
    dependency_score: float
    location_score: float
    performance_score: float

    available_capacity_hours: float
    current_workload_hours: float
    utilization: float

    exact_skill_matches: List[str] = []
    adjacent_skill_matches: List[str] = []
    missing_skills: List[str] = []

    risk_before: float = 0
    predicted_risk_after: float = 0

    reasons: List[str] = []
    rejection_reasons: List[str] = []


class AllocationRequest(BaseModel):
    task_id: int = Field(gt=0)

    max_candidates: int = Field(
        default=10,
        ge=1,
        le=50,
    )


class AllocationResponse(BaseModel):
    success: bool
    task_id: int
    selected_candidate: Optional[CandidateScore] = None
    candidates: List[CandidateScore] = []
    explanation: str = ""


# ============================================================
# REALLOCATION
# ============================================================

class ReallocationRequest(BaseModel):
    employee_id: int = Field(gt=0)

    reason: str = Field(
        default="Employee became unavailable",
        min_length=1,
        max_length=500,
    )

    require_approval: bool = True


class ReallocationCandidate(BaseModel):
    task_id: int
    task_code: str
    task_title: str

    old_employee_id: int
    old_employee_name: str

    new_employee_id: int
    new_employee_name: str

    score: float

    risk_before: float
    risk_after: float

    reason: str


class ReallocationPlan(BaseModel):
    success: bool
    affected_employee_id: int

    affected_tasks: List[int] = []

    candidates: List[ReallocationCandidate] = []

    total_tasks: int = 0

    risk_before: float = 0
    risk_after: float = 0

    requires_approval: bool = True

    explanation: str = ""


# ============================================================
# RISK
# ============================================================

class RiskItem(BaseModel):
    risk_type: str
    severity: str
    score: float

    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None

    reason: str
    recommended_action: str

    affected_tasks: List[int] = []
    affected_projects: List[int] = []


class RiskSummary(BaseModel):
    total_risks: int
    critical_risks: int
    high_risks: int
    medium_risks: int
    low_risks: int

    average_risk: float

    risks: List[RiskItem] = []


# ============================================================
# SLA RISK
# ============================================================

class SLARiskItem(BaseModel):
    task_id: int
    task_code: str
    task_title: str

    project_id: Optional[int] = None
    project_name: Optional[str] = None

    deadline: Optional[datetime] = None

    sla_status: str
    risk_score: float

    remaining_hours: float

    assigned_employee_id: Optional[int] = None
    assigned_employee_name: Optional[str] = None

    reason: str
    recommended_mitigation: str


class SLARiskSummary(BaseModel):
    total_at_risk: int
    critical: int
    high: int
    medium: int

    items: List[SLARiskItem] = []


# ============================================================
# SIMULATION
# ============================================================

class SimulationChange(BaseModel):
    change_type: str

    employee_id: Optional[int] = None
    task_id: Optional[int] = None
    project_id: Optional[int] = None

    value: Optional[Any] = None

    duration_hours: Optional[float] = None


class SimulationRequest(BaseModel):
    name: str = Field(
        default="Workforce Scenario",
        min_length=1,
        max_length=200,
    )

    scenario_type: str

    changes: List[SimulationChange] = []

    strategies: List[str] = [
        "Keep Current Assignments",
        "Reallocate Suitable Employees",
        "Reallocate + Delay Lower Priority Work",
    ]


class StrategyResult(BaseModel):
    strategy_name: str

    affected_employees: List[int] = []
    affected_tasks: List[int] = []
    affected_projects: List[int] = []

    capacity_before: float
    capacity_after: float

    utilization_before: float
    utilization_after: float

    risk_before: float
    risk_after: float

    risk_change: float

    sla_risk_before: float
    sla_risk_after: float

    sla_change: float

    dependency_impact: List[str] = []

    recommendation: str = ""


class SimulationResponse(BaseModel):
    success: bool

    scenario_id: Optional[int] = None

    scenario_type: str

    baseline_summary: Dict[str, Any] = {}

    scenario_summary: Dict[str, Any] = {}

    strategies: List[StrategyResult] = []

    recommended_strategy: Optional[str] = None

    explanation: str = ""


# ============================================================
# CRISIS MODE
# ============================================================

class CrisisRequest(BaseModel):
    crisis_type: str = Field(
        min_length=1,
        max_length=100,
    )

    affected_employee_ids: List[int] = []

    affected_task_ids: List[int] = []

    demand_increase_percentage: float = Field(
        default=0,
        ge=0,
        le=1000,
    )

    deadline_acceleration_hours: float = Field(
        default=0,
        ge=0,
    )

    description: Optional[str] = None


class CrisisImpact(BaseModel):
    affected_employees: List[int] = []
    affected_tasks: List[int] = []
    affected_projects: List[int] = []

    capacity_lost_hours: float = 0

    utilization_change: float = 0

    risk_before: float = 0
    risk_after: float = 0

    sla_risk_before: float = 0
    sla_risk_after: float = 0

    skill_shortages: List[str] = []
    critical_dependencies: List[int] = []


class RecoveryStrategy(BaseModel):
    strategy_name: str

    description: str

    actions: List[str] = []

    expected_risk: float = 0

    expected_sla_risk: float = 0

    expected_capacity_recovery: float = 0

    approval_required: bool = True


class CrisisResponse(BaseModel):
    success: bool

    crisis_id: Optional[int] = None

    stage: str

    impact: CrisisImpact

    strategies: List[RecoveryStrategy] = []

    recommended_strategy: Optional[str] = None

    timeline: List[str] = []

    explanation: str = ""


# ============================================================
# POLICY
# ============================================================

class PolicyCheckRequest(BaseModel):
    action_type: str

    employee_ids: List[int] = []
    task_ids: List[int] = []
    project_ids: List[int] = []

    proposed_changes: Dict[str, Any] = {}


class PolicyCheckResult(BaseModel):
    allowed: bool

    requires_approval: bool

    risk_level: str

    violations: List[str] = []

    warnings: List[str] = []

    explanation: str = ""


# ============================================================
# APPROVAL
# ============================================================

class ApprovalCreateRequest(BaseModel):
    action_type: str

    action_payload: Dict[str, Any]

    reason: Optional[str] = None

    risk_before: float = 0

    risk_after: float = 0

    simulation_result: Optional[Dict[str, Any]] = None

    affected_resources: List[str] = []


class ApprovalResponse(BaseModel):
    id: int
    organization_id: int
    action_type: str
    action_payload: Dict[str, Any]
    reason: Optional[str] = None

    risk_before: float
    risk_after: float

    simulation_result: Optional[Any] = None

    affected_resources: List[str] = []

    status: str

    requested_by: Optional[int] = None
    reviewed_by: Optional[int] = None

    reviewed_at: Optional[datetime] = None
    created_at: datetime


class ApprovalDecisionRequest(BaseModel):
    decision: str

    comment: Optional[str] = None


# ============================================================
# AUDIT
# ============================================================

class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    user_id: Optional[int] = None

    action: str

    resource_type: Optional[str] = None
    resource_id: Optional[str] = None

    before_state: Optional[str] = None
    decision_evidence: Optional[str] = None
    ai_recommendation: Optional[str] = None
    simulation_result: Optional[str] = None
    approval_decision: Optional[str] = None
    after_state: Optional[str] = None

    created_at: datetime


# ============================================================
# COPILOT
# ============================================================

class CopilotRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=5000,
    )

    conversation_id: Optional[str] = None


class CopilotToolCall(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


class CopilotEvidence(BaseModel):
    source_type: str
    source_id: Optional[str] = None
    title: str
    information: str


class CopilotActionPreview(BaseModel):
    action_type: str

    requires_approval: bool

    risk_level: str

    affected_resources: List[str] = []

    proposed_changes: Dict[str, Any] = {}


class CopilotResponse(BaseModel):
    success: bool

    answer: str

    tool_calls: List[CopilotToolCall] = []

    evidence: List[CopilotEvidence] = []

    action_preview: Optional[CopilotActionPreview] = None

    ai_available: bool = False


# ============================================================
# WORKFORCE DIGITAL TWIN
# ============================================================

class WorkforceSummary(BaseModel):
    total_employees: int

    available_employees: int
    unavailable_employees: int

    total_capacity_hours: float
    available_capacity_hours: float

    current_workload_hours: float

    utilization_percentage: float

    active_projects: int
    active_tasks: int

    critical_tasks: int

    sla_risk_count: int

    critical_risk_count: int

    skill_gap_count: int


class WorkforceEmployeeState(BaseModel):
    employee_id: int
    employee_code: str
    employee_name: str

    team: Optional[str] = None

    availability: str

    capacity_hours: float
    workload_hours: float
    available_hours: float

    utilization: float

    performance_score: float

    skills: List[str] = []


class WorkforceStateResponse(BaseModel):
    summary: WorkforceSummary

    employees: List[WorkforceEmployeeState] = []

    generated_at: datetime


# ============================================================
# DASHBOARD
# ============================================================

class DashboardResponse(BaseModel):
    workforce: WorkforceSummary

    top_risks: List[RiskItem] = []

    sla_risks: List[SLARiskItem] = []

    pending_approvals: int = 0

    recent_audit_events: List[AuditLogResponse] = []

    generated_at: datetime


# ============================================================
# PAGINATION
# ============================================================

class PaginationResponse(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


# ============================================================
# ERROR
# ============================================================

class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None


# ============================================================
# PYDANTIC FORWARD REFERENCES
# ============================================================

TaskCreateRequest.model_rebuild()
