import csv
from pathlib import Path

import pytest
from pydantic import ValidationError

from fault_triage_rules import (
    SAFETY_ALERT_CODES,
    FaultMessage,
    FixPath,
    SafetyAlertList,
    TriageResult,
    UrgencyTag,
    triage,
)

CSV = Path(__file__).resolve().parent.parent / "data" / "overnight_fault_messages_2026-11-16.csv"


@pytest.fixture(scope="module")
def rows():
    with open(CSV, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def msg(row):
    return FaultMessage(
        message_id=row["message_id"],
        vehicle_alert_code=row["vehicle_alert_code"],
        message_subject=row["message_subject"],
        message_text=row["message_text"],
    )


# --- enums and mapping ---
def test_exactly_three_tags_and_four_paths():
    assert {t.value for t in UrgencyTag} == {"safety_urgent", "soon", "routine"}
    assert {p.value for p in FixPath} == {"stop_and_tow", "priority_booking", "scheduled_repair", "self_serve_reply"}


def test_bad_tag_path_pairing_rejected():
    with pytest.raises(ValidationError):
        TriageResult(tag=UrgencyTag.SAFETY_URGENT, fix_path=FixPath.SCHEDULED_REPAIR, rule_id="x", reason="x")
    with pytest.raises(ValidationError):
        TriageResult(tag=UrgencyTag.SOON, fix_path=FixPath.STOP_AND_TOW, rule_id="x", reason="x")
    TriageResult(tag=UrgencyTag.ROUTINE, fix_path=FixPath.SELF_SERVE_REPLY, rule_id="x", reason="x")


# --- safety alert list ---
def test_safety_codes_exist_in_csv():
    from fault_triage_rules import SAFETY_ALERTS
    SAFETY_ALERTS.check_against_csv(CSV)
    assert SAFETY_ALERT_CODES == {"BRK_a001", "BRK_w003", "ABS_w002", "ESP_w003", "EPAS_w202", "EPAS_a191"}


def test_none_never_on_list():
    with pytest.raises(ValidationError):
        SafetyAlertList(codes=frozenset({"BRK_w003", "NONE"}))


def test_unknown_code_fails_csv_check():
    with pytest.raises(ValueError):
        SafetyAlertList(codes=frozenset({"BRK_w003", "MADE_UP"})).check_against_csv(CSV)


def test_non_safety_codes_not_listed():
    assert not {"UI_a004", "CP_a004", "WIP_w001", "HVAC_w003", "NONE"} & SAFETY_ALERT_CODES


# --- batch checks ---
def test_all_hand_checked_safety_faults_are_safety_urgent(rows):
    checked = [r for r in rows if r["hand_checked_safety_fault"] == "TRUE"]
    assert len(checked) == 60
    missed = [r["message_id"] for r in checked if triage(msg(r)).tag != UrgencyTag.SAFETY_URGENT]
    assert missed == []


def test_hidden_rule_fires_on_41_none_rows(rows):
    hits = [r for r in rows if r["vehicle_alert_code"] == "NONE"
            and triage(msg(r)).rule_id == "R2_HIDDEN_BRAKE_STEERING"]
    assert len(hits) == 41


def test_batch_counts(rows):
    counts = {}
    for r in rows:
        t = triage(msg(r)).tag
        counts[t] = counts.get(t, 0) + 1
    assert counts == {UrgencyTag.SAFETY_URGENT: 105, UrgencyTag.SOON: 28, UrgencyTag.ROUTINE: 167}


# --- unit tests ---
def test_calm_no_rush_soft_pedal_is_safety():
    r = triage(FaultMessage(vehicle_alert_code="NONE", message_subject="small thing",
                            message_text="No rush at all, happy to wait for a slot. The brake pedal sinks a bit further than it used to."))
    assert r.tag == UrgencyTag.SAFETY_URGENT and r.fix_path == FixPath.STOP_AND_TOW
    assert r.rule_id == "R2_HIDDEN_BRAKE_STEERING"


def test_none_code_decided_by_text():
    safe = triage(FaultMessage(vehicle_alert_code="NONE", message_text="The car tugs to the left when I stop at lights."))
    other = triage(FaultMessage(vehicle_alert_code="NONE", message_text="A rattle from the rear seat area over bumps."))
    assert safe.tag == UrgencyTag.SAFETY_URGENT
    assert other.tag == UrgencyTag.ROUTINE


def test_code_not_on_list_still_gets_text_check():
    r = triage(FaultMessage(vehicle_alert_code="WIP_w001", message_text="Wiper warning is on and the brake pedal feels spongy."))
    assert r.tag == UrgencyTag.SAFETY_URGENT
    assert r.rule_id == "R2_HIDDEN_BRAKE_STEERING"
    assert triage(FaultMessage(vehicle_alert_code="WIP_w001", message_text="Wiper grinds when it parks.")).tag == UrgencyTag.ROUTINE


def test_safety_code_without_symptom_is_safety():
    r = triage(FaultMessage(vehicle_alert_code="ESP_w003", message_text="Light came on and went off again."))
    assert r.tag == UrgencyTag.SAFETY_URGENT and r.rule_id == "R4_SAFETY_CODE"


def test_brakes_feel_normal_sentence_does_not_trigger():
    r = triage(FaultMessage(vehicle_alert_code="NONE",
                            message_text="Tyre pressure light came on. Pedal and steering feel completely normal so I think it is the cold."))
    assert r.tag == UrgencyTag.SOON
    assert r.rule_id != "R2_HIDDEN_BRAKE_STEERING"
    assert triage(FaultMessage(message_text="There is a clunk over bumps. The brakes feel normal.")).tag == UrgencyTag.ROUTINE


def test_fire_and_cut_off_rules():
    assert triage(FaultMessage(message_text="I smell smoke from the dash.")).rule_id == "R1_FIRE_OR_POWER_LOSS"
    assert triage(FaultMessage(message_text="Advisor note cut off, it was about the steering")).tag == UrgencyTag.SAFETY_URGENT
