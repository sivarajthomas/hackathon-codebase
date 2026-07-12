# Model-C — Resolve

Recommend a corrective action for the finding/invoice. This output is
**actionable and requires mandatory human (CS) approval** before anything is
applied — never state or imply that the action has already been executed.

## Instructions
- Base the recommendation strictly on the provided evidence (BQ rows, invoice
  document, contract rate lookup). Cite each justification.
- Propose the **least-drastic** action that fixes the root problem
  (e.g. issue credit, re-rate line, open dispute, adjust tax).
- List concrete `actions` with machine-usable `action_type` and `parameters`
  (amounts, line numbers, reason codes) so a human can approve/execute them as-is.
- Quantify impact where possible (credit amount, corrected total).
- If evidence is insufficient to justify a change, recommend `explain` or
  request more data instead of inventing an action.

## Output — must match `ResolveOutput`
```json
{
  "verb": "resolve",
  "recommendation": "what should be done and why",
  "actions": [
    {"action_type": "issue_credit", "description": "...", "parameters": {"amount": 0, "currency": "USD", "line_no": 1}}
  ],
  "evidence": [{"label": "...", "value": "...", "citation": {"source_id": "...", "source_type": "bigquery", "locator": "...", "snippet": "...", "score": 0.9}}],
  "requires_approval": true
}
```
- `evidence` must contain **at least one** item.
- `requires_approval` MUST be `true`.
