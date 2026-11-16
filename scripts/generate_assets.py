"""Genera un emblema SSG propio. No reproduce un escudo nacional ni un sello oficial."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
image = Image.new("RGBA", (384, 384), (255, 255, 255, 0))
draw = ImageDraw.Draw(image)
draw.ellipse((13, 13, 371, 371), fill="#691c32", outline="#b99b68", width=8)
draw.ellipse((31, 31, 353, 353), outline="#d8c29c", width=3)
draw.polygon(
    [(115, 91), (269, 91), (269, 219), (244, 259), (192, 290), (140, 259), (115, 219)],
    fill="#f6f2e9",
)
font_path = Path("C:/Windows/Fonts/arialbd.ttf")
font = (
    ImageFont.truetype(str(font_path), 54)
    if font_path.exists()
    else ImageFont.load_default(size=54)
)
draw.text((192, 185), "SSG", font=font, fill="#691c32", anchor="mm")
draw.line([(144, 228), (240, 228)], fill="#9f7a3e", width=7)
for dest in [ROOT / "backend/app/assets/sello-ssg.png", ROOT / "frontend/src/assets/sello-ssg.png"]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest)
