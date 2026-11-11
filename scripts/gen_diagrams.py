"""用 Pillow 生成架构图与对比实验图表 PNG(供论文/报告使用)。

依赖: pip install pillow
输出: docs/diagrams/*.png
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "C:/Windows/Fonts/simhei.ttf"
OUT = Path(__file__).resolve().parent.parent / "docs" / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

# 配色
BLUE = (21, 101, 192)
GREEN = (46, 125, 50)
ORANGE = (239, 108, 0)
PURPLE = (106, 27, 154)
RED = (198, 40, 40)
GRAY = (117, 117, 117)
BG = (255, 255, 255)
BOX = (245, 245, 245)
LIGHT_BLUE = (227, 242, 253)
LIGHT_GREEN = (232, 245, 233)
LIGHT_ORANGE = (255, 243, 224)
LIGHT_PURPLE = (243, 229, 245)
LIGHT_RED = (252, 228, 236)


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_PATH, size)


def center_text(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, f: ImageFont, fill=(0, 0, 0)) -> None:
    bbox = draw.textbbox((0, 0), text, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x - w / 2, y - h / 2 - bbox[1]), text, font=f, fill=fill)


def rrect(draw: ImageDraw.ImageDraw, box, radius=10, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_arrow(draw, x1, y1, x2, y2, color=GRAY):
    draw.line([(x1, y1), (x2, y2)], fill=color, width=3)
    # 箭头
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    for da in (math.radians(150), math.radians(-150)):
        draw.line([(x2, y2), (x2 + 14 * math.cos(ang + da), y2 + 14 * math.sin(ang + da))],
                  fill=color, width=3)


def gen_architecture() -> None:
    """四层架构图。"""
    W, H = 900, 780
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title, f_layer, f_mod, f_small = font(30), font(22), font(17), font(13)

    center_text(d, W // 2, 40, "AI辅助自动化生活类签到系统 · 四层架构", f_title, (0, 0, 0))
    center_text(d, W // 2, 76, "感知-决策-执行-自愈 分层架构", f_small, GRAY)

    layers = [
        ("应用层  App Layer", ["用户配置", "任务编排 Scheduler", "结果通知 Notifier"], LIGHT_BLUE, BLUE),
        ("决策层  Decision Layer", ["LLM 语义理解", "页面解析 Parser", "异常诊断 Diagnostician"], LIGHT_GREEN, GREEN),
        ("感知层  Perception Layer", ["OCR PaddleOCR", "视觉大模型 Vision", "验证码识别 Captcha"], LIGHT_ORANGE, ORANGE),
        ("执行层  Execution Layer", ["请求构造", "浏览器自动化", "Cookie管理", "加密适配"], LIGHT_PURPLE, PURPLE),
    ]
    y = 110
    box_h = 140
    for name, mods, bgc, color in layers:
        rrect(d, (60, y, W - 60, y + box_h), 14, fill=bgc, outline=color, width=3)
        d.text((80, y + 12), name, font=f_layer, fill=color)
        # 模块子框
        mw = (W - 120 - 20 * (len(mods) - 1)) // len(mods)
        for i, m in enumerate(mods):
            mx = 80 + i * (mw + 20)
            rrect(d, (mx, y + 52, mx + mw, y + box_h - 18), 8, fill=(255, 255, 255), outline=color, width=2)
            center_text(d, mx + mw // 2, y + (52 + box_h - 18) // 2, m, f_mod, (0, 0, 0))
        y += box_h + 24
        if name.startswith("执行层"):
            pass

    # 自愈核心框
    core_y = y + 6
    rrect(d, (60, core_y, W - 60, core_y + 70), 14, fill=LIGHT_RED, outline=RED, width=3)
    d.text((80, core_y + 8), "核心: 自愈引擎 SelfHealEngine", font=f_layer, fill=RED)
    center_text(d, W // 2, core_y + 50, "监控 → 诊断 → 决策 → 自愈  (重试/重登/重析/验证码/降级/报警)", f_mod, (0, 0, 0))

    # 层级箭头
    ly = 110
    for _ in range(3):
        draw_arrow(d, W // 2, ly + box_h, W // 2, ly + box_h + 24)
        ly += box_h + 24
    draw_arrow(d, W // 2, core_y - 18, W // 2, core_y)
    # 反馈箭头
    d.line([(W - 60, core_y + 35), (W - 20, core_y + 35), (W - 20, 110 + 10)], fill=RED, width=3)

    img.save(OUT / "architecture.png")
    print("生成 architecture.png")


def gen_pipeline() -> None:
    """自愈闭环流程图(清晰布局)。"""
    W, H = 980, 900
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    f_title, f_node = font(28), font(16)

    center_text(d, W // 2, 36, "自愈闭环: 监控-诊断-决策-自愈", f_title, (0, 0, 0))

    w, h = 250, 56
    nodes = {
        "start": (490, 105, "开始签到"),
        "sense": (490, 185, "感知: 请求/页面/验证码"),
        "diag": (490, 275, "诊断: LLM 语义分类"),
        "ok": (800, 275, "签到成功"),
        "relogin": (155, 400, "重登刷新Cookie"),
        "rean": (385, 400, "重新分析生成逻辑"),
        "cap": (615, 400, "语义验证码识别"),
        "wait": (830, 400, "退避等待/降级"),
        "retry": (490, 520, "是否达上限?"),
        "fail": (155, 660, "最终失败并报警"),
        "log": (490, 780, "LLM归纳失败模式, 优化策略"),
    }
    colors = {
        "ok": (200, 230, 201), "fail": (255, 205, 210), "diag": (227, 242, 253),
        "log": (255, 249, 196),
    }
    for k, (x, y, t) in nodes.items():
        rrect(d, (x - w // 2, y - h // 2, x + w // 2, y + h // 2), 10,
              fill=colors.get(k, BOX), outline=(0, 0, 0), width=2)
        center_text(d, x, y, t, f_node, (0, 0, 0))

    def edge(a, b, label="", color=GRAY, lx=None, ly=None):
        ax, ay, _ = nodes[a]
        bx, by, _ = nodes[b]
        d.line([(ax, ay + h // 2), (bx, by - h // 2)], fill=color, width=3)
        if label:
            center_text(d, lx if lx is not None else (ax + bx) // 2,
                        ly if ly is not None else (ay + by) // 2, label, font(15), color)

    # 主链
    edge("start", "sense")
    edge("sense", "diag")
    edge("diag", "ok", "成功", GREEN, lx=680, ly=250)
    edge("diag", "relogin", "Cookie过期", BLUE, lx=250, ly=330)
    edge("diag", "rean", "加密升级", PURPLE, lx=380, ly=345)
    edge("diag", "cap", "验证码", ORANGE, lx=560, ly=345)
    edge("diag", "wait", "瞬时/风控", GRAY, lx=720, ly=330)
    # 动作汇总到重试判定
    edge("relogin", "retry", "", GRAY)
    edge("rean", "retry", "", GRAY)
    edge("cap", "retry", "", GRAY)
    edge("wait", "retry", "", GRAY)
    # 闭环与终止
    edge("ok", "log", "", GREEN)
    edge("retry", "sense", "否", BLUE, lx=560, ly=470)
    edge("retry", "fail", "是", RED, lx=250, ly=590)
    edge("fail", "log", "", RED)

    img.save(OUT / "pipeline.png")
    print("生成 pipeline.png")


def _panel(d: ImageDraw.ImageDraw, x, y, w, h, title, trad, ai, lo, hi) -> None:
    """单个指标柱状面板。"""
    f_t, f_lab, f_val = font(18), font(15), font(17)
    center_text(d, x + w // 2, y + 18, title, f_t, (0, 0, 0))
    base_y = y + h - 60
    plot_h = h - 110
    bw = 110
    x1, x2 = x + w // 2 - bw - 50, x + w // 2 + 50
    trad_h = max(4, (trad - lo) / (hi - lo) * plot_h)
    ai_h = max(4, (ai - lo) / (hi - lo) * plot_h)
    # 基线
    d.line([(x + 40, base_y), (x + w - 40, base_y)], fill=(0, 0, 0), width=2)
    # 传统条
    d.rectangle([x1, base_y - trad_h, x1 + bw, base_y], fill=(180, 180, 180))
    center_text(d, x1 + bw // 2, base_y - trad_h - 22, f"{trad:g}", f_val, (60, 60, 60))
    center_text(d, x1 + bw // 2, base_y + 20, "传统", f_lab, (60, 60, 60))
    # AI条
    d.rectangle([x2, base_y - ai_h, x2 + bw, base_y], fill=(76, 175, 80))
    center_text(d, x2 + bw // 2, base_y - ai_h - 22, f"{ai:g}", f_val, (27, 94, 32))
    center_text(d, x2 + bw // 2, base_y + 20, "AI方案", f_lab, (27, 94, 32))


def gen_comparison() -> None:
    """传统 vs AI 对比柱状图(两个独立面板: 成功率/人工干预)。"""
    W, H = 900, 520
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    center_text(d, W // 2, 36, "传统脚本 vs AI辅助方案 对比(100次/方案)", font(26), (0, 0, 0))
    _panel(d, 30, 80, 400, 400, "签到成功率 (%)", 1.0, 99.0, 0, 100)
    _panel(d, 470, 80, 400, 400, "人工干预次数", 98, 1, 0, 110)
    img.save(OUT / "comparison.png")
    print("生成 comparison.png")


if __name__ == "__main__":
    gen_architecture()
    gen_pipeline()
    gen_comparison()
