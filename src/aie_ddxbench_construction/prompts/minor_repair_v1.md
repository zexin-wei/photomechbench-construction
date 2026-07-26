You are repairing one PhotoMechBench v0.4 reference case after a quality review.

Apply every substantive recommendation in REVIEW, but make the smallest scientifically necessary edits.

Hard constraints:
1. Return exactly one JSON object with keys revised_json and changes.
2. revised_json must be the complete case JSON, not a patch.
3. Preserve case_id, version, track, public_input, and source_article exactly.
4. Preserve evidence quotes unless REVIEW specifically requires correcting an inaccurate quote or evidence attribution.
5. Do not invent experiments, evidence IDs, quotes, mechanisms, exclusions, or numerical values.
6. Distinguish "not supported/not evaluated" from experimentally weakened or rejected.
7. Keep mechanism values within the official 11-mechanism vocabulary plus FINAL_EVIDENCE_GROUNDED_DIAGNOSIS.
8. Ensure every supporting_evidence_id exists and every diagnosis_id/evidence_id is unique.
9. Keep the final synthesis consistent with revised statuses and roles.
10. Do not make style-only rewrites outside fields implicated by REVIEW.
11. Never add structure_resolution_report, model reports, review reports, or other internal workflow fields to revised_json.

REVIEW:
```text
$REVIEW
```
SOURCE.MD:
```text
$SOURCE
```

ORIGINAL CASE JSON:
```json
$ORIGINAL_CASE_JSON
```

Output schema:
```json
{
  "revised_json": {"...": "complete case"},
  "changes": [
    {"json_path": "...", "before": "...", "after": "...", "reason": "..."}
  ]
}
```
