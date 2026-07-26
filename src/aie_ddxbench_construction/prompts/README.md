# Versioned Prompt Assets

These files are the authoritative static instructions for model-assisted
stages in the final PhotoMechBench raw-case construction workflow.

Python code may append only run-specific context, such as paper metadata,
parsed source text, candidate identity, locked SMILES, local-gate reports, or
the three independent-review artifacts. Stable policies, output contracts,
allowed decisions, and repair restrictions belong in these files.

Changing a prompt requires a new versioned filename and a corresponding
version update in the calling module. Historical prompts are not part of the
final release interface.
