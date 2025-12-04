import os
import uuid
import colorsys
import math
import base64
from flask import Flask, render_template, request, jsonify, url_for
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter

app = Flask(__name__)

# --- 配置区域 ---
app.config['UPLOAD_FOLDER'] = 'static'
# 【注意】必须确保 fonts 目录下有 font.ttf 文件
app.config['FONT_PATH'] = 'fonts/font.ttf'

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def rgb_to_hex(rgb):
    """辅助函数：RGB转HEX"""
    return '#{:02x}{:02x}{:02x}'.format(rgb[0], rgb[1], rgb[2])

def clean_and_brighten_color_v5(rgb_color, is_start_color=True):
    """
    V5 终极调色算法：高亮、鲜艳 (保持不变)
    """
    r, g, b = rgb_color
    h, s, v = colorsys.rgb_to_hsv(r/255.0, g/255.0, b/255.0)

    if is_start_color:
        # === 左侧（高光） ===
        v = 1.0 
        s = min(s, 0.55) 
        s = max(s, 0.20)
        if 0.0 < h < 0.15: 
            h = (h + 0.12) / 2
    else:
        # === 右侧（鲜艳暗部） ===
        # 暴力提亮，最低 0.85
        v = max(v, 0.85)
        # 极致饱和度，最低 0.90
        s = max(s, 0.90)
        s = min(s, 1.0)
        # 去土色，往红色偏移
        if 0.05 < h < 0.2:
            h = h * 0.4 

    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r*255), int(g*255), int(b*255))

def analyze_colors_v5(image_path):
    """提取 V5 风格颜色 (保持不变)"""
    try:
        img = Image.open(image_path).convert('RGB')
        
        # 极度拉高饱和度 (3.0倍)
        enhancer = ImageEnhance.Color(img)
        img = enhancer.enhance(3.0) 
        
        small = img.resize((50, 50), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())
        pixels.sort(key=lambda p: p[0]*0.299 + p[1]*0.587 + p[2]*0.114)
        
        raw_shadow = pixels[int(len(pixels) * 0.1)] 
        raw_highlight = pixels[int(len(pixels) * 0.9)]
        
        final_highlight = clean_and_brighten_color_v5(raw_highlight, is_start_color=True)
        final_shadow = clean_and_brighten_color_v5(raw_shadow, is_start_color=False)
        
        return final_highlight, final_shadow
    except Exception as e:
        print(f"Color analysis failed: {e}")
        return (255, 245, 210), (255, 80, 40)

def create_gradient_text_png(text_content, font, c1, c2):
    """生成 PNG 水印图层 (正体，无斜切)"""
    ascent, descent = font.getmetrics()
    bbox = font.getbbox(text_content)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1] + descent
    
    padding = 100
    w = text_w + padding
    h = text_h + padding
    
    # 1. 绘制初始蒙版
    mask = Image.new('L', (w, h), 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.text((padding//2, padding//2 - bbox[1]), text_content, font=font, fill=255)
    
    # [已删除] 这里的斜体变换代码已被移除
    
    # 2. 绘制渐变
    base = Image.new('RGB', (w, h), c1)
    draw = ImageDraw.Draw(base)
    r1, g1, b1 = c1
    r2, g2, b2 = c2
    for x in range(w):
        ratio = x / w
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        draw.line([(x, 0), (x, h)], fill=(r, g, b))
        
    base.putalpha(mask)
    return base

def generate_svg_content(text, font_path, width, height, c1, c2):
    """生成 SVG 矢量内容 (正体，无斜切)"""
    try:
        with open(font_path, "rb") as f:
            font_data = base64.b64encode(f.read()).decode('utf-8')
    except Exception:
        font_data = ""

    hex_c1 = rgb_to_hex(c1)
    hex_c2 = rgb_to_hex(c2)
    
    # [已删除] 这里的 transform_attr 斜切属性已被移除
    
    svg_content = f"""<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      @font-face {{
        font-family: 'CustomFont';
        src: url('data:font/ttf;base64,{font_data}') format('truetype');
      }}
      .watermark-text {{
        font-family: 'CustomFont', sans-serif;
        font-size: 160px;
        font-weight: bold;
      }}
    </style>
    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:{hex_c1};stop-opacity:1" />
      <stop offset="100%" style="stop-color:{hex_c2};stop-opacity:1" />
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="4"/>
      <feOffset dx="4" dy="4" result="offsetblur"/>
      <feComponentTransfer>
        <feFuncA type="linear" slope="0.55"/>
      </feComponentTransfer>
      <feMerge> 
        <feMergeNode/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" 
        class="watermark-text" fill="url(#grad1)" filter="url(#shadow)">
    {text}
  </text>
</svg>"""
    return svg_content

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    if 'image' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['image']
    text_content = request.form.get('text', 'HASSELBLAD')
    
    if not text_content or text_content.strip() == "":
        text_content = "HASSELBLAD"

    if file.filename == '': return jsonify({'error': 'No file'}), 400

    unique_id = str(uuid.uuid4())
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
    source_filename = f"{unique_id}_source.{ext}"
    source_path = os.path.join(app.config['UPLOAD_FOLDER'], source_filename)
    file.save(source_path)

    try:
        # V5 终极调色
        c1, c2 = analyze_colors_v5(source_path)
        
        font_size = 160
        try:
            font = ImageFont.truetype(app.config['FONT_PATH'], font_size)
        except:
            return jsonify({'error': '无法加载字体文件 (fonts/font.ttf)'}), 500

        # 生成 PNG (正体)
        text_layer = create_gradient_text_png(text_content, font, c1, c2)
        
        # 添加投影
        shadow_mask = text_layer.getchannel('A')
        shadow_layer = Image.new('RGBA', text_layer.size, (0, 0, 0, 0))
        shadow_fill = Image.new('RGBA', text_layer.size, (0, 0, 0, 140)) 
        shadow_layer.paste(shadow_fill, (0,0), mask=shadow_mask)
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=10))
        
        canvas = Image.new('RGBA', text_layer.size, (0,0,0,0))
        canvas.paste(shadow_layer, (6, 6), mask=shadow_layer)
        canvas.paste(text_layer, (0, 0), mask=text_layer)
        
        output_png = f"{unique_id}_watermark.png"
        output_path_png = os.path.join(app.config['UPLOAD_FOLDER'], output_png)
        canvas.save(output_path_png, "PNG")

        # 生成 SVG (正体)
        svg_content = generate_svg_content(
            text_content, 
            app.config['FONT_PATH'], 
            canvas.width, 
            canvas.height, 
            c1, c2
        )
        output_svg = f"{unique_id}_watermark.svg"
        output_path_svg = os.path.join(app.config['UPLOAD_FOLDER'], output_svg)
        with open(output_path_svg, "w", encoding="utf-8") as f:
            f.write(svg_content)

        return jsonify({
            'source_url': url_for('static', filename=source_filename),
            'watermark_url': url_for('static', filename=output_png),
            'svg_url': url_for('static', filename=output_svg),
            'colors': [c1, c2]
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)