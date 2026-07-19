# Stage 3 Bounded SMILES Repair

Perform one bounded repair of a provisional SMILES using only the supplied source evidence and validation or identity failure report.

Preserve target identity. Do not invent missing groups or switch to another molecule. Return `proposed_smiles: null` if evidence is insufficient. Any repair must be rerun through RDKit validation, depiction, and visual identity review.

Return exactly one JSON object with `candidate_id`, `molecule_label`, `proposed_smiles`, `repair_action`, `source_basis`, `uncertainty_reason`, `final_decision`, and `confidence`. `repair_action` must be `fixed_smiles|cannot_fix|reject`.
