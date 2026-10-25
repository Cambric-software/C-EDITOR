"""Create the local, transparent PNG and ICO brand assets for the app."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
size = 1024
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# A deep-indigo rounded app tile with a warm creative accent and document mark.
d.rounded_rectangle((54, 54, 970, 970), radius=215, fill="#182B4D")
d.rounded_rectangle((82, 82, 942, 942), radius=185, fill="#244B7C")
d.ellipse((660, 104, 902, 346), fill="#F4B544")
d.rounded_rectangle((238, 190, 700, 838), radius=62, fill="#F8FBFF")
d.polygon([(570, 190), (700, 320), (570, 320)], fill="#D6E6F7")
d.line((328, 426, 598, 426), fill="#315C8A", width=38)
d.line((328, 530, 598, 530), fill="#315C8A", width=38)
d.line((328, 634, 520, 634), fill="#315C8A", width=38)
d.rounded_rectangle((650, 642, 826, 820), radius=34, fill="#F4B544")
d.polygon([(681, 770), (722, 802), (798, 680), (765, 647)], fill="#182B4D")

png = ASSETS / "studio_logo.png"
ico = ASSETS / "studio_logo.ico"
img.save(png, "PNG")
img.save(ico, "ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(png)
print(ico)
