"""Submission API schemas — spec §6.1, §8, §9. Single source of contract truth."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Constants (spec §6.1 hard caps)
# ---------------------------------------------------------------------------
MAX_TRIALS = 50
MAX_TIMEOUT_S = 30.0
MAX_MEMORY_MB = 1024
MAX_CODE_BYTES = 64 * 1024       # 64 KiB
MAX_PROMPT_BYTES = 16 * 1024     # 16 KiB
MAX_FILE_CONTENT_BYTES = 64 * 1024
MAX_FILES_PER_SUITE = 64
_FILE_NAME_RE = re.compile(r"^[A-Za-z0-9_./-]{1,128}$")

Language = Annotated[
    str,
    Field(pattern=r"^(python|javascript|java|cpp|rust)$"),
]
Framework = Annotated[
    str,
    Field(pattern=r"^(pytest|jest|junit|gtest|cargo_test)$"),
]
Status = Annotated[
    str,
    Field(pattern=r"^(queued|running|scored|failed)$"),
]

# Mapping spec §7.4 — default framework per language.
LANGUAGE_FRAMEWORK: dict[str, str] = {
    "python": "pytest",
    "javascript": "jest",
    "java": "junit",
    "cpp": "gtest",
    "rust": "cargo_test",
}


# ---------------------------------------------------------------------------
# Test suite
# ---------------------------------------------------------------------------
class TestFile(BaseModel):
    name: str = Field(..., description="File path inside /work, e.g. test_add.py")
    content: str = Field(..., description="UTF-8 file content, max 64 KiB")

    @field_validator("name")
    @classmethod
    def valid_name(cls, v: str) -> str:
        if not _FILE_NAME_RE.match(v):
            raise ValueError("File name must match [A-Za-z0-9_./-]{1,128}")
        return v

    @field_validator("content")
    @classmethod
    def valid_content(cls, v: str) -> str:
        if len(v.encode()) > MAX_FILE_CONTENT_BYTES:
            raise ValueError(f"File content exceeds {MAX_FILE_CONTENT_BYTES} bytes")
        return v


class TestSuite(BaseModel):
    framework: Framework
    files: list[TestFile] = Field(..., min_length=1, max_length=MAX_FILES_PER_SUITE)
    entrypoint: str = Field(..., description="Name of the main test file from `files`")

    @model_validator(mode="after")
    def entrypoint_must_be_in_files(self) -> "TestSuite":
        names = {f.name for f in self.files}
        if self.entrypoint not in names:
            raise ValueError(f"entrypoint '{self.entrypoint}' not found in files: {names}")
        return self


# ---------------------------------------------------------------------------
# Submission create (client → API)
# ---------------------------------------------------------------------------
class SubmissionCreate(BaseModel):
    model_id: str = Field(..., min_length=1, max_length=256)
    language: Language
    code: str = Field(..., description="Submitted solution code, max 64 KiB")
    prompt: str = Field(default="", description="Natural-language task description, max 16 KiB")
    test_suite: TestSuite
    trials: int = Field(default=10, ge=1, le=MAX_TRIALS)
    timeout_seconds: float = Field(default=5.0, gt=0.0, le=MAX_TIMEOUT_S)
    memory_limit_mb: int = Field(default=256, ge=16, le=MAX_MEMORY_MB)
    determinism_seed: int = Field(default=0xCAFEF00D)

    @field_validator("code")
    @classmethod
    def valid_code(cls, v: str) -> str:
        if len(v.encode()) > MAX_CODE_BYTES:
            raise ValueError(f"code exceeds {MAX_CODE_BYTES} bytes")
        return v

    @field_validator("prompt")
    @classmethod
    def valid_prompt(cls, v: str) -> str:
        if len(v.encode()) > MAX_PROMPT_BYTES:
            raise ValueError(f"prompt exceeds {MAX_PROMPT_BYTES} bytes")
        return v

    @model_validator(mode="after")
    def framework_matches_language(self) -> "SubmissionCreate":
        expected = LANGUAGE_FRAMEWORK.get(self.language)
        if expected and self.test_suite.framework != expected:
            raise ValueError(
                f"language '{self.language}' requires framework '{expected}', "
                f"got '{self.test_suite.framework}'"
            )
        return self


# ---------------------------------------------------------------------------
# Trial result (scheduler → aggregator via stream)
# ---------------------------------------------------------------------------
class Trial(BaseModel):
    index: int
    wall_ns: int = Field(ge=0)
    mem_kb: int = Field(ge=0)
    exit_code: int
    framework_passed: bool
    sandbox_violation: bool
    stderr_snippet: str | None = None


# ---------------------------------------------------------------------------
# Scored result (aggregator writes, API returns)
# ---------------------------------------------------------------------------
class CI(BaseModel):
    lo: float
    hi: float


class ScoredResult(BaseModel):
    correctness: float = Field(ge=0.0, le=1.0)
    correctness_ci: CI
    reliability: float = Field(ge=0.0, le=1.0)
    flaky: bool
    perf_normalized: float | None = None
    perf_ci: CI | None = None
    trials_total: int
    trials_passed: int
    wall_time_ms_p50: int
    wall_time_ms_p95: int
    mem_peak_mb: int | None = None
    attestation_pubkey_id: str
    scored_at: datetime
    raw_trials: list[Trial] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Full Submission response
# ---------------------------------------------------------------------------
class SubmissionResponse(BaseModel):
    id: UUID
    tenant_id: str
    model_id: str
    language: Language
    status: Status
    version: int
    created_at: datetime
    updated_at: datetime
    result: ScoredResult | None = None


class SubmitResponse(BaseModel):
    id: UUID
    replay: bool


class SubmissionListItem(BaseModel):
    id: UUID
    tenant_id: str
    model_id: str
    language: Language
    status: Status
    trials_total: int | None = None
    correctness: float | None = None
    perf_normalized: float | None = None
    reliability: float | None = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Attestation (spec §9)
# ---------------------------------------------------------------------------
class AttestationScores(BaseModel):
    correctness: float
    correctness_ci: list[float] = Field(..., min_length=2, max_length=2)
    reliability: float
    perf_normalized: float | None = None
    perf_ci: list[float] | None = None


class Attestation(BaseModel):
    version: str = "1.0"
    submission_id: UUID
    tenant_id: str
    model_id: str
    language: str
    prompt_hash: str
    test_suite_hash: str
    runner_image_digest: str
    scheduler_version: str
    scores: AttestationScores
    trials: int
    scored_at: datetime
    host_fingerprint: str
    signature_algorithm: str = "Ed25519"
    pubkey_id: str
    signature: str = ""  # populated by aggregator/sign.py; empty before signing
