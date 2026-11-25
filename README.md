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

```text
Create a new Python repo called fault-triage-rules. Use Pydantic v2 and pytest. Model the urgency rules for overnight vehicle fault messages.

1. Tags. Define an enum UrgencyTag with exactly three members: safety_urgent, soon, routine.

2. Fix paths. Define an enum FixPath with exactly four members:
   - stop_and_tow: call the owner within 30 minutes, tell them not to drive, tow or send a mobile tech, same-day brake and steering bay.
   - priority_booking: book within 3 working days; the owner may keep driving.
   - scheduled_repair: workshop repair at the next scheduled visit.
   - self_serve_reply: reply with steps to try first, no booking.
   Map tags to paths in one place: safety_urgent -> stop_and_tow only; soon -> priority_booking only; routine -> scheduled_repair or self_serve_reply. Reject any other pairing in a validator.

3. Safety alert list. A frozen set of codes taken from the vehicle_alert_code column of the CSV: BRK_a001, BRK_w003, ABS_w002, ESP_w003, EPAS_w202, EPAS_a191. Add a validator that every code on the list exists in the CSV. NONE is the absence of an alert and must never be on the list. UI_a004, CP_a004, WIP_w001 and HVAC_w003 are not safety codes.

4. Rules. A Pydantic model TriageResult(tag, fix_path, rule_id, reason) and a function triage(message) -> TriageResult. The first match wins, in this order:
   - smoke, fire, sparks, burning smell, or loss of power while driving -> safety_urgent
   - the hidden safety rule: brake or steering symptom wording -> safety_urgent. This covers soft, sinking, spongy or long pedal; pulling or tugging when braking or stopping; grinding at stops; heavy, loose, wobbling or shimmying steering. It applies when the code is NONE, when the code is not on the safety list, and when the tone is calm or polite. Tone must never lower the tag. Check one sentence at a time and skip any sentence saying the brakes or steering feel normal.
   - loss of braking, such as "pedal went to the floor" -> safety_urgent
   - code on the safety list -> safety_urgent, even without symptom wording
   - cut-off note that mentions brakes, pedal, steering or pulling -> safety_urgent
   - soon: cannot charge or cable locked in; wipers stuck or stopping, or defrost failing; screen rebooting while driving; tyre pressure, bouncy ride, wheel hum, smell from vents; other cut-off notes
   - everything else -> routine. Use self_serve_reply for app, key, range and delivery questions, and scheduled_repair for noises and physical repairs.

5. Tests. Load the CSV from data/. Assert that all 60 rows with hand_checked_safety_fault=TRUE come out safety_urgent. Assert that the hidden rule fires on NONE rows (expect 41). Add unit tests for: a calm "no rush" soft-pedal message, a NONE code, a code not on the list, and a "brakes feel normal" sentence that must not trigger.

6. Docs. A README that explains the tags, paths, safety list and hidden rule, and contains two sections for me to fill in: the key prompt you were given, and one change made to your output with the reason. Leave both sections as clearly marked placeholders; do not invent them.

Commit with clear messages, create the GitHub repo, and push. Give me the link.
```

## One change I made to Claude Code's output, and why

**The "spongy" word was missed by the pedal-feel check.**

The first version of the hidden brake and steering rule matched pedal words with a word boundary on both sides, and it listed the stem `spong` instead of the whole word. So "the pedal feels spongy" did not match, because "spong" is followed by "y", not a word boundary. I noticed it when a message with a brake alert code and the text "pedal feels spongy" passed only because of its alert code. The same wording with no alert code would have been tagged routine.

I changed the pattern to `spong\w*`, so "spongy" and "sponginess" both match, and added a regression test (`test_spongy_pedal_with_no_alert_code_is_safety`) for a `NONE`-code message.

**Why:** this rule exists to catch calm messages that hide a brake symptom. A missed word means a safety message waits as routine, which is the exact failure the rule is there to prevent. Without the test, the bug could return unnoticed.
