"""LangGraph workflow state definitions."""

from typing import TypedDict, Annotated, Sequence, Optional, Any
from operator import add
from enum import Enum


class AgentRole(str, Enum):
    ORCHESTRATOR = "orchestrator"
    SPEC_ARCHITECT = "spec_architect"
    DEVELOPER = "developer"
    REVIEWER = "reviewer"
    QA = "qa"


class WorkflowPhase(str, Enum):
    INIT = "init"
    SPEC_WRITING = "spec_writing"
    SPEC_REVIEW = "spec_review"
    CODING = "coding"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    COMPLETE = "complete"
    ERROR = "error"


class Message(TypedDict):
    role: str
    content: str
    agent: Optional[str]


class FileOp(TypedDict):
    path: str
    content: str
    action: str  # "create", "update", "delete"


class ReviewResult(TypedDict):
    score: int  # 0-100
    issues: list[str]
    suggestions: list[str]
    passed: bool


class TestResult(TypedDict):
    total: int
    passed: int
    failed: int
    details: list[str]
    coverage: float


class AgentState(TypedDict):
    # Workflow control
    phase: WorkflowPhase
    messages: Annotated[Sequence[Message], add]

    # User input
    requirement: str
    project_context: str
    target_language: str  # default "python"

    # Spec phase outputs
    product_spec: Optional[str]
    architecture_spec: Optional[str]
    api_spec: Optional[str]
    spec_revision_count: int

    # Development phase outputs
    generated_files: Annotated[Sequence[FileOp], add]
    coding_iteration: int

    # Review phase outputs
    review_result: Optional[ReviewResult]
    review_iteration: int

    # QA phase outputs
    test_result: Optional[TestResult]
    test_iteration: int

    # Control
    max_iterations: int
    error_message: Optional[str]
    final_report: Optional[str]
