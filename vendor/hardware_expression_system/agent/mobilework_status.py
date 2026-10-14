"""MobileWork business-status mapping.

Business status stays outside the generic expression state machine.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..models import ExpressionIntent


class MobileWorkStatus(str, Enum):
    WAITING_INPUT = "WAITING_INPUT"
    PLANNING = "PLANNING"
    EXPERT_ROUTING = "EXPERT_ROUTING"
    SKILL_MATCHING = "SKILL_MATCHING"
    KNOWLEDGE_RETRIEVING = "KNOWLEDGE_RETRIEVING"
    TOOL_RUNNING = "TOOL_RUNNING"
    FILE_GENERATING = "FILE_GENERATING"
    AUTOMATION_SCHEDULED = "AUTOMATION_SCHEDULED"
    CASE_REPLAYING = "CASE_REPLAYING"
    SECURITY_CHECKING = "SECURITY_CHECKING"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NETWORK_UNAVAILABLE = "NETWORK_UNAVAILABLE"
    HUMAN_INTERVENTION = "HUMAN_INTERVENTION"


@dataclass(frozen=True)
class MobileWorkStatusMapping:
    status: MobileWorkStatus
    expression_state: str
    visual_variant: str
    progress_enabled: bool = False
    accent: str = "#7dfffb"
    capability_area: str = "task_hub"

    def to_intent(self) -> ExpressionIntent:
        return ExpressionIntent(
            source=f"mobilework_status:{self.status.value}",
            expression_state=self.expression_state,
            visual_variant=self.visual_variant,
            progress_enabled=self.progress_enabled,
            accent=self.accent,
            metadata={
                "status": self.status.value,
                "capability_area": self.capability_area,
            },
        )


MOBILEWORK_STATUS_MAPPINGS = {
    MobileWorkStatus.WAITING_INPUT: MobileWorkStatusMapping(
        MobileWorkStatus.WAITING_INPUT, "IDLE", "idle_wait"
    ),
    MobileWorkStatus.PLANNING: MobileWorkStatusMapping(
        MobileWorkStatus.PLANNING, "THINKING", "planning_scan"
    ),
    MobileWorkStatus.EXPERT_ROUTING: MobileWorkStatusMapping(
        MobileWorkStatus.EXPERT_ROUTING,
        "THINKING",
        "expert_routing",
        capability_area="swarm_collaboration",
    ),
    MobileWorkStatus.SKILL_MATCHING: MobileWorkStatusMapping(
        MobileWorkStatus.SKILL_MATCHING,
        "THINKING",
        "skill_match",
        capability_area="experts_skills_knowledge",
    ),
    MobileWorkStatus.KNOWLEDGE_RETRIEVING: MobileWorkStatusMapping(
        MobileWorkStatus.KNOWLEDGE_RETRIEVING,
        "THINKING",
        "knowledge_retrieve",
        capability_area="experts_skills_knowledge",
    ),
    MobileWorkStatus.TOOL_RUNNING: MobileWorkStatusMapping(
        MobileWorkStatus.TOOL_RUNNING,
        "THINKING",
        "tool_activity",
        capability_area="ecosystem",
    ),
    MobileWorkStatus.FILE_GENERATING: MobileWorkStatusMapping(
        MobileWorkStatus.FILE_GENERATING,
        "THINKING",
        "progress",
        True,
        capability_area="creation",
    ),
    MobileWorkStatus.AUTOMATION_SCHEDULED: MobileWorkStatusMapping(
        MobileWorkStatus.AUTOMATION_SCHEDULED,
        "IDLE",
        "automation_armed",
        capability_area="scheduled_automation",
    ),
    MobileWorkStatus.CASE_REPLAYING: MobileWorkStatusMapping(
        MobileWorkStatus.CASE_REPLAYING,
        "THINKING",
        "case_replay",
        capability_area="case_replay",
    ),
    MobileWorkStatus.SECURITY_CHECKING: MobileWorkStatusMapping(
        MobileWorkStatus.SECURITY_CHECKING,
        "THINKING",
        "security_check",
        accent="#ffd36c",
        capability_area="security",
    ),
    MobileWorkStatus.WAITING_CONFIRMATION: MobileWorkStatusMapping(
        MobileWorkStatus.WAITING_CONFIRMATION,
        "CLARIFY",
        "confirmation",
        capability_area="task_hub",
    ),
    MobileWorkStatus.COMPLETED: MobileWorkStatusMapping(
        MobileWorkStatus.COMPLETED, "FULFILLED", "completed"
    ),
    MobileWorkStatus.FAILED: MobileWorkStatusMapping(
        MobileWorkStatus.FAILED,
        "SAD_SOFT",
        "failed",
        accent="#ff7d8a",
        capability_area="task_hub",
    ),
    MobileWorkStatus.BLOCKED: MobileWorkStatusMapping(
        MobileWorkStatus.BLOCKED,
        "CONCERNED",
        "blocked",
        accent="#ffd36c",
        capability_area="security",
    ),
    MobileWorkStatus.NETWORK_UNAVAILABLE: MobileWorkStatusMapping(
        MobileWorkStatus.NETWORK_UNAVAILABLE,
        "CONCERNED",
        "network_warning",
        accent="#ffd36c",
        capability_area="connection",
    ),
    MobileWorkStatus.HUMAN_INTERVENTION: MobileWorkStatusMapping(
        MobileWorkStatus.HUMAN_INTERVENTION,
        "CONCERNED",
        "human_help",
        accent="#ffeaa4",
        capability_area="task_hub",
    ),
}


class MobileWorkStatusMapper:
    """Resolve MobileWork status to a canonical expression intent."""

    def resolve(self, status: str | MobileWorkStatus) -> MobileWorkStatusMapping:
        if isinstance(status, MobileWorkStatus):
            key = status
        else:
            key = MobileWorkStatus(str(status).strip().upper())
        return MOBILEWORK_STATUS_MAPPINGS[key]

    def resolve_intent(self, status: str | MobileWorkStatus) -> ExpressionIntent:
        return self.resolve(status).to_intent()
