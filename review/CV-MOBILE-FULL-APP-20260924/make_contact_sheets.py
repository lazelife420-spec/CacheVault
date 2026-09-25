from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parent
font_path = r'C:\Windows\Fonts\arial.ttf'
font_bold_path = r'C:\Windows\Fonts\arialbd.ttf'
font = ImageFont.truetype(font_path, 28)
small = ImageFont.truetype(font_path, 20)
bold = ImageFont.truetype(font_bold_path, 34)

def fit(image, size):
    image = image.convert('RGB')
    image.thumbnail(size, Image.Resampling.LANCZOS)
    return image

def before_after(before_path, after_path, output, title):
    before = Image.open(before_path)
    after = Image.open(after_path)
    width = 560
    left = fit(before, (width, 1180))
    right = fit(after, (width, 1180))
    canvas = Image.new('RGB', (width * 2 + 72, 1260), '#0b0f14')
    draw = ImageDraw.Draw(canvas)
    draw.text((24, 16), title, fill='#f4f7f8', font=bold)
    draw.text((24, 66), 'BEFORE', fill='#d6a84f', font=font)
    draw.text((width + 48, 66), 'AFTER · S23', fill='#00d1b2', font=font)
    canvas.paste(left, (24, 110))
    canvas.paste(right, (width + 48, 110))
    canvas.save(output)

before_after(
    root.parent / 'CV-MOBILE-1-PHYSICAL-20260924' / 'phys_home_unpaired2.png',
    root / 'HOME_EMPTY_AFTER.png', root / 'HOME_EMPTY_BEFORE_AFTER.png',
    'Home · empty local vault')
before_after(
    root.parent / 'CV-MOBILE-1-PHYSICAL-20260924' / 'phys_home_after_restart.png',
    root / 'HOME_POPULATED_AFTER.png', root / 'HOME_POPULATED_BEFORE_AFTER.png',
    'Home · populated local vault')

screens = [
    ('Home · empty', 'HOME_EMPTY_AFTER.png'),
    ('Home · populated', 'HOME_POPULATED_AFTER.png'),
    ('Search', 'SEARCH_AFTER.png'),
    ('Add / Save', 'ADD_AFTER.png'),
    ('Item detail', 'ITEM_DETAIL_AFTER.png'),
    ('Safes', 'SAFES_AFTER.png'),
    ('Safe content', 'SAFE_CONTENT_AFTER.png'),
    ('Activity', 'ACTIVITY_AFTER.png'),
    ('Recently Removed', 'RECENTLY_REMOVED_AFTER.png'),
    ('Share intake', 'SHARE_INTAKE_AFTER.png'),
    ('Paired PC · unpaired', 'PAIRED_PC_AFTER.png'),
    ('Settings', 'SETTINGS_AFTER.png'),
]

def sheet(output, cols, tile_w, title):
    tile_h = round(tile_w * 2340 / 1080)
    label_h, pad = 56, 22
    rows = (len(screens) + cols - 1) // cols
    canvas = Image.new('RGB', (pad + cols * (tile_w + pad), 82 + rows * (tile_h + label_h + pad)), '#0b0f14')
    draw = ImageDraw.Draw(canvas)
    draw.text((pad, 20), title, fill='#f4f7f8', font=bold)
    for index, (label, filename) in enumerate(screens):
        col, row = index % cols, index // cols
        x = pad + col * (tile_w + pad)
        y = 82 + row * (tile_h + label_h + pad)
        draw.text((x, y + 8), f'{index + 1:02d}  {label}', fill='#00d1b2', font=small)
        image = fit(Image.open(root / filename), (tile_w, tile_h))
        canvas.paste(image, (x, y + label_h))
        draw.rectangle((x, y + label_h, x + tile_w, y + label_h + tile_h), outline='#29313a', width=2)
    canvas.save(root / output)

sheet('S23_FULL_APP_CONTACT_SHEET.png', 4, 260, 'Cache Vault Mobile · Full app · Galaxy S23')
sheet('MOBILE_FULL_APP_FLOW_CONTACT_SHEET.png', 3, 340, 'Cache Vault Mobile · Primary flows')
