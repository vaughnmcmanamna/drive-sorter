"""Create a multiresolution Windows ICO from the app's canonical PNG."""

from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "assets" / "drive-sorter-icon.png"
destination = ROOT / "assets" / "drive-sorter-icon.ico"

with Image.open(source) as image:
    image.convert("RGBA").save(
        destination,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )

print(f"Created {destination}")
