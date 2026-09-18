"""
WORKFORCEX AI
Realistic Demo Data Seeder

Creates:

- 1 organization
- 5 users
- 50 employees
- 20 skills
- Employee skill relationships
- 10 projects
- 100 tasks
- Task dependencies
- Assignments
- Availability records
- Workload/capacity data
- SLA information
- Historical performance data

Run:

    python seed.py

The script is safe to run repeatedly because it resets the
WORKFORCEX prototype database before creating fresh demo data.
"""

import random
from datetime import datetime, timedelta

from database import Base, engine, SessionLocal
from models import (
    Organization,
    User,
    Employee,
    Team,
    Skill,
    EmployeeSkill,
    Project,
    Task,
    TaskDependency,
    Assignment,
    Availability,
    SLA,
)


# ============================================================
# CONFIGURATION
# ============================================================

random.seed(42)

TODAY = datetime.utcnow().replace(
    hour=9,
    minute=0,
    second=0,
    microsecond=0,
)


# ============================================================
# DEMO ORGANIZATION
# ============================================================

ORGANIZATION_NAME = "NOVATECH INDUSTRIES"


# ============================================================
# TEAMS
# ============================================================

TEAM_DATA = [
    ("Backend Engineering", "Software"),
    ("Frontend Engineering", "Software"),
    ("Data & AI", "Technology"),
    ("Cloud & DevOps", "Technology"),
    ("Cybersecurity", "Security"),
    ("QA & Testing", "Engineering"),
    ("Product Engineering", "Engineering"),
    ("Operations", "Operations"),
    ("Manufacturing Systems", "Operations"),
    ("Technical Support", "Support"),
]


# ============================================================
# SKILLS
# ============================================================

SKILL_DATA = [
    ("Python", "Software"),
    ("FastAPI", "Software"),
    ("JavaScript", "Software"),
    ("React", "Software"),
    ("TypeScript", "Software"),
    ("SQL", "Data"),
    ("PostgreSQL", "Data"),
    ("Machine Learning", "AI"),
    ("Data Engineering", "Data"),
    ("AWS", "Cloud"),
    ("Docker", "Cloud"),
    ("Kubernetes", "Cloud"),
    ("CI/CD", "DevOps"),
    ("Cybersecurity", "Security"),
    ("Network Security", "Security"),
    ("Testing", "Quality"),
    ("Automation Testing", "Quality"),
    ("Project Management", "Management"),
    ("Embedded Systems", "Electronics"),
    ("IoT", "Electronics"),
]


# ============================================================
# PROJECTS
# ============================================================

PROJECT_DATA = [
    (
        "Cloud Migration Platform",
        "Move critical workloads to the cloud.",
        "Critical",
    ),
    (
        "AI Analytics Platform",
        "Enterprise analytics and ML platform.",
        "High",
    ),
    (
        "Customer Web Portal",
        "Modern customer-facing web platform.",
        "High",
    ),
    (
        "Cybersecurity Upgrade",
        "Improve enterprise security controls.",
        "Critical",
    ),
    (
        "IoT Monitoring System",
        "Real-time industrial IoT monitoring.",
        "High",
    ),
    (
        "Mobile Operations App",
        "Mobile application for field operations.",
        "Medium",
    ),
    (
        "Data Warehouse Modernization",
        "Modernize enterprise data infrastructure.",
        "High",
    ),
    (
        "Automated QA Program",
        "Increase automated software testing.",
        "Medium",
    ),
    (
        "Manufacturing Dashboard",
        "Operational manufacturing dashboard.",
        "Medium",
    ),
    (
        "Enterprise Support System",
        "Centralized technical support platform.",
        "Medium",
    ),
]


# ============================================================
# EMPLOYEE FIRST NAMES
# ============================================================

FIRST_NAMES = [
    "Arun",
    "Rahul",
    "Karthik",
    "Vikram",
    "Aditya",
    "Ravi",
    "Pranav",
    "Naveen",
    "Sanjay",
    "Surya",
    "Ajay",
    "Vishal",
    "Dinesh",
    "Manoj",
    "Harish",
    "Gokul",
    "Hari",
    "Mohan",
    "Aravind",
    "Sathish",
    "Deepak",
    "Nithin",
    "Akash",
    "Rohit",
    "Varun",
    "Anand",
    "Suresh",
    "Ramesh",
    "Prakash",
    "Bala",
    "Kavin",
    "Lokesh",
    "Dharshan",
    "Siddharth",
    "Yash",
    "Abhishek",
    "Vignesh",
    "Suraj",
    "Nikhil",
    "Madhan",
    "Keerthivasan",
    "Manikandan",
    "Vijay",
    "Ashwin",
    "Santhosh",
    "Gautham",
    "Ranjith",
    "Sriram",
    "Tarun",
    "Varsha",
]


LAST_NAMES = [
    "Kumar",
    "Sharma",
    "Raj",
    "Singh",
    "Patel",
    "Iyer",
    "Reddy",
    "Nair",
    "Menon",
    "Das",
]


# ============================================================
# LOCATIONS
# ============================================================

LOCATIONS = [
    "Coimbatore",
    "Chennai",
    "Bangalore",
    "Hyderabad",
    "Pune",
]


# ============================================================
# TASK TITLES
# ============================================================

TASK_TEMPLATES = [
    "Implement API integration",
    "Develop authentication module",
    "Build analytics dashboard",
    "Fix production issue",
    "Create database migration",
    "Develop automated tests",
    "Configure cloud infrastructure",
    "Review security configuration",
    "Build machine learning pipeline",
    "Develop IoT data ingestion",
    "Optimize database queries",
    "Create deployment pipeline",
    "Investigate system failure",
    "Implement monitoring service",
    "Develop frontend module",
    "Perform security audit",
    "Create data processing workflow",
    "Configure CI/CD pipeline",
    "Resolve customer issue",
    "Implement notification service",
]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def random_name(index: int) -> str:
    """
    Generate deterministic employee names.
    """

    first = FIRST_NAMES[index % len(FIRST_NAMES)]

    last = LAST_NAMES[
        (index // len(FIRST_NAMES))
        % len(LAST_NAMES)
    ]

    return f"{first} {last}"


def random_email(name: str, index: int) -> str:
    """
    Generate unique demo email.
    """

    normalized = (
        name.lower()
        .replace(" ", ".")
    )

    return f"{normalized}.{index + 1}@novatech.example"


def required_skill_for_task(task_index: int) -> int:
    """
    Map tasks to skills.

    This intentionally creates skill demand patterns so
    the allocation engine has meaningful decisions.
    """

    skill_cycle = [
        0,   # Python
        1,   # FastAPI
        2,   # JavaScript
        3,   # React
        4,   # TypeScript
        5,   # SQL
        6,   # PostgreSQL
        7,   # ML
        8,   # Data Engineering
        9,   # AWS
        10,  # Docker
        11,  # Kubernetes
        12,  # CI/CD
        13,  # Cybersecurity
        14,  # Network Security
        15,  # Testing
        16,  # Automation Testing
        17,  # Project Management
        18,  # Embedded Systems
        19,  # IoT
    ]

    return skill_cycle[
        task_index % len(skill_cycle)
    ]


def priority_for_task(task_index: int) -> str:
    """
    Generate realistic task priorities.
    """

    if task_index % 17 == 0:
        return "Critical"

    if task_index % 5 == 0:
        return "High"

    if task_index % 3 == 0:
        return "Medium"

    return "Low"


def task_complexity(task_index: int) -> int:
    """
    Complexity from 1 to 10.
    """

    return (
        task_index * 7
    ) % 10 + 1


# ============================================================
# RESET DATABASE
# ============================================================

def reset_database():
    """
    Recreate all database tables.

    This gives the hackathon a clean deterministic demo state.
    """

    print("Resetting WORKFORCEX database...")

    Base.metadata.drop_all(
        bind=engine
    )

    Base.metadata.create_all(
        bind=engine
    )

    print("Database reset complete.")


# ============================================================
# CREATE ORGANIZATION
# ============================================================

def create_organization(db):
    organization = Organization(
        name=ORGANIZATION_NAME,
        industry="Technology",
        description=(
            "Demo enterprise organization for "
            "WORKFORCEX AI workforce intelligence."
        ),
        is_active=True,
    )

    db.add(organization)
    db.flush()

    return organization


# ============================================================
# CREATE TEAMS
# ============================================================

def create_teams(db, organization):
    teams = []

    for name, department in TEAM_DATA:

        team = Team(
            organization_id=organization.id,
            name=name,
            department=department,
            description=(
                f"{name} team at "
                f"{ORGANIZATION_NAME}."
            ),
        )

        db.add(team)
        teams.append(team)

    db.flush()

    return teams


# ============================================================
# CREATE SKILLS
# ============================================================

def create_skills(db, organization):
    skills = []

    for name, category in SKILL_DATA:

        skill = Skill(
            organization_id=organization.id,
            name=name,
            category=category,
            description=(
                f"{name} capability."
            ),
        )

        db.add(skill)
        skills.append(skill)

    db.flush()

    return skills


# ============================================================
# CREATE EMPLOYEES
# ============================================================

def create_employees(
    db,
    organization,
    teams,
    skills,
):
    employees = []

    for i in range(50):

        team = teams[
            i % len(teams)
        ]

        # Intentionally create different workloads.
        if i < 5:
            workload = random.randint(
                85,
                98,
            )

            capacity = random.randint(
                80,
                100,
            )

        elif i < 10:
            workload = random.randint(
                65,
                85,
            )

            capacity = random.randint(
                80,
                100,
            )

        else:
            workload = random.randint(
                20,
                75,
            )

            capacity = random.randint(
                70,
                100,
            )

        # A few intentionally unavailable employees.
        if i in [7, 23]:
            availability_status = "Unavailable"

        elif i in [14, 31]:
            availability_status = "Partial"

        else:
            availability_status = "Available"

        employee = Employee(
            organization_id=organization.id,
            team_id=team.id,
            employee_code=f"E{100 + i}",
            name=random_name(i),
            email=random_email(
                random_name(i),
                i,
            ),
            role=(
                "Senior Engineer"
                if i % 7 == 0
                else "Engineer"
            ),
            location=LOCATIONS[
                i % len(LOCATIONS)
            ],
            availability_status=availability_status,
            capacity_percent=capacity,
            current_workload_percent=workload,
            historical_performance=round(
                random.uniform(
                    0.65,
                    0.98,
                ),
                2,
            ),
            is_active=True,
        )

        db.add(employee)
        employees.append(employee)

    db.flush()

    return employees


# ============================================================
# CREATE EMPLOYEE SKILLS
# ============================================================

def create_employee_skills(
    db,
    employees,
    skills,
):
    employee_skills = []

    for index, employee in enumerate(
        employees
    ):

        # Every employee receives 4–7 skills.
        number_of_skills = (
            4 + index % 4
        )

        selected_skills = []

        # Give some teams stronger alignment
        # with their primary skill families.
        primary_skill = (
            index
            % len(skills)
        )

        selected_skills.append(
            skills[primary_skill]
        )

        while len(selected_skills) < number_of_skills:

            skill = random.choice(skills)

            if skill not in selected_skills:
                selected_skills.append(skill)

        for skill in selected_skills:

            proficiency = random.randint(
                1,
                5,
            )

            # Ensure primary skill is usually strong.
            if skill == skills[primary_skill]:
                proficiency = random.randint(
                    4,
                    5,
                )

            relationship = EmployeeSkill(
                employee_id=employee.id,
                skill_id=skill.id,
                proficiency=proficiency,
                years_experience=round(
                    random.uniform(
                        0.5,
                        8.0,
                    ),
                    1,
                ),
                is_primary=(
                    skill == skills[primary_skill]
                ),
            )

            db.add(relationship)
            employee_skills.append(
                relationship
            )

    db.flush()

    return employee_skills


# ============================================================
# CREATE USERS
# ============================================================

def create_users(
    db,
    organization,
    employees,
):
    """
    Create demo application users.

    Demo password for all users:

        password123
    """

    from auth import hash_password

    users = []

    user_definitions = [
        (
            "admin",
            "Organization Admin",
            employees[0],
        ),
        (
            "manager",
            "Workforce Manager",
            employees[1],
        ),
        (
            "projectmanager",
            "Project Manager",
            employees[2],
        ),
        (
            "teamlead",
            "Team Lead",
            employees[3],
        ),
        (
            "employee",
            "Employee",
            employees[4],
        ),
    ]

    for username, role, employee in user_definitions:

        user = User(
            organization_id=organization.id,
            employee_id=employee.id,
            username=username,
            password_hash=hash_password(
                "password123"
            ),
            role=role,
            is_active=True,
        )

        db.add(user)
        users.append(user)

    db.flush()

    return users


# ============================================================
# CREATE PROJECTS
# ============================================================

def create_projects(
    db,
    organization,
):
    projects = []

    for index, (
        name,
        description,
        priority,
    ) in enumerate(
        PROJECT_DATA
    ):

        start_date = TODAY - timedelta(
            days=random.randint(
                10,
                60,
            )
        )

        deadline = TODAY + timedelta(
            days=random.randint(
                7,
                60,
            )
        )

        # Make a few projects intentionally urgent.
        if index == 0:
            deadline = TODAY + timedelta(
                days=7
            )

        if index == 3:
            deadline = TODAY + timedelta(
                days=10
            )

        project = Project(
            organization_id=organization.id,
            name=name,
            description=description,
            priority=priority,
            status="Active",
            start_date=start_date,
            deadline=deadline,
        )

        db.add(project)
        projects.append(project)

    db.flush()

    return projects


# ============================================================
# CREATE TASKS
# ============================================================

def create_tasks(
    db,
    organization,
    projects,
    skills,
):
    tasks = []

    for index in range(100):

        project = projects[
            index % len(projects)
        ]

        priority = priority_for_task(
            index
        )

        complexity = task_complexity(
            index
        )

        required_skill = skills[
            required_skill_for_task(
                index
            )
        ]

        # Make critical tasks have tighter deadlines.
        if priority == "Critical":
            due_date = TODAY + timedelta(
                days=random.randint(
                    1,
                    5,
                )
            )

            sla_hours = random.choice(
                [8, 12, 24]
            )

        elif priority == "High":
            due_date = TODAY + timedelta(
                days=random.randint(
                    3,
                    12,
                )
            )

            sla_hours = random.choice(
                [24, 48, 72]
            )

        else:
            due_date = TODAY + timedelta(
                days=random.randint(
                    7,
                    30,
                )
            )

            sla_hours = random.choice(
                [48, 72, 120]
            )

        title_template = TASK_TEMPLATES[
            index
            % len(TASK_TEMPLATES)
        ]

        task = Task(
            organization_id=organization.id,
            project_id=project.id,
            title=(
                f"{title_template} "
                f"#{index + 1:03d}"
            ),
            description=(
                f"Operational task for "
                f"{project.name}."
            ),
            priority=priority,
            status="Open",
            complexity=complexity,
            required_skill_id=required_skill.id,
            required_proficiency=(
                4
                if priority in {
                    "Critical",
                    "High",
                }
                else 3
            ),
            estimated_hours=random.randint(
                2,
                24,
            ),
            due_date=due_date,
        )

        db.add(task)
        tasks.append(task)

        # SLA created separately after task exists.

    db.flush()

    return tasks


# ============================================================
# CREATE SLAs
# ============================================================

def create_slas(
    db,
    organization,
    tasks,
):
    slas = []

    for index, task in enumerate(tasks):

        created_at = TODAY - timedelta(
            hours=random.randint(
                2,
                48,
            )
        )

        if task.priority == "Critical":
            target_hours = 12

        elif task.priority == "High":
            target_hours = 24

        elif task.priority == "Medium":
            target_hours = 72

        else:
            target_hours = 120

        deadline = created_at + timedelta(
            hours=target_hours
        )

        # Intentionally create SLA-risk tasks.
        if index in [3, 12, 28, 47, 71, 89]:

            deadline = TODAY + timedelta(
                hours=random.randint(
                    1,
                    6,
                )
            )

        sla = SLA(
            organization_id=organization.id,
            task_id=task.id,
            target_hours=target_hours,
            created_at=created_at,
            deadline=deadline,
            status="At Risk"
            if deadline <= TODAY + timedelta(
                hours=12
            )
            else "On Track",
        )

        db.add(sla)
        slas.append(sla)

    db.flush()

    return slas


# ============================================================
# CREATE AVAILABILITY
# ============================================================

def create_availability(
    db,
    organization,
    employees,
):
    availability_records = []

    for index, employee in enumerate(
        employees
    ):

        if employee.availability_status == "Unavailable":

            available_percent = 0

        elif employee.availability_status == "Partial":

            available_percent = random.randint(
                20,
                50,
            )

        else:

            available_percent = random.randint(
                60,
                100,
            )

        record = Availability(
            organization_id=organization.id,
            employee_id=employee.id,
            date=TODAY.date(),
            availability_percent=available_percent,
            status=employee.availability_status,
            notes=(
                "Demo availability record."
            ),
        )

        db.add(record)
        availability_records.append(
            record
        )

    db.flush()

    return availability_records


# ============================================================
# CREATE ASSIGNMENTS
# ============================================================

def create_assignments(
    db,
    organization,
    employees,
    tasks,
):
    assignments = []

    for index, task in enumerate(
        tasks
    ):

        # Leave some tasks intentionally unassigned.
        if index % 11 == 0:
            continue

        employee = employees[
            (index * 7)
            % len(employees)
        ]

        assignment = Assignment(
            organization_id=organization.id,
            task_id=task.id,
            employee_id=employee.id,
            allocation_percent=random.randint(
                10,
                40,
            ),
            status="Active",
            assigned_at=TODAY - timedelta(
                days=random.randint(
                    0,
                    15,
                )
            ),
        )

        db.add(assignment)
        assignments.append(assignment)

    db.flush()

    return assignments


# ============================================================
# CREATE TASK DEPENDENCIES
# ============================================================

def create_dependencies(
    db,
    organization,
    tasks,
):
    dependencies = []

    for index in range(
        1,
        len(tasks),
    ):

        # Approximately 20% of tasks get dependencies.
        if index % 5 != 0:
            continue

        parent_index = index - (
            1 + index % 4
        )

        if parent_index < 0:
            continue

        parent_task = tasks[
            parent_index
        ]

        child_task = tasks[
            index
        ]

        if parent_task.id == child_task.id:
            continue

        dependency = TaskDependency(
            organization_id=organization.id,
            predecessor_task_id=parent_task.id,
            successor_task_id=child_task.id,
            dependency_type="Finish-to-Start",
        )

        db.add(dependency)
        dependencies.append(
            dependency
        )

    db.flush()

    return dependencies


# ============================================================
# MAIN SEED FUNCTION
# ============================================================

def seed_database():

    print()
    print("=" * 60)
    print("WORKFORCEX AI DATABASE SEED")
    print("=" * 60)
    print()

    reset_database()

    db = SessionLocal()

    try:

        print("Creating organization...")

        organization = create_organization(
            db
        )

        print("Creating teams...")

        teams = create_teams(
            db,
            organization,
        )

        print(
            f"Created {len(teams)} teams."
        )

        print("Creating skills...")

        skills = create_skills(
            db,
            organization,
        )

        print(
            f"Created {len(skills)} skills."
        )

        print("Creating employees...")

        employees = create_employees(
            db,
            organization,
            teams,
            skills,
        )

        print(
            f"Created {len(employees)} employees."
        )

        print("Creating employee skills...")

        employee_skills = (
            create_employee_skills(
                db,
                employees,
                skills,
            )
        )

        print(
            f"Created {len(employee_skills)} "
            "employee-skill relationships."
        )

        print("Creating users...")

        users = create_users(
            db,
            organization,
            employees,
        )

        print(
            f"Created {len(users)} users."
        )

        print("Creating projects...")

        projects = create_projects(
            db,
            organization,
        )

        print(
            f"Created {len(projects)} projects."
        )

        print("Creating tasks...")

        tasks = create_tasks(
            db,
            organization,
            projects,
            skills,
        )

        print(
            f"Created {len(tasks)} tasks."
        )

        print("Creating SLAs...")

        slas = create_slas(
            db,
            organization,
            tasks,
        )

        print(
            f"Created {len(slas)} SLA records."
        )

        print("Creating availability...")

        availability = create_availability(
            db,
            organization,
            employees,
        )

        print(
            f"Created {len(availability)} "
            "availability records."
        )

        print("Creating assignments...")

        assignments = create_assignments(
            db,
            organization,
            employees,
            tasks,
        )

        print(
            f"Created {len(assignments)} assignments."
        )

        print("Creating task dependencies...")

        dependencies = create_dependencies(
            db,
            organization,
            tasks,
        )

        print(
            f"Created {len(dependencies)} "
            "task dependencies."
        )

        db.commit()

        print()
        print("=" * 60)
        print("DATABASE SEED COMPLETE")
        print("=" * 60)
        print()

        print(
            f"Organization : {ORGANIZATION_NAME}"
        )
        print(
            f"Teams        : {len(teams)}"
        )
        print(
            f"Skills       : {len(skills)}"
        )
        print(
            f"Employees    : {len(employees)}"
        )
        print(
            f"Users        : {len(users)}"
        )
        print(
            f"Projects     : {len(projects)}"
        )
        print(
            f"Tasks        : {len(tasks)}"
        )
        print(
            f"Assignments  : {len(assignments)}"
        )
        print(
            f"SLAs         : {len(slas)}"
        )
        print(
            f"Dependencies : {len(dependencies)}"
        )

        print()
        print("Demo login accounts:")
        print()
        print(
            "admin / password123"
        )
        print(
            "manager / password123"
        )
        print(
            "projectmanager / password123"
        )
        print(
            "teamlead / password123"
        )
        print(
            "employee / password123"
        )

        print()
        print(
            "The demo dataset is ready for "
            "allocation, simulation, risk, "
            "reallocation and Copilot testing."
        )
        print()

    except Exception as exc:

        db.rollback()

        print()
        print(
            "DATABASE SEED FAILED:"
        )
        print(exc)
        print()

        raise

    finally:

        db.close()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    seed_database()
