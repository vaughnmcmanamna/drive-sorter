"""Create an illustrative GIF for the Drive Sorter README or portfolio."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "demo" / "drive-sorter-demo.gif"
ICON = ROOT / "assets" / "drive-sorter-icon.png"
SIZE = (900, 560)

DESKTOP = "#008080"
WINDOW = "#c0c0c0"
WHITE = "#ffffff"
BLACK = "#000000"
SHADOW = "#808080"
TITLE = "#000080"
GREEN = "#008000"
AMBER = "#804000"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    filename = "arialbd.ttf" if bold else "arial.ttf"
    return ImageFont.truetype(Path("C:/Windows/Fonts") / filename, size)


def raised(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    draw.line((left, bottom, right, bottom), fill=BLACK)
    draw.line((right, top, right, bottom), fill=BLACK)
    draw.line((left, top, right - 1, top), fill=WHITE)
    draw.line((left, top, left, bottom - 1), fill=WHITE)
    draw.line((left + 1, bottom - 1, right - 1, bottom - 1), fill=SHADOW)
    draw.line((right - 1, top + 1, right - 1, bottom - 1), fill=SHADOW)


def sunken(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    left, top, right, bottom = box
    draw.line((left, top, right, top), fill=BLACK)
    draw.line((left, top, left, bottom), fill=BLACK)
    draw.line((left + 1, top + 1, right - 1, top + 1), fill=SHADOW)
    draw.line((left + 1, top + 1, left + 1, bottom - 1), fill=SHADOW)
    draw.line((left, bottom, right, bottom), fill=WHITE)
    draw.line((right, top, right, bottom), fill=WHITE)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int = 14, bold: bool = False, fill: str = BLACK) -> None:
    draw.text(xy, text, fill=fill, font=font(size, bold))


def button(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str) -> None:
    draw.rectangle(box, fill=WINDOW)
    raised(draw, box)
    text_box = draw.textbbox((0, 0), text, font=font(13))
    width = text_box[2] - text_box[0]
    height = text_box[3] - text_box[1]
    left, top, right, bottom = box
    label(draw, ((left + right - width) // 2, (top + bottom - height) // 2 - 1), text, 13)


def base_frame() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, DESKTOP)
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 28, 872, 528), fill=BLACK)
    draw.rectangle((32, 24, 868, 524), fill=WINDOW)
    draw.rectangle((38, 30, 862, 70), fill=TITLE)
    icon = Image.open(ICON).convert("RGBA").resize((28, 28), Image.Resampling.NEAREST)
    image.alpha_composite(icon, (46, 36)) if image.mode == "RGBA" else image.paste(icon, (46, 36), icon)
    label(draw, (82, 40), "Drive Sorter", 17, True, WHITE)
    label(draw, (82, 57), "Preview first. Move only after confirmation.", 10, False, WHITE)

    draw.rectangle((52, 88, 848, 178), fill=WINDOW)
    raised(draw, (52, 88, 848, 178))
    draw.rectangle((64, 82, 167, 99), fill=WINDOW)
    label(draw, (72, 82), "Source folder", 12)
    draw.rectangle((68, 112, 604, 143), fill=WHITE)
    sunken(draw, (68, 112, 604, 143))
    label(draw, (77, 120), r"C:\Videos\Game Clips", 13)
    button(draw, (620, 112, 700, 143), "Browse")
    button(draw, (712, 112, 772, 143), "Scan")
    button(draw, (780, 112, 838, 143), "Organize")
    return image, draw


def scanning_frame() -> Image.Image:
    image, draw = base_frame()
    draw.rectangle((52, 196, 848, 452), fill=WINDOW)
    raised(draw, (52, 196, 848, 452))
    draw.rectangle((64, 190, 142, 207), fill=WINDOW)
    label(draw, (72, 190), "Move plan", 12)
    label(draw, (76, 220), "SCANNING...", 15, True, TITLE)
    label(draw, (76, 252), "Reading metadata: 18 / 48 - capture_2024-06-08.mp4", 13)
    draw.rectangle((76, 286, 824, 312), fill=WHITE)
    sunken(draw, (76, 286, 824, 312))
    draw.rectangle((79, 289, 357, 309), fill=TITLE)
    label(draw, (76, 338), "[ SCANNING ]", 14, True, TITLE)
    label(draw, (55, 486), "Reading video metadata...", 12)
    return image


def summary_frame() -> Image.Image:
    image, draw = base_frame()
    draw.rectangle((52, 196, 848, 452), fill=WINDOW)
    raised(draw, (52, 196, 848, 452))
    draw.rectangle((64, 190, 142, 207), fill=WINDOW)
    label(draw, (72, 190), "Move plan", 12)
    label(draw, (76, 220), "SCAN COMPLETE", 15, True, TITLE)
    label(draw, (76, 250), "48 clips found", 13)
    label(draw, (76, 274), "42 READY TO ORGANIZE", 13, True, GREEN)
    label(draw, (76, 298), "4 going to Unsorted    2 conflicts", 13, False, AMBER)
    label(draw, (76, 334), "READY DESTINATIONS", 13, True)
    label(draw, (96, 360), "VALORANT / 2024", 13)
    label(draw, (610, 360), "18 files - CREATE", 13, False, GREEN)
    label(draw, (96, 386), "Call of Duty HQ / 2024", 13)
    label(draw, (610, 386), "24 files - CREATE", 13, False, GREEN)
    label(draw, (76, 420), "[ SCAN COMPLETE ]", 14, True, GREEN)
    label(draw, (55, 486), "48 clips scanned - 42 ready to organize", 12)
    return image


def complete_frame() -> Image.Image:
    image, draw = base_frame()
    draw.rectangle((52, 196, 848, 452), fill=WINDOW)
    raised(draw, (52, 196, 848, 452))
    draw.rectangle((64, 190, 142, 207), fill=WINDOW)
    label(draw, (72, 190), "Move plan", 12)
    label(draw, (76, 232), "ORGANIZATION COMPLETE", 16, True, GREEN)
    label(draw, (76, 278), "42 ready files moved successfully", 14, True)
    label(draw, (76, 310), "4 clips sent to Unsorted", 13)
    label(draw, (76, 336), "2 conflicts were safely skipped", 13)
    label(draw, (76, 402), "[ ORGANIZATION COMPLETE ]", 14, True, GREEN)
    label(draw, (55, 486), "Complete: all ready files moved successfully.", 12)
    return image


OUTPUT.parent.mkdir(parents=True, exist_ok=True)
frames = [scanning_frame(), summary_frame(), complete_frame()]
frames[0].save(OUTPUT, save_all=True, append_images=frames[1:], duration=[1400, 1800, 2200], loop=0)
print(f"Created {OUTPUT}")
