# tesla-priority-request-queue

Stage 1 of the Morning fault queue. The Python package is `fault_triage_rules`.

Urgency rules for overnight vehicle fault messages, written as Pydantic v2 models. Every later part of the Morning fault queue follows these rules, so a brake warning no longer waits behind a question about wipers.

## Tags (exactly three)
`UrgencyTag`: `safety_urgent`, `soon`, `routine`.

## Fix paths (exactly four)
| Path | Allowed tag | What happens |
|---|---|---|
| `stop_and_tow` | safety_urgent | Call the owner within 30 minutes, tell them not to drive, tow or send a mobile tech, same-day brake and steering bay. |
| `priority_booking` | soon | Book within 3 working days. The owner may keep driving. |
| `scheduled_repair` | routine | Workshop repair at the next scheduled visit. |
| `self_serve_reply` | routine | Reply with steps to try first, no booking. |

The mapping lives in one place, `TAG_TO_PATHS` in `models.py`. `TriageResult` rejects any other pairing.

## Safety alert list
Six codes from the `vehicle_alert_code` column: `BRK_a001`, `BRK_w003`, `ABS_w002`, `ESP_w003`, `EPAS_w202`, `EPAS_a191`.

- `SafetyAlertList.check_against_csv()` fails if a listed code is not in the CSV.
- `NONE` means no alert and can never be on the list.
- `UI_a004`, `CP_a004`, `WIP_w001` and `HVAC_w003` are not safety codes.
- `ESP_w003` is the one judgment call. It stays on the list because stability control is the safety net when grip is lost.

## Rules (first match wins)
1. Smoke, fire, sparks, burning smell, or loss of power: `safety_urgent`.
2. **Hidden safety rule.** Brake or steering symptom wording: `safety_urgent`. This covers a soft, sinking, spongy or long pedal; pulling or tugging when braking or stopping; grinding at stops; heavy, loose, wobbling or shimmying steering. It applies when the code is `NONE`, when the code is not on the safety list, and when the tone is calm or polite. Tone never lowers the tag. Text is checked one sentence at a time, and a sentence saying the brakes or steering feel normal is skipped.
3. Loss of braking, such as "pedal went to the floor": `safety_urgent`.
4. Code on the safety list: `safety_urgent`, even with no symptom wording.
5. Cut-off note that mentions brakes, pedal, steering or pulling: `safety_urgent`.
6. `soon`: cannot charge or cable locked in; wipers stuck or stopping, or defrost failing; screen rebooting while driving; tyre pressure, bouncy ride, wheel hum, smell from vents; other cut-off notes.
7. Everything else is `routine`: `self_serve_reply` for app, key, range and delivery questions, `scheduled_repair` for noises and physical repairs.

## Results on the 16 November 2026 batch (300 messages)
- 105 `safety_urgent`, 28 `soon`, 167 `routine`.
- All 60 hand-checked safety faults are `safety_urgent`.
- The hidden rule fires on 41 `NONE` rows. A code-only rule would send all 41 to routine.
- The 60 hand-checked rows are all safety faults, so they test misses only. Nothing in the data tests over-flagging.

## Usage
```python
from fault_triage_rules import FaultMessage, triage

result = triage(FaultMessage(vehicle_alert_code="NONE", message_text="No rush, but the brake pedal sinks further than it used to."))
# tag=safety_urgent fix_path=stop_and_tow rule_id='R2_HIDDEN_BRAKE_STEERING'
```

```bash
pip install -e ".[dev]"
pytest
```

## Data
`data/overnight_fault_messages_2026-11-16.csv` is the overnight batch. `customer_name` and `vin_last6` are replaced with `REDACTED` in this copy. Message text is unchanged and may still contain first names.

---

## Key Claude Code prompt
> **TODO: add the key prompt you gave Claude Code here.**

## One change I made to Claude Code's output, and why
> **TODO: describe one real change you made to the generated code, and the reason.**
