# Mutation Testing (pytest-gremlins)

Tool: `pytest-gremlins` 1.13.2. Kill set: `tests/test_rules.py tests/test_api.py`
(the domain + API tests; browser E2E excluded). Raw machine-readable reports are
in this directory: `gremlins-baseline-rules.json`, `gremlins-final.json`.

## Commands

```powershell
# Initial baseline — business-rule module only
.venv\Scripts\python.exe -m pytest --gremlins `
  --gremlin-targets=app/domain/rules.py `
  --gremlin-report=console,json tests/test_rules.py tests/test_api.py

# Broader pass + final — rules + service layer
.venv\Scripts\python.exe -m pytest --gremlins `
  --gremlin-targets=app/domain/rules.py,app/services/invoice_service.py `
  --gremlin-report=console,json tests/test_rules.py tests/test_api.py
```

## Results (actual)

| Pass | Target(s) | Total | Killed (zapped) | Survived | Score |
|---|---|---|---|---|---|
| Baseline (req scope) | `app/domain/rules.py` | 27 | 27 | 0 | **100.00%** |
| Broader — before | rules + `invoice_service.py` | 35 | 33 | 2 | 94.29% |
| Broader — after | rules + `invoice_service.py` | 35 | 34 | 1 | **97.14%** |

The business-rule module (`rules.py`) was already at **100%** on the first run —
no survivors, so no rule-test changes were needed there.

To exercise the process meaningfully, the scope was widened to include the
service layer, which surfaced **2 survivors**:

1. `invoice_service.py:69` `+ → -` (arithmetic) — `sequence = len(approvals) + 1`.
   **Genuine gap**: no test asserted approval `sequence` values. **Fixed** by
   adding `tests/test_api.py::test_approval_sequence_numbers`, which asserts
   sequences are `[1, 2]` (high-value) and `[1]` (single). This killed the mutant
   (final pass). Assertions were strengthened, not weakened; no rule was changed.

2. `invoice_service.py:22` `True → False` (boolean) — the `frozen=True` flag on
   the `ApprovalResult` dataclass. **Equivalent mutant**: changing a result
   object's immutability flag produces no observable change in any specified
   behavior. Killing it would require asserting an implementation detail
   (dataclass immutability) unrelated to the approval rules, which would violate
   the "don't change tests merely to raise the score" guidance. **Disposition:
   accepted as an equivalent mutant.**

Net: score improved 94.29% → 97.14% via a real test gap fix; the single remaining
survivor is a documented equivalent mutant.
