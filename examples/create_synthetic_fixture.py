"""Create the redistributable source-structure image used by the example."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main() -> None:
    output = Path(__file__).parent / "fixtures" / "source_structure.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (900, 520), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()
    draw.text((35, 28), "Synthetic Scheme 1: target molecule A", fill="black", font=font)
    draw.line((260, 265, 420, 265), fill="black", width=5)
    draw.line((420, 265, 560, 190), fill="black", width=5)
    draw.text((208, 250), "CH3", fill="black", font=font)
    draw.text((405, 285), "CH2", fill="black", font=font)
    draw.text((565, 174), "OH", fill="black", font=font)
    draw.text((35, 465), "This is a synthetic, openly redistributable test fixture.", fill="black", font=font)
    image.save(output)


if __name__ == "__main__":
    main()
