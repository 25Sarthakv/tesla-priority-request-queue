"""Tags, fix paths, the safety alert list and the result model."""
from __future__ import annotations

import csv
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class UrgencyTag(str, Enum):
    """Exactly three urgency tags."""

    SAFETY_URGENT = "safety_urgent"
    SOON = "soon"
    ROUTINE = "routine"


class FixPath(str, Enum):
    """Exactly four fix paths."""

    STOP_AND_TOW = "stop_and_tow"  # call within 30 min, do not drive, tow/mobile tech, same-day brake and steering bay
    PRIORITY_BOOKING = "priority_booking"  # book within 3 working days; owner may keep driving
    SCHEDULED_REPAIR = "scheduled_repair"  # workshop repair at the next scheduled visit
    SELF_SERVE_REPLY = "self_serve_reply"  # reply with steps to try first, no booking


# The one place that maps tags to fix paths.
TAG_TO_PATHS: dict[UrgencyTag, frozenset[FixPath]] = {
    UrgencyTag.SAFETY_URGENT: frozenset({FixPath.STOP_AND_TOW}),
    UrgencyTag.SOON: frozenset({FixPath.PRIORITY_BOOKING}),
    UrgencyTag.ROUTINE: frozenset({FixPath.SCHEDULED_REPAIR, FixPath.SELF_SERVE_REPLY}),
}

# Codes taken from the vehicle_alert_code column. NONE means no alert and is never on this list.
# UI_a004, CP_a004, WIP_w001 and HVAC_w003 are deliberately not safety codes.
NO_ALERT = "NONE"


class SafetyAlertList(BaseModel):
    model_config = ConfigDict(frozen=True)

    codes: frozenset[str]

    @field_validator("codes")
    @classmethod
    def _no_none(cls, v: frozenset[str]) -> frozenset[str]:
        if NO_ALERT in v:
            raise ValueError("NONE is the absence of an alert and cannot be on the safety list")
        return v

    def check_against_csv(self, csv_path: str | Path) -> None:
        """Raise ValueError unless every code on the list appears in the CSV's vehicle_alert_code column."""
        with open(csv_path, newline="", encoding="utf-8") as f:
            seen = {row["vehicle_alert_code"] for row in csv.DictReader(f)}
        missing = sorted(self.codes - seen)
        if missing:
            raise ValueError(f"codes not found in vehicle_alert_code column: {missing}")


SAFETY_ALERTS = SafetyAlertList(
    codes=frozenset({"BRK_a001", "BRK_w003", "ABS_w002", "ESP_w003", "EPAS_w202", "EPAS_a191"})
)
SAFETY_ALERT_CODES = SAFETY_ALERTS.codes


class FaultMessage(BaseModel):
    message_id: str = ""
    vehicle_alert_code: str = NO_ALERT
    message_subject: str = ""
    message_text: str


class TriageResult(BaseModel):
    tag: UrgencyTag
    fix_path: FixPath
    rule_id: str
    reason: str

    @model_validator(mode="after")
    def _pairing(self) -> "TriageResult":
        if self.fix_path not in TAG_TO_PATHS[self.tag]:
            raise ValueError(f"fix path {self.fix_path.value} is not allowed for tag {self.tag.value}")
        return self
