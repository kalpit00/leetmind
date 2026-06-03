"""Pydantic schemas for LLM structured outputs in the knowledge base.

Using structured outputs (OpenAI ``responses.parse`` / ``chat.completions.parse``)
keeps the analyzer robust: the model must return exactly these fields, so the
rest of the pipeline can rely on the shape without defensive JSON parsing.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SolutionAnalysis(BaseModel):
    """Structured analysis of a single accepted submission."""

    pattern_name: str = Field(
        description="Short canonical name of the core pattern, e.g. 'Monotonic Increasing Stack', 'Two Pointers', 'Top-down DP with memoization'."
    )
    core_idea: str = Field(
        description="1-3 sentences explaining the approach actually used in this code."
    )
    invariant: str = Field(
        description="The key loop or data-structure invariant the solution maintains. Empty string if not applicable."
    )
    complexity: str = Field(
        description="Time and space complexity, e.g. 'O(n) time, O(n) space'."
    )
    techniques: list[str] = Field(
        default_factory=list,
        description="Technique/topic labels inferred from the code, e.g. ['stack', 'monotonic stack', 'array'].",
    )
    pitfalls: list[str] = Field(
        default_factory=list,
        description="Edge cases or gotchas this pattern requires, grounded in the code.",
    )
    template_code: str = Field(
        description="A generalized, reusable code skeleton (same language as the submission) capturing the pattern with placeholder names, not the full problem-specific solution."
    )
    style_notes: list[str] = Field(
        default_factory=list,
        description="Observable coding-style traits in THIS submission: naming conventions, data structures chosen (e.g. 'ArrayDeque over Stack'), iterative vs recursive, variable grouping, formatting cleanliness.",
    )


class BridgeCandidate(BaseModel):
    """One relationship between the target problem and an already-solved problem."""

    source_problem_slug: str = Field(
        description="Slug of the already-solved problem that the target reduces to or shares a pattern with. MUST be one of the provided candidate slugs."
    )
    relationship: str = Field(
        description="How the target problem relates to or reduces to the source problem."
    )
    shared_patterns: list[str] = Field(
        default_factory=list, description="Patterns/techniques shared between the two."
    )
    transfer_steps: list[str] = Field(
        default_factory=list,
        description="Concrete steps to adapt the source solution/template to the target problem.",
    )
    confidence: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Confidence in this bridge, 0.0-1.0."
    )


class BridgeResult(BaseModel):
    """Ranked set of bridges from the target problem to solved problems."""

    bridges: list[BridgeCandidate] = Field(default_factory=list)
