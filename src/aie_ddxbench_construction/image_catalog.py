"""Build a stable image catalog and visual contact sheets for parsed papers."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote

from PIL import Image, ImageDraw, ImageFont, ImageOps

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\((?:<)?([^)>\s]+)(?:>)?(?:\s+['\"].*?['\"])?\)")
CAPTION_RE = re.compile(r"\b(?:fig(?:ure)?|scheme|table)\s*[.]?\s*(?:s?\d+|[a-z])", re.IGNORECASE)
CAPTION_START_RE = re.compile(r"^(?:fig(?:ure)?|scheme|table)\s*[.]?\s*(?:s?\d+|[a-z])", re.IGNORECASE)
CAPTION_LINE_RE = re.compile(r"^(?:fig(?:ure)?|scheme|table)\s*[.]?\s*(?:s?\d+|[a-z]).*$", re.IGNORECASE | re.MULTILINE)


def discover_image_paths(
    *,
    source_image_dir: Path,
) -> list[Path]:
    """Return unique images from the MinerU output directory."""
    paths = (
        [
            path.resolve()
            for path in sorted(source_image_dir.rglob("*"))
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
        if source_image_dir.is_dir()
        else []
    )
    unique: dict[str, Path] = {}
    for path in paths:
        unique.setdefault(str(path).lower(), path)
    return list(unique.values())


def build_image_catalog(source_md: Path, image_paths: Iterable[Path]) -> dict[str, Any]:
    """Associate stable IDs with images and nearby Markdown caption context."""
    text = source_md.read_text(encoding="utf-8", errors="replace")
    available = [path.resolve() for path in image_paths]
    by_name: dict[str, list[Path]] = {}
    for path in available:
        by_name.setdefault(path.name.lower(), []).append(path)

    ordered: list[tuple[Path, str, str]] = []
    used: set[str] = set()
    for match in MARKDOWN_IMAGE_RE.finditer(text):
        reference = unquote(match.group(1)).replace("\\", "/")
        name = Path(reference).name.lower()
        choices = by_name.get(name, [])
        path = next((item for item in choices if str(item).lower() not in used), choices[0] if choices else None)
        if path is None or str(path).lower() in used:
            continue
        used.add(str(path).lower())
        ordered.append((path, reference, _caption_context(text, match.start(), match.end())))

    for path in available:
        if str(path).lower() not in used:
            ordered.append((path, "", ""))

    records = []
    for index, (path, reference, caption) in enumerate(ordered, start=1):
        records.append(
            {
                "image_id": f"I{index:03d}",
                "path": str(path),
                "filename": path.name,
                "markdown_reference": reference,
                "caption_context": caption,
                "sha256": _sha256(path),
            }
        )
    return {"source_markdown": str(source_md.resolve()), "image_count": len(records), "images": records}


def prompt_image_records(catalog: dict[str, Any], *, caption_limit: int = 500) -> list[dict[str, str]]:
    """Return compact records suitable for Stage 1 and Stage 2 prompts."""
    return [
        {
            "image_id": str(row["image_id"]),
            "filename": str(row["filename"]),
            "caption_context": str(row.get("caption_context") or "")[:caption_limit],
        }
        for row in catalog.get("images", [])
    ]


def select_catalog_records(catalog: dict[str, Any], image_ids: Iterable[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Resolve model-selected IDs in request order and report unknown IDs."""
    index = {str(row["image_id"]): row for row in catalog.get("images", [])}
    selected: list[dict[str, Any]] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for raw_id in image_ids:
        image_id = str(raw_id)
        if image_id in seen:
            continue
        seen.add(image_id)
        if image_id in index:
            selected.append(index[image_id])
        else:
            unknown.append(image_id)
    return selected, unknown


def render_contact_sheets(
    records: list[dict[str, Any]],
    *,
    output_dir: Path,
    per_sheet: int = 12,
) -> tuple[Path, ...]:
    """Render labeled previews; original images remain unchanged for Stage 3."""
    if not records:
        return ()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for page_index, start in enumerate(range(0, len(records), per_sheet), start=1):
        page = records[start : start + per_sheet]
        canvas = Image.new("RGB", (1500, 400 * ((len(page) + 2) // 3)), "white")
        draw = ImageDraw.Draw(canvas)
        font = ImageFont.load_default()
        for offset, row in enumerate(page):
            col, grid_row = offset % 3, offset // 3
            x, y = col * 500, grid_row * 400
            try:
                with Image.open(row["path"]) as source:
                    preview = ImageOps.contain(source.convert("RGB"), (450, 300))
            except Exception:
                preview = Image.new("RGB", (450, 300), "#eeeeee")
            canvas.paste(preview, (x + (500 - preview.width) // 2, y + 10))
            label = f"{row['image_id']}  {row['filename']}"
            draw.text((x + 15, y + 320), label[:70], fill="black", font=font)
            caption = _single_line(str(row.get("caption_context") or ""))
            draw.text((x + 15, y + 342), caption[:76], fill="#333333", font=font)
            draw.rectangle((x, y, x + 499, y + 399), outline="#cccccc", width=1)
        path = output_dir / f"contact_sheet_{page_index:02d}.png"
        canvas.save(path)
        paths.append(path)
    return tuple(paths)


def _caption_context(text: str, start: int, end: int) -> str:
    formal_candidates: list[tuple[int, str]] = []
    before_formal = text[max(0, start - 2000) : start]
    after_formal = text[end : min(len(text), end + 5000)]
    for match in CAPTION_LINE_RE.finditer(before_formal):
        formal_candidates.append((len(before_formal) - match.end(), _single_line(match.group(0))))
    for match in CAPTION_LINE_RE.finditer(after_formal):
        formal_candidates.append((match.start(), _single_line(match.group(0))))
    for block in (item.strip() for item in re.split(r"\n\s*\n", before_formal) if item.strip()):
        clean = _single_line(block)
        if CAPTION_START_RE.match(clean):
            formal_candidates.append((len(before_formal) - before_formal.rfind(block), clean))
    for block in (item.strip() for item in re.split(r"\n\s*\n", after_formal) if item.strip()):
        clean = _single_line(block)
        if CAPTION_START_RE.match(clean):
            formal_candidates.append((after_formal.find(block), clean))
    if formal_candidates:
        return min(formal_candidates, key=lambda item: item[0])[1][:1000]

    before_start = max(0, start - 900)
    before = text[before_start:start]
    previous_images = list(MARKDOWN_IMAGE_RE.finditer(before))
    if previous_images:
        before = before[previous_images[-1].end() :]
    after = text[end : min(len(text), end + 1200)]
    next_image = MARKDOWN_IMAGE_RE.search(after)
    if next_image:
        after = after[: next_image.start()]
    candidates: list[tuple[int, str]] = []
    for block in (item.strip() for item in re.split(r"\n\s*\n", before) if item.strip()):
        if CAPTION_RE.search(block):
            candidates.append((len(before) - before.rfind(block), block))
    for block in (item.strip() for item in re.split(r"\n\s*\n", after) if item.strip()):
        if CAPTION_RE.search(block):
            candidates.append((after.find(block), block))
    if candidates:
        return _single_line(min(candidates, key=lambda item: item[0])[1])[:1000]
    return _single_line((before[-350:] + " " + after[:500]).strip())[:1000]


def _single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
