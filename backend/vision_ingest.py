"""用 gpt-4o 看照片，起草一张"回忆卡片"。
AI 只根据画面推测，个人才知道的事（时间/人物/发生了什么）留给你补充。"""
import base64
import io
import os
from typing import List

from PIL import Image, ImageOps
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage

from llm_config import make_chat, struct_method

# 建库(看图起草卡片)默认用更快的小模型——起草不需要 32b 的细腻，
# 32b 留给真正需要它的陪伴对话。想改用 .env 里的 INGEST_MODEL。
INGEST_MODEL = os.environ.get("INGEST_MODEL", "qwen2.5vl:7b")
# 送进模型前把图缩到这个最长边——手机照片动辄 5000+ 像素，缩到 1024 看图又快又不掉卡片质量。
MAX_SIDE = 1024


def _shrink_for_vision(image_bytes: bytes) -> bytes:
    """只缩"送给模型看"的那份；原图照常存档、照常显示，不动。"""
    try:
        im = Image.open(io.BytesIO(image_bytes))
        im = ImageOps.exif_transpose(im).convert("RGB")   # 先按 EXIF 摆正，模型看到的才是正的
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=85)
        return buf.getvalue()
    except Exception:
        return image_bytes  # 缩不动就用原图，别让建库直接挂


class MemoryCard(BaseModel):
    title: str = Field(description="给这段回忆起一个温暖的小标题")
    where: str = Field(description="照片里看起来是什么地方；看不出就写'（请你补充）'")
    when: str = Field(description="能否推测季节/时段；具体日期看不出就写'（请你补充）'")
    who: str = Field(description="画面里有没有人；具体是谁看不出就写'（请你补充）'")
    what_happened: str = Field(description="画面像是在做什么；细节看不出就写'（请你补充）'")
    see: str = Field(description="画面里能看到的具体东西：颜色、光线、物体")
    hear: str = Field(description="那种场景里可能会有的声音（温和地猜）")
    touch: str = Field(description="那种场景里皮肤可能感觉到的：风、阳光、水、材质")
    smell_taste: str = Field(description="那种场景可能有的气味或味道")
    weather_temp: str = Field(description="画面透露的天气/温度线索")
    food: str = Field(description="如果画面里有食物，是什么；没有就留空")
    emotion: str = Field(description="这张照片传达出的温暖、平静或开心的感觉")
    grounding_questions: List[str] = Field(
        description="4-6 个温柔的、一次只问一个的着陆问题，围绕这张照片的感官/空间/情绪细节，用第二人称'你'，口气像很在乎 ta 的朋友"
    )


SYS = """你在帮一个有 PTSD、会经历闪回的人，建立一个"美好回忆"的着陆(grounding)库。
现在给你一张 ta 珍藏的、代表美好时刻的照片。

请温柔、仔细地观察这张照片，起草一张"回忆卡片"：
- 能从画面看出来的（地点、看到的东西、光线颜色、可能的天气、氛围），尽量具体地写。
- 那种场景里"通常会有"的感官（声音、触感、气味），可以温和地、试探性地写，帮 ta 打开回忆。
- 只有 ta 本人才知道的（确切时间、和谁、发生了什么），如果看不出来，就**只写"（请你补充）"这五个字本身**，
  后面绝不要再加任何推测或补充说明（不要写"（请你补充）：可能有重要的人同行"这种）。
- 特别注意：**不要臆测这是什么活动或事件**（郊游、旅行、聚会、约会……），除非画面里明确显示。
  一辆车、一片海、一间厨房，都不等于任何特定事件——看不出就 what_happened 写"（请你补充）"。
- grounding_questions 要温柔、简短、一次一个，像陪伴者会问的那种，目的是把注意力带到具体、真实、安全的细节上。

语气始终温暖、平静、不评判。用中文。"""


def _to_dict(obj):
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    return dict(obj)


def draft_memory_from_image(image_bytes: bytes, mime: str = "image/jpeg", model: str = None) -> dict:
    """看图 -> 回忆卡片草稿(dict)。需要环境变量 OPENAI_API_KEY（可指向 z.ai）。"""
    small = _shrink_for_vision(image_bytes)          # 先缩小，看图快很多
    b64 = base64.b64encode(small).decode()
    # json_schema 方式：本地 Ollama 的视觉模型（Qwen2.5-VL）不支持 tools，
    # 但支持 json_schema 约束输出；OpenAI 的 gpt-4o 也支持，所以两边通吃。
    llm = make_chat(0.4, model=model or INGEST_MODEL, disable_thinking=False).with_structured_output(MemoryCard, method=struct_method())
    result = llm.invoke([
        SystemMessage(content=SYS),
        HumanMessage(content=[
            {"type": "text", "text": "这是我很珍惜的一张照片，请帮我起草这张回忆卡片。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]),
    ])
    return _to_dict(result)
