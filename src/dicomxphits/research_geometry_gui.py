"""GUI review model; the CLI and GUI share all acceptance and file validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dicomxphits.research_geometry_recovery import apply, preview

RESEARCH_NOTICE = (
    "RESEARCH ONLY: geometry recovery was reported; PHITS remains failed. "
    "Operator acceptance does not establish dose accuracy or clinical validity. "
    "Not for clinical use, commissioning, patient QA, or vendor certification."
)


@dataclass(frozen=True)
class ResearchGeometryReview:
    workspace_root: Path
    staging_directory: str
    generation: int
    evidence: dict[str, Any]

    @classmethod
    def prepare(cls, workspace_root: Path, staging_directory: str, generation: int):
        root = workspace_root.expanduser().resolve()
        return cls(root, staging_directory, generation,
                   preview(root, staging_directory=staging_directory))

    def current(self, workspace_root: Path, generation: int) -> bool:
        return self.workspace_root == workspace_root.expanduser().resolve() and generation == self.generation

    def text(self) -> str:
        plan = self.evidence["plan"]
        counts = plan["diagnostics"]["counts"]
        pairs = "\n".join(f"  {p['region1']} -> {p['region2']}: {p['count']}"
                          for p in plan["region_pair_counts"])
        outputs = "\n".join(f"  {p['destination']}" for p in plan["outputs"])
        return (f"{RESEARCH_NOTICE}\n\nWorkspace: {self.workspace_root}\n"
                f"Segment: {plan['accepted_segment_id']}\nStaging: {self.staging_directory}\n"
                f"Lost: {counts['lost_particles']}; recovering: {counts['geometry_recovering']}; "
                f"unrecovered: {counts['unrecovered_errors']}\nRegion pairs:\n{pairs}\n"
                f"Final batch: {plan['completed_batches']} / {plan['maxbch']}\n"
                f"Existing tallies to publish:\n{outputs}\n"
                f"Plan: {self.evidence['plan_digest']}\n\n"
                "Acceptance reads saved evidence and creates a receipt. "
                "PHITS is not recalculated. Sumtally and RTDOSE are separate actions.")

    def confirm(self, *, workspace_root: Path, generation: int,
                reason: str | None, confirmed: bool):
        if confirmed is not True or reason is None:
            return None  # No, cancel, Escape, and window closure never apply.
        if not self.current(workspace_root, generation):
            raise ValueError("Workspace selection changed; create a new research preview")
        return apply(self.workspace_root, staging_directory=self.staging_directory,
                     expected_plan_digest=self.evidence["plan_digest"],
                     acknowledge_research_only=True, reason=reason)
