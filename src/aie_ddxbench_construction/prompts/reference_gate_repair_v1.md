# Stage 4 Deterministic-Gate Repair

Repair only the reported deterministic local-gate issues. Return the complete v0.4 JSON object, not a patch or wrapper.

Preserve `case_id`, `version`, `track`, `public_input`, `hidden_reference.source_article`, and the locked SMILES exactly. Do not add structure-resolution fields to the case. Do not invent evidence, quotations, or results. Replace a bad `paper_quote` only with an exact continuous source span and narrow the linked claim if necessary.
