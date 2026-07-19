from __future__ import annotations

from pathlib import Path

from PIL import Image

from aie_ddxbench_construction.image_catalog import (
    build_image_catalog,
    render_contact_sheets,
    select_catalog_records,
)


def test_catalog_uses_markdown_order_and_caption_context(tmp_path: Path) -> None:
    image_a = tmp_path / "a.png"
    image_b = tmp_path / "b.png"
    Image.new("RGB", (20, 20), "white").save(image_a)
    Image.new("RGB", (20, 20), "black").save(image_b)
    source = tmp_path / "source.md"
    source.write_text(
        "![](b.png)\n\nFig. 2. Molecular structure of B.\n\n![](a.png)\n\nScheme 1. Synthesis of A.",
        encoding="utf-8",
    )

    catalog = build_image_catalog(source, [image_a, image_b])

    assert [row["filename"] for row in catalog["images"]] == ["b.png", "a.png"]
    assert catalog["images"][0]["image_id"] == "I001"
    assert "Fig. 2" in catalog["images"][0]["caption_context"]


def test_selected_images_render_to_labeled_contact_sheet(tmp_path: Path) -> None:
    image = tmp_path / "structure.png"
    Image.new("RGB", (100, 100), "white").save(image)
    catalog = {"images": [{"image_id": "I001", "path": str(image), "filename": image.name, "caption_context": "Fig. 1. Structure."}]}

    selected, unknown = select_catalog_records(catalog, ["I001", "I999"])
    sheets = render_contact_sheets(selected, output_dir=tmp_path / "sheets")

    assert [row["image_id"] for row in selected] == ["I001"]
    assert unknown == ["I999"]
    assert sheets[0].is_file()
