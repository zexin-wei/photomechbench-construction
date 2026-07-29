# Stage 3 Provisional SMILES Proposal

Propose a provisional single-molecule SMILES for the exact target in the paper.

- Use the target label, paper text, captions, schemes, and supplied molecular figures together.
- Do not infer SMILES from the label alone.
- Do not switch to a same-paper analogue, control, reagent, precursor, or product.
- Do not silently replace a metal complex or multicomponent target with a free ligand.
- If the structure is not sufficiently supported, return `proposed_smiles: null`.

Return exactly one JSON object with `candidate_id`, `molecule_label`, `proposed_smiles`, `source_basis`, `single_molecule_intent`, `same_paper_confusion_risk`, `structure_features_claimed`, `uncertainty_reason`, `final_decision`, and `confidence`.

`source_basis` must be one of `paper_structure_image|paper_text_name|paper_caption|supporting_info_reference|unclear`. `final_decision` must be `pass|fail`. Use `pass` only when a concrete SMILES is proposed for RDKit and identity validation.
