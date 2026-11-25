"""Rule engine. First match wins, in the order set out in triage()."""
from __future__ import annotations

import re

from .models import (
    SAFETY_ALERT_CODES,
    FaultMessage,
    FixPath,
    TriageResult,
    UrgencyTag,
)

I = re.IGNORECASE

# --- Rule 1: smoke, fire, sparks, burning smell, loss of power --------------------------------
FIRE = re.compile(r"\b(smoke|smoking|burning smell|fire|flames|sparks?)\b", I)
POWER_LOSS = re.compile(r"\b(lost power|cut power|power cut|loss of power|shut down while driving|stalled)\b", I)

# --- Rule 2: the hidden safety rule (brake or steering symptom wording) ----------------------
# A sentence saying brakes/steering feel normal is skipped.
NORMAL = re.compile(
    r"\b(brakes?|pedal|steer(ing)?|it)\b[^.]*\b(normal|fine|same|as before|as always|exactly as|firm|tracks straight|not stopping me)\b"
    r"|not a safety|not urgent at all",
    I,
)
PEDAL = re.compile(
    r"\b(brake pedal|pedal|brakes?)\b[^.]*\b(soft|softer|sink|sinks|sinking|spong\w*|long|floor|lower|further|grab|grabs|grabby|"
    r"shudder|pulse|pulses|drops?|dropped|goes? down|takes? longer|stopping takes|go(es)? a long way|doesn't bite|"
    r"bites? late|different|odd|off|uneven|not like before)\b",
    I,
)
PEDAL_REV = re.compile(r"\b(soft|spongy|sinks?|sinking|long)\b[^.]*\bpedal\b", I)
GRIND_STOP = re.compile(r"\bgrind(ing)?\b[^.]*\b(stop|stopping|lights|pedal|brak|junction)", I)
GRIND_STOP_REV = re.compile(
    r"\b(stop|stopping|lights|brak\w*)\b[^.]*\bgrind(ing)?\b[^.]*\b(front wheels?|pedal|front|rubbing)", I
)
PULL_BRAKING = re.compile(
    r"\b(pull(s|ing)?|tug(s|ging)?|drift(s|ing)?)\b[^.]*\b(brak|stop|stopping|slow|slowing|coming to|halt|junction|lights)", I
)
PULL_BRAKING_REV = re.compile(
    r"\b(brak\w*|stop(ping)?|slow(ing)?)\b[^.]*\b(pull(s|ing)?|tug(s|ging)?|drift(s|ing)?)\b", I
)
PULL_FREE = re.compile(
    r"\bpulls?\b[^.]*\b(gently )?(to the )?(left|right|one side)\b[^.]*\b(straight|hands off|off-centre|corrections?|keep correcting)"
    r"|keep correcting",
    I,
)
STEERING = re.compile(
    r"\b(steering|wheel)\b[^.]*\b(heavy|stiff|loose|wobble|shimmy|catches|jerks?|uneven|resists|odd|off-centre|heavier|light(?! on))\b", I
)
STEERING_WOBBLE = re.compile(
    r"\b(wobble|shimmy)\b[^.]*\b(steering|wheel|hands)\b|\b(steering|wheel)\b[^.]*\b(wobble|shimmy|jerks?)\b", I
)
STEERING_PULL_LOW_SPEED = re.compile(
    r"\b(pulled?|pulls?)\b[^.]*\b(one side|to the (left|right)|left|right)\b[^.]*\b(low speed|parking|car park|turn)"
    r"|steering[^.]*\bpulls? to one side",
    I,
)

SYMPTOM_PATTERNS = (
    ("pedal feel", (PEDAL, PEDAL_REV)),
    ("grinding at stops", (GRIND_STOP, GRIND_STOP_REV)),
    ("pulls when braking/stopping", (PULL_BRAKING, PULL_BRAKING_REV, PULL_FREE)),
    ("steering feel", (STEERING, STEERING_WOBBLE, STEERING_PULL_LOW_SPEED)),
)

# --- Rule 3: loss of braking -----------------------------------------------------------------
LOSS_OF_BRAKING = re.compile(
    r"\b(to the floor|went (right )?down|all the way down|no brakes|brakes (failed|gone)|couldn't stop|could not stop)\b", I
)

# --- Rule 5: cut-off notes -------------------------------------------------------------------
CUT_OFF = re.compile(r"(note cut off|call dropped|advisor note clipped|note clipped|cut off)", I)
BRAKE_STEER_WORDS = re.compile(r"(brak|pedal|steer|pull)", I)

# --- Soon rules ------------------------------------------------------------------------------
SOON_RULES = (
    ("S1", "Cannot charge or cable locked in", re.compile(
        r"(cable is still locked|latch will not release|won't start charging|cannot start charging|locked in)", I)),
    ("S2", "Visibility: wipers stuck or stopping, or defrost failing", re.compile(
        r"(wipers? (stopp|stuck)|stopped halfway|stopping halfway|stuck in the up|stops in the middle|"
        r"defrost[^.]*(slow|ages|takes)|not clearing the glass)", I)),
    ("S3", "Screen reboots while driving", re.compile(
        r"(reboot|restart)\w*[^.]*(driving|drive|commute)|(driving|drive|commute)[^.]*(reboot|restart)", I)),
    ("S4", "Tyre pressure, bouncy ride, wheel hum", re.compile(
        r"(tyre pressure|one wheel is low|bouncy|rocking after|hum from (the )?(rear )?wheels|wheel bearing)", I)),
    ("S5", "Smell from vents", re.compile(r"(burnt smell|burning|coolant|sweet smell)", I)),
)

# --- Routine: which path ---------------------------------------------------------------------
SELF_SERVE = re.compile(
    r"(\bapp\b|log ?in|sign in|password|phone key|key card|\bpair|\brange\b|delivery|mileage|odometer|seat memory)", I
)


def _sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.!?])\s+", text)


def brake_steering_symptoms(text: str) -> list[str]:
    """Return the symptom kinds found, checking one sentence at a time and skipping 'feels normal' sentences."""
    found: list[str] = []
    for sentence in _sentences(text):
        if NORMAL.search(sentence):
            continue
        for kind, patterns in SYMPTOM_PATTERNS:
            if any(p.search(sentence) for p in patterns):
                if kind not in found:
                    found.append(kind)
                break
    return found


def _result(tag: UrgencyTag, path: FixPath, rule_id: str, reason: str) -> TriageResult:
    return TriageResult(tag=tag, fix_path=path, rule_id=rule_id, reason=reason)


def triage(message: FaultMessage) -> TriageResult:
    """Triage one fault message. First match wins."""
    text = f"{message.message_subject}. {message.message_text}"
    code = message.vehicle_alert_code

    # 1. Smoke, fire, sparks, burning smell, loss of power
    if FIRE.search(text) or POWER_LOSS.search(text):
        return _result(UrgencyTag.SAFETY_URGENT, FixPath.STOP_AND_TOW, "R1_FIRE_OR_POWER_LOSS",
                       "Smoke, fire, sparks, burning smell or loss of power")

    # 2. Hidden safety rule: wording decides, whatever the code and whatever the tone
    symptoms = brake_steering_symptoms(f"{message.message_text} {message.message_subject}")
    if symptoms:
        suffix = " (no dashboard alert)" if code == "NONE" else ""
        return _result(UrgencyTag.SAFETY_URGENT, FixPath.STOP_AND_TOW, "R2_HIDDEN_BRAKE_STEERING",
                       "Brake/steering symptom: " + ", ".join(symptoms) + suffix)

    # 3. Loss of braking
    if LOSS_OF_BRAKING.search(text):
        return _result(UrgencyTag.SAFETY_URGENT, FixPath.STOP_AND_TOW, "R3_LOSS_OF_BRAKING",
                       "Reports loss of braking")

    # 4. Code on the safety list
    if code in SAFETY_ALERT_CODES:
        return _result(UrgencyTag.SAFETY_URGENT, FixPath.STOP_AND_TOW, "R4_SAFETY_CODE",
                       f"Dashboard alert {code} is on the safety list")

    # 5. Cut-off note that mentions brakes, pedal, steering or pulling
    if CUT_OFF.search(message.message_text) and BRAKE_STEER_WORDS.search(text):
        return _result(UrgencyTag.SAFETY_URGENT, FixPath.STOP_AND_TOW, "R5_CUT_OFF_BRAKE_STEER",
                       "Cut-off note mentioning brakes, pedal, steering or pulling")

    # Soon
    for rule_id, name, pattern in SOON_RULES:
        if pattern.search(text):
            return _result(UrgencyTag.SOON, FixPath.PRIORITY_BOOKING, rule_id, name)
    if CUT_OFF.search(message.message_text):
        return _result(UrgencyTag.SOON, FixPath.PRIORITY_BOOKING, "S6", "Message cut off, call back to read the rest")

    # Routine
    if SELF_SERVE.search(text):
        return _result(UrgencyTag.ROUTINE, FixPath.SELF_SERVE_REPLY, "R9_SELF_SERVE",
                       "App, key, range or delivery question")
    return _result(UrgencyTag.ROUTINE, FixPath.SCHEDULED_REPAIR, "R9_SCHEDULED",
                   "Noise, comfort or physical repair for the next visit")
