"""
Favicon generator for Stockfirm CRM
Generates favicon.ico with green and black colors - ST letters
"""
from PIL import Image, ImageDraw
import os

def generate_favicon():
    """Generate favicon.ico with green and black design - ST letters"""
    
    # Create new image (256x256 for better quality, will be scaled down)
    size = 256
    img = Image.new('RGBA', (size, size), color=(255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    
    # Define colors
    dark_green = (34, 197, 94)      # #22c55e - vibrant green
    black = (15, 23, 42)             # #0f172a - dark black
    light_green = (74, 222, 128)     # #4ade80 - lighter green
    
    # Draw background circle (black)
    margin = 10
    draw.ellipse([margin, margin, size-margin, size-margin], 
                 fill=black, outline=None)
    
    # Draw "ST" letters with green
    # Letter "S" - left side
    # Upper curve of S
    draw.arc([50, 40, 120, 110], start=0, end=180, fill=light_green, width=18)
    # Middle bar of S
    draw.line([(120, 90), (50, 130)], fill=dark_green, width=18)
    # Lower curve of S
    draw.arc([50, 120, 120, 190], start=180, end=360, fill=light_green, width=18)
    
    # Letter "T" - right side
    # Top horizontal bar of T
    draw.rectangle([130, 45, 210, 65], fill=light_green)
    # Vertical stem of T
    draw.rectangle([160, 65, 180, 190], fill=dark_green)
    
    # Save as different sizes for favicon
    # 16x16
    img_16 = img.resize((16, 16), Image.Resampling.LANCZOS)
    # 32x32
    img_32 = img.resize((32, 32), Image.Resampling.LANCZOS)
    # 64x64
    img_64 = img.resize((64, 64), Image.Resampling.LANCZOS)
    
    # Save favicon.ico with multiple sizes
    favicon_path = os.path.join(os.path.dirname(__file__), 'crm', 'static', 'favicon.ico')
    os.makedirs(os.path.dirname(favicon_path), exist_ok=True)
    
    img.save(favicon_path, format='ICO', size=[(16, 16), (32, 32), (64, 64), (256, 256)])
    
    # Also save PNG versions for web use
    png_path = os.path.join(os.path.dirname(__file__), 'crm', 'static', 'favicon.png')
    img_32.save(png_path, format='PNG')
    
    print(f"✓ Favicon generated successfully!")
    print(f"  - favicon.ico: {favicon_path}")
    print(f"  - favicon.png: {png_path}")
    print(f"\nDesign: ST (Stockfirm) letters")
    print(f"Colors used:")
    print(f"  - Dark Green: #22c55e (RGB: {dark_green})")
    print(f"  - Light Green: #4ade80 (RGB: {light_green})")
    print(f"  - Black: #0f172a (RGB: {black})")

if __name__ == '__main__':
    generate_favicon()
