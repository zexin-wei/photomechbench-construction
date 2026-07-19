# Stage 3 Visual Molecular Identity Review

Review molecular identity using the supplied side-by-side image. The image contains source-paper molecular structure evidence and an RDKit depiction of the candidate SMILES. The source-paper panel is the identity authority. RDKit validity alone is not identity proof.

Check scaffold and bond connectivity, linker length, substituent identity and position, heteroatom composition, formal charge, and explicitly specified stereochemistry. For metal-containing or multicomponent targets, also check the metal center, ligands, counterions, and other components required by the paper-defined target. Audit same-paper analogue, control, precursor, regioisomer, and stereoisomer confusion.

Return exactly one JSON object with `candidate_id`, `molecule_label`, `candidate_smiles`, `structure_match_status`, `single_molecule_ok`, `target_label_ok`, `not_confused_with_other_paper_molecule`, `confusion_risk`, `final_stage3_decision`, `confidence`, `failure_mode`, `key_matching_features`, `specific_concerns`, and `recommended_next_action`.

Only an explicit `confirmed_match` plus `confirmed_smiles` can create a locked structure. Copy the supplied candidate SMILES; do not rewrite it.
