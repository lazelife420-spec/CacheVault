from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent
font_regular = ImageFont.truetype(r'C:\Windows\Fonts\arial.ttf', 16)
font_bold = ImageFont.truetype(r'C:\Windows\Fonts\arialbd.ttf', 24)
items = [
    ('Search · S23', 'SEARCH_S23.png'), ('Search · Emulator', 'SEARCH_EMULATOR.png'),
    ('Save shortcut · S23', 'ADD_S23.png'), ('Save shortcut · Emulator', 'ADD_EMULATOR.png'),
    ('Safes shortcut · S23', 'SAFES_S23.png'), ('Safes shortcut · Emulator', 'SAFES_EMULATOR.png'),
    ('Share text · S23', 'SHARE_TEXT_S23.png'), ('Share text · Emulator', 'SHARE_TEXT_EMULATOR.png'),
    ('Share URL · S23', 'SHARE_URL_S23.png'), ('Share URL · Emulator', 'SHARE_URL_EMULATOR.png'),
    ('Share image · S23', 'SHARE_IMAGE_S23.png'), ('Share image · Emulator', 'SHARE_IMAGE_EMULATOR.png'),
]
cols, tile_w, pad, label_h, title_h = 4, 260, 18, 34, 64
tile_h = round(tile_w * 2340 / 1080)
rows = (len(items) + cols - 1) // cols
canvas = Image.new('RGB', (pad + cols * (tile_w + pad), title_h + rows * (tile_h + label_h + pad)), '#0b0f14')
draw = ImageDraw.Draw(canvas)
draw.text((pad, 15), 'Cache Vault · Android system integration', font=font_bold, fill='#f4f7f8')
for i, (label, filename) in enumerate(items):
    col, row = i % cols, i // cols
    x, y = pad + col * (tile_w + pad), title_h + row * (tile_h + label_h + pad)
    draw.text((x, y + 7), label, font=font_regular, fill='#00c6a6')
    image = Image.open(root / filename).convert('RGB')
    image.thumbnail((tile_w, tile_h), Image.Resampling.LANCZOS)
    canvas.paste(image, (x, y + label_h))
    draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline='#29313a', width=2)
canvas.save(root / 'SYSTEM_INTEGRATION_CONTACT_SHEET.png')
