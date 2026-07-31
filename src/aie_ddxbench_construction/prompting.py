"""Versioned prompt loading and independent-review request construction."""

from __future__ import annotations

from importlib.resources import files

INDEPENDENT_REVIEW_PROMPT_VERSION = "independent_review_v2"
INDEPENDENT_REVIEW_SYSTEM_PROMPT = (
    "You are a strict reviewer of AIE and molecular-photophysics benchmark cases. "
    "Use only the three supplied artifacts and follow the required output template exactly. "
    "Do not reveal chain-of-thought, drafts, hidden reasoning, or <think> tags."
)


def load_prompt(name: str) -> str:
    path = files("aie_ddxbench_construction").joinpath(f"prompts/{name}.md")
    if not path.is_file():
        raise ValueError(f"Unknown prompt asset: {name}")
    return path.read_text(encoding="utf-8")


def build_independent_review_text(
    *,
    case_name: str,
    archive_mechanism: str,
    case_json_text: str,
    source_text: str,
    include_image: bool,
) -> str:
    """Build the three-artifact Stage 5 audit request without a machine path."""
    template_text = load_prompt(INDEPENDENT_REVIEW_PROMPT_VERSION)
    image_note = (
        "structure_match.png is attached as an image input. Perform the required visual structure check."
        if include_image
        else "structure_match.png is not attached. Mark image-dependent checks as unverifiable."
    )
    return f"""Review the three supplied case artifacts using the PhotoMechBench reference-alignment template below.

Mandatory constraints:
- Use only final_reference_alignment.json, source.md, and structure_match.png from this message.
- Do not browse, use remembered facts, or regenerate the JSON.
- Respond in English.
- Preserve the required output format; do not replace it with a free-form summary.
- Do not output chain-of-thought, drafts, <think> tags, or hidden reasoning. Output only the final review.
- Mark anything that cannot be checked from the supplied artifacts as unclear, unverifiable, or UNVERIFIABLE as required by the template.

Supplied artifacts:
1. final_reference_alignment.json
2. source.md
3. structure_match.png

Image status:
{image_note}

Case:
{case_name}

Archive mechanism:
{archive_mechanism}

====================
REVIEW TEMPLATE START
====================

{template_text}

====================
REVIEW TEMPLATE END
====================

====================
final_reference_alignment.json
====================

```json
{case_json_text}
```

====================
source.md
====================

```markdown
{source_text}
```
"""
