"""
Pydantic input schemas for tool validation.
"""

from typing import Optional, List, Literal
from enum import Enum

try:
    from pydantic import BaseModel, Field, model_validator, field_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Stub for when Pydantic is not available
    class BaseModel:
        pass
    def Field(*args, **kwargs):
        return None
    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator
    def model_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


class ThinkingLevel(str, Enum):
    """Reasoning depth. AUTO = model default (Gemini 3+ always thinks); OFF is a deprecated alias of AUTO."""
    AUTO = "auto"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    OFF = "off"


class CodeStyle(str, Enum):
    """Code generation style."""
    PRODUCTION = "production"
    PROTOTYPE = "prototype"
    MINIMAL = "minimal"


class AnalysisType(str, Enum):
    """Codebase analysis focus."""
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    DEPENDENCIES = "dependencies"
    GENERAL = "general"


class ChallengeFocus(str, Enum):
    """Challenge/critique focus area."""
    GENERAL = "general"
    SECURITY = "security"
    PERFORMANCE = "performance"
    MAINTAINABILITY = "maintainability"
    SCALABILITY = "scalability"
    COST = "cost"


class CodeReviewFocus(str, Enum):
    """Code review focus area."""
    GENERAL = "general"
    SECURITY = "security"
    PERFORMANCE = "performance"
    READABILITY = "readability"
    BUGS = "bugs"


class BrainstormMethodology(str, Enum):
    """Brainstorming framework."""
    AUTO = "auto"
    DIVERGENT = "divergent"
    CONVERGENT = "convergent"
    SCAMPER = "scamper"
    DESIGN_THINKING = "design-thinking"
    LATERAL = "lateral"


# =============================================================================
# INPUT SCHEMAS
# =============================================================================

class AskGeminiInput(BaseModel):
    """Schema for ask_gemini tool input."""

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=100000,
        description="The question or prompt for Gemini"
    )
    model: Literal["pro", "flash", "fast", "flash-lite"] = Field(
        default="pro",
        description="Model alias; the concrete ID is auto-detected (newest matching model the API exposes)"
    )
    temperature: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Sampling temperature"
    )
    thinking_level: ThinkingLevel = Field(
        default=ThinkingLevel.AUTO,
        description="Reasoning depth: auto (model default), low, medium, high"
    )
    include_thoughts: bool = Field(
        default=False,
        description="Include reasoning process in output"
    )
    continuation_id: Optional[str] = Field(
        default=None,
        description="Thread ID for conversation continuity"
    )


class GenerateCodeInput(BaseModel):
    """Schema for gemini_generate_code tool input."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="What code to generate"
    )
    context_files: Optional[List[str]] = Field(
        default=None,
        description="Files to include as context (@file syntax)"
    )
    language: Literal[
        "auto", "typescript", "javascript", "python",
        "rust", "go", "java", "cpp", "csharp", "html", "css", "sql"
    ] = Field(default="auto")
    style: CodeStyle = Field(default=CodeStyle.PRODUCTION)
    model: Literal["pro", "flash"] = Field(default="pro")
    output_dir: Optional[str] = Field(
        default=None,
        description="Directory to auto-save generated files"
    )

    @field_validator('context_files', mode='before')
    @classmethod
    def handle_null_context_files(cls, v):
        """Handle null from MCP protocol."""
        return v or []


class ChallengeInput(BaseModel):
    """Schema for gemini_challenge tool input."""

    statement: str = Field(
        ...,
        min_length=1,
        description="The idea/plan/code to critique"
    )
    context: str = Field(
        default="",
        description="Background context"
    )
    focus: ChallengeFocus = Field(default=ChallengeFocus.GENERAL)


class AnalyzeCodebaseInput(BaseModel):
    """Schema for gemini_analyze_codebase tool input."""

    prompt: str = Field(
        ...,
        min_length=1,
        description="Analysis task"
    )
    files: List[str] = Field(
        ...,
        min_length=1,
        description="File paths or glob patterns"
    )
    analysis_type: AnalysisType = Field(default=AnalysisType.GENERAL)
    model: Literal["pro", "flash"] = Field(default="pro")
    continuation_id: Optional[str] = Field(
        default=None,
        description="Thread ID for iterative analysis"
    )


class CodeReviewInput(BaseModel):
    """Schema for gemini_code_review tool input."""

    code: str = Field(
        ...,
        min_length=1,
        description="Code to review"
    )
    focus: CodeReviewFocus = Field(default=CodeReviewFocus.GENERAL)
    model: Literal["pro", "flash"] = Field(default="pro")


class BrainstormInput(BaseModel):
    """Schema for gemini_brainstorm tool input."""

    topic: str = Field(
        ...,
        min_length=1,
        description="Topic or challenge to brainstorm"
    )
    context: str = Field(
        default="",
        description="Additional context or background"
    )
    methodology: BrainstormMethodology = Field(default=BrainstormMethodology.AUTO)
    domain: Optional[str] = Field(
        default=None,
        description="Domain context: software, business, creative, etc."
    )
    constraints: Optional[str] = Field(
        default=None,
        description="Known limitations: budget, time, technical, etc."
    )
    idea_count: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Target number of ideas"
    )
    include_analysis: bool = Field(
        default=True,
        description="Include feasibility, impact scores"
    )


class DeepResearchInput(BaseModel):
    """Schema for gemini_deep_research tool input."""

    query: str = Field(
        default="",
        max_length=5000,
        description="Research topic or question (>= 10 chars). Empty with continuation_id = retrieve/resume that research."
    )
    max_wait_minutes: int = Field(
        default=30,
        ge=5,
        le=60,
        description="Maximum wait time in minutes (5-60)"
    )
    continuation_id: Optional[str] = Field(
        default=None,
        description="Previous interaction ID: retrieve it (empty query) or chain a follow-up (with query)"
    )

    @model_validator(mode="after")
    def _query_or_continuation(self):
        if self.query and len(self.query) < 10:
            raise ValueError("query must be at least 10 characters")
        if not self.query and not self.continuation_id:
            raise ValueError("provide a query or a continuation_id")
        return self


# =============================================================================
# VALIDATION HELPER
# =============================================================================

# Schema mapping for validation
TOOL_SCHEMAS = {
    "ask_gemini": AskGeminiInput,
    "gemini_generate_code": GenerateCodeInput,
    "gemini_challenge": ChallengeInput,
    "gemini_analyze_codebase": AnalyzeCodebaseInput,
    "gemini_code_review": CodeReviewInput,
    "gemini_brainstorm": BrainstormInput,
    "gemini_deep_research": DeepResearchInput,
}


def validate_tool_input(tool_name: str, args: dict) -> dict:
    """
    Validate and transform tool input using Pydantic schemas.

    Args:
        tool_name: Name of the tool
        args: Raw input arguments

    Returns:
        Validated and transformed arguments

    Raises:
        ValueError: If validation fails
    """
    if not PYDANTIC_AVAILABLE:
        return args

    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        return args

    try:
        validated = schema(**args)
        # Convert to dict, handling enums
        result = {}
        for key, value in validated.model_dump().items():
            if isinstance(value, Enum):
                result[key] = value.value
            else:
                result[key] = value
        return result
    except Exception as e:
        raise ValueError(f"Invalid input for {tool_name}: {e}")
