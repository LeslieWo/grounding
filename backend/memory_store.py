"""本地存储：回忆卡片存成 data/memories.json，照片存在 data/photos/。
全部只在你自己电脑上。"""
import io
import json
import os
import uuid

from PIL import Image, ImageOps

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "data")
PHOTOS = os.path.join(DATA, "photos")
DB = os.path.join(DATA, "memories.json")
CONFIG = os.path.join(DATA, "config.json")

# 回忆卡片的字段（中文标签 -> 存储键）
FIELDS = [
    ("小标题", "title"),
    ("地点（在哪）", "where"),
    ("时间（什么时候）", "when"),
    ("和谁在一起", "who"),
    ("发生了什么", "what_happened"),
    ("看到什么", "see"),
    ("听到什么", "hear"),
    ("摸到 / 身体的感觉", "touch"),
    ("气味 / 味道", "smell_taste"),
    ("天气 / 温度", "weather_temp"),
    ("吃了什么", "food"),
    ("当时的心情", "emotion"),
]


def _ensure():
    os.makedirs(PHOTOS, exist_ok=True)
    if not os.path.exists(DB):
        with open(DB, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def load_memories():
    _ensure()
    try:
        with open(DB, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def upright_bytes(image_bytes, ext=".jpg"):
    """按 EXIF 方向把照片摆正，并把方向"烧"进像素（去掉 EXIF 标签）。
    手机照片常把方向存在标签里、像素没转，不摆正显示就会歪/倒。"""
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im = ImageOps.exif_transpose(im)          # 按 EXIF 真正旋转像素
        buf = io.BytesIO()
        if ext.lower() == ".png":
            im.save(buf, format="PNG")
        else:
            im.convert("RGB").save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception:
        return image_bytes                        # 处理不了就原样存，别让保存挂掉


def save_memory(chunk, image_bytes, ext=".jpg"):
    """新建或覆盖一段回忆。chunk 是 dict；image_bytes 是照片原始字节。"""
    _ensure()
    mid = chunk.get("id") or uuid.uuid4().hex[:8]
    chunk["id"] = mid
    img_name = f"{mid}{ext}"
    if image_bytes is not None:
        image_bytes = upright_bytes(image_bytes, ext)   # 存进去就是正的
        with open(os.path.join(PHOTOS, img_name), "wb") as f:
            f.write(image_bytes)
        chunk["image_path"] = os.path.join("data", "photos", img_name)
    mems = [m for m in load_memories() if m.get("id") != mid]
    mems.append(chunk)
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(mems, f, ensure_ascii=False, indent=2)
    return chunk


def update_memory(chunk):
    mems = load_memories()
    mems = [chunk if m.get("id") == chunk.get("id") else m for m in mems]
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(mems, f, ensure_ascii=False, indent=2)


def delete_memory(mid):
    mems = [m for m in load_memories() if m.get("id") != mid]
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(mems, f, ensure_ascii=False, indent=2)
    # 顺手删掉照片
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        p = os.path.join(PHOTOS, f"{mid}{ext}")
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


def image_abspath(rel_path):
    """把存储的相对路径转成绝对路径，方便 Streamlit 显示。"""
    if not rel_path:
        return None
    p = os.path.join(BASE, rel_path)
    return p if os.path.exists(p) else None


# ---- 可信联系人（发作时一键联系一个真人）----
def load_config():
    _ensure()
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"contact_name": "", "contact_note": ""}


def save_config(cfg):
    _ensure()
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
