# Stage 3 Bounded SMILES Repair

Perform one bounded repair of a provisional SMILES using only the supplied source evidence and validation or identity failure report.

Preserve target identity. Do not invent missing groups or switch to another molecule. Return `proposed_smiles: null` if evidence is insufficient.

Return exactly one JSON object with `candidate_id`, `molecule_label`, `proposed_smiles`, `repair_action`, `source_basis`, `uncertainty_reason`, and `confidence`. `repair_action` must be `fixed_smiles|cannot_fix|reject`. Use `fixed_smiles` only when `proposed_smiles` contains a concrete candidate for renewed validation.
