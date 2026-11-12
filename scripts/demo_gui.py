"""AI辅助自动化生活类签到系统 - 可视化演示 (GUI).

把系统应用到"示例生活论坛"软件上, 以图形界面呈现:
  左: 目标软件(示例生活论坛)的签到界面, 实时反映登录态/验证码/签到结果;
  右: AI 智能体控制台, 实时滚动 感知->诊断->决策->自愈 闭环日志;
  底: 关键指标(签到成功率 / 自愈触发次数 / 人工干预次数)。

用法:
    python scripts/demo_gui.py              # 交互演示(不录制)
    python scripts/demo_gui.py --record out.mp4   # 演示并录制屏幕为视频
"""
from __future__ import annotations

import argparse
import logging
import os
import queue
import sys
import tempfile
import threading
import time
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aicheckin.core import SelfHealEngine
from aicheckin.decision import Diagnostician
from aicheckin.models import Platform as PlatformConfig
from aicheckin.models import PlatformType

# ---------------- 场景脚本 ----------------
# 每个场景 = 一次完整签到(内部可能含多次尝试, 由自愈引擎处理)
# script 为 do_checkin 依次返回的 (status, body) 列表
ROUNDS = [
    {
        "title": "场景一 · 正常签到（基线）",
        "desc": "登录态正常, 直接签到成功",
        "script": [(200, "签到成功：今日积分已到账")],
        "captcha": None,
    },
    {
        "title": "场景二 · 滑块/语义验证码拦截",
        "desc": "AI 语义理解 + 视觉识别 自动通过",
        "script": [(200, "需要滑块验证码，请完成验证"), (200, "签到成功：今日积分已到账")],
        "captcha": "slider",
    },
    {
        "title": "场景三 · Cookie 过期",
        "desc": "AI 状态监测 -> 自动重登刷新 Cookie",
        "script": [(401, "未登录：会话已过期，请重新登录"), (200, "签到成功：今日积分已到账")],
        "captcha": None,
    },
    {
        "title": "场景四 · 动态加密升级",
        "desc": "AI 检测签名失败 -> 重新分析并生成新逻辑",
        "script": [(400, "参数校验失败：签名不正确（期望新算法）"), (200, "签到成功：今日积分已到账")],
        "captcha": None,
    },
    {
        "title": "场景五 · 瞬时故障 / 风控",
        "desc": "AI 语义分类 -> 退避重试",
        "script": [(502, "网关超时：上游服务暂时不可用"), (200, "签到成功：今日积分已到账")],
        "captcha": None,
    },
]


# ---------------- 脚本化平台 ----------------
class ScriptedPlatform:
    """一个"示例生活论坛"签到平台, 按脚本依次抛出真实环境干扰。

    复用系统的真实决策层(Diagnostician/MockLLM)与自愈引擎(SelfHealEngine),
    仅把"平台返回什么"脚本化, 从而在演示中确定性地复现四大痛点。
    """

    def __init__(self, key: str = "life_forum", on_response=None) -> None:
        self.config = PlatformConfig(key=key, name="示例生活论坛",
                                     type=PlatformType.FORUM, username="demo_user")
        self._script: list = []
        self._idx = 0
        self._on_response = on_response or (lambda *a, **k: None)
        # 登录态(供界面显示)
        self.logged_in = True
        self.cookie_valid = True
        self.captcha_shown = False
        self.last_status = 0
        self.last_body = ""
        self.sign_count = 0

    # ---- CheckinPlatform 接口 ----
    def validate_login(self, cookie) -> bool:
        return self.logged_in and self.cookie_valid

    def relogin(self):
        self.logged_in = True
        self.cookie_valid = True
        self._on_response("relogin", 200, "重新登录成功：已获取新 Cookie")
        return {"session": "new-session", "uid": "u1001"}

    def do_checkin(self, cookie, sign_fn=None):
        if self._idx >= len(self._script):
            self._idx = 0
        status, body = self._script[self._idx]
        self._idx += 1
        self.last_status = status
        self.last_body = body
        self._on_response("checkin", status, body)
        if "验证码" in body:
            self.captcha_shown = True
        else:
            self.captcha_shown = False
        if "未登录" in body or status in (401, 403):
            self.logged_in = False
            self.cookie_valid = False
        else:
            self.logged_in = True
        if "签到成功" in body:
            self.sign_count += 1
        return status, body

    def solve_captcha(self, captcha, sign_fn=None):
        return {"ok": True, "answer": "demo-captcha-ok"}

    def analyze_page(self, body: str):
        return {"text": body[:200]}

    def build_sign_fn(self):
        return lambda params: "mock-sign"

    def reanalyze(self):
        return True

    def set_round(self, script, captcha):
        self._script = list(script)
        self._idx = 0
        self.captcha_shown = False
        self.logged_in = True
        self.cookie_valid = True
        self._captcha_kind = captcha


# ---------------- 日志 -> GUI 桥 ----------------
class QueueLogHandler(logging.Handler):
    """把系统运行日志实时转发到 GUI 队列(控制台面板)。"""

    def __init__(self, q: "queue.Queue") -> None:
        super().__init__()
        self.q = q

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.q.put(("log", record.levelno, self.format(record)))
        except Exception:
            pass


# ---------------- 场景执行线程 ----------------
class ScenarioRunner(threading.Thread):
    """按脚本依次执行 5 个场景, 每个场景由真实自愈引擎处理。"""

    def __init__(self, q: "queue.Queue") -> None:
        super().__init__(daemon=True)
        self.q = q
        self.platform = ScriptedPlatform(on_response=lambda *a: self.q.put(("app",) + a))
        self.diagnoser = Diagnostician()
        self.engine = SelfHealEngine(
            diagnoser=self.diagnoser, max_attempts=5, retry_delay=1.2,
            max_backoff=4.0, allow_relogin=True, allow_reanalyze=True,
            allow_browser_fallback=True, alert_on_failure=True,
        )
        self.stop_flag = threading.Event()

    def log(self, level, msg):
        self.q.put(("log", level, msg))

    def run(self) -> None:
        total = 0
        ok = 0
        heals = 0
        self.q.put(("intro",))
        time.sleep(3.2)
        for i, rnd in enumerate(ROUNDS, start=1):
            if self.stop_flag.is_set():
                break
            self.q.put(("round_start", i, len(ROUNDS), rnd["title"], rnd["desc"]))
            time.sleep(2.2)
            # 感知
            self.q.put(("phase", "感知"))
            self.log(logging.INFO, f"[感知] 读取平台配置, 构造签到请求 ...")
            time.sleep(1.4)
            self.platform.set_round(rnd["script"], rnd["captcha"])
            # 执行签到(自愈引擎驱动)
            ctx = {"sign_fn": self.platform.build_sign_fn(),
                   "reanalyze_fn": self.platform.reanalyze}
            result = self.engine.run(self.platform, ctx)
            total += 1
            if result.ok:
                ok += 1
            heals += len(result.heal_events)
            for ev in result.heal_events:
                self.log(logging.WARNING, f"[自愈] {ev}")
            self.log(logging.INFO,
                     f"[结果] 第{i}个场景: {'成功' if result.ok else '失败'} "
                     f"(尝试 {result.attempts} 次, 自愈事件 {len(result.heal_events)} 个)")
            self.q.put(("round_done", i, result.ok, result.attempts, len(result.heal_events)))
            self.q.put(("metrics", ok, total, heals))
            time.sleep(2.0)
        self.q.put(("outro", ok, total, heals))
        time.sleep(3.5)
        self.q.put(("finished", ok, total, heals))


# ---------------- GUI ----------------
F = "Microsoft YaHei"

BG = "#0f1420"
PANEL = "#171e2e"
PANEL2 = "#1e2740"
ACCENT = "#38bdf8"
GREEN = "#34d399"
RED = "#f87171"
YELLOW = "#fbbf24"
PURPLE = "#a78bfa"
GRAY = "#94a3b8"
TXT = "#e2e8f0"


class App:
    def __init__(self, root, q: "queue.Queue", out: str | None):
        self.root = root
        self.q = q
        self.out = out
        self.root.title("AI 辅助自动化生活类签到系统 · 演示")
        self.root.configure(bg=BG)
        self.root.geometry("1440x780+10+5")
        # 置顶, 避免被其它窗口遮挡(录制时需要)
        self.root.attributes("-topmost", True)
        self.root.lift()
        self.root.after(300, self.root.lift)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        self._build()
        self.round = 0
        self.ok = 0
        self.total = 0
        self.heals = 0
        self.frames_dir = None
        self.frame_no = 0
        self.fps = 8
        self.recording = bool(out)
        self._start_recording()
        self.root.after(100, self._poll)

    # ---------- UI ----------
    def _build(self):
        root = self.root
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=0)
        root.rowconfigure(1, weight=0)
        root.rowconfigure(2, weight=1)
        root.rowconfigure(3, weight=0)

        # 顶栏
        top = tk.Frame(root, bg=BG)
        top.grid(row=0, column=0, sticky="ew", padx=18, pady=(12, 4))
        tk.Label(top, text="AI 辅助自动化生活类签到系统", font=(F, 22, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Label(top, text="大模型 · OCR · 计算机视觉 驱动的智能签到",
                 font=(F, 12), fg=GRAY, bg=BG).pack(side="left", padx=16, pady=(6, 0))
        self.round_lbl = tk.Label(top, text="待开始", font=(F, 13, "bold"),
                                  fg=GREEN, bg=BG)
        self.round_lbl.pack(side="right")

        # 横幅(场景说明)
        self.banner = tk.Label(root, text="AI 智能体将依次演示：正常签到 · 验证码 · Cookie过期 · 加密升级 · 瞬时故障",
                               font=(F, 12, "bold"), fg="#0b1020", bg=ACCENT)
        self.banner.grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 6))

        body = tk.Frame(root, bg=BG)
        body.grid(row=2, column=0, sticky="nsew", padx=18, pady=(4, 8))
        self._body = body
        body.columnconfigure(0, weight=1, uniform="col")
        body.columnconfigure(1, weight=1, uniform="col")
        body.rowconfigure(0, weight=1)

        # 左: 目标软件
        left = tk.Frame(body, bg=PANEL, highlightbackground="#2b3650",
                        highlightthickness=1)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._build_app(left)

        # 右: AI 控制台
        right = tk.Frame(body, bg=PANEL, highlightbackground="#2b3650",
                         highlightthickness=1)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self._build_console(right)

        # 底: 指标
        bottom = tk.Frame(root, bg=BG)
        bottom.grid(row=3, column=0, sticky="ew", padx=18, pady=(4, 14))
        self._bottom = bottom
        self._build_metrics(bottom)

    def _build_app(self, parent):
        tk.Label(parent, text="目标软件：示例生活论坛", font=(F, 15, "bold"),
                 fg=TXT, bg=PANEL).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(parent, text="（真实论坛/PT站/校园打卡平台的可交互模拟）",
                 font=(F, 10), fg=GRAY, bg=PANEL).pack(anchor="w", padx=18)

        card = tk.Frame(parent, bg=PANEL2, highlightbackground="#2b3650",
                        highlightthickness=1)
        card.pack(fill="both", expand=True, padx=18, pady=12)

        # 论坛头部
        head = tk.Frame(card, bg=PANEL2)
        head.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(head, text="示例生活论坛", font=(F, 17, "bold"), fg=ACCENT,
                 bg=PANEL2).pack(side="left")
        tk.Label(head, text="每日签到 · 连续打卡领积分", font=(F, 11),
                 fg=GRAY, bg=PANEL2).pack(side="left", padx=12, pady=(8, 0))

        # 登录状态
        lrow = tk.Frame(card, bg=PANEL2)
        lrow.pack(fill="x", padx=16, pady=(10, 2))
        tk.Label(lrow, text="登录状态", font=(F, 11), fg=GRAY,
                 bg=PANEL2).pack(side="left")
        self.login_dot = tk.Canvas(lrow, width=16, height=16, bg=PANEL2,
                                   highlightthickness=0)
        self.login_dot.pack(side="left", padx=6)
        self.login_dot.create_oval(3, 3, 13, 13, fill=GREEN, outline="")
        self.login_lbl = tk.Label(lrow, text="已登录", font=(F, 12, "bold"),
                                  fg=GREEN, bg=PANEL2)
        self.login_lbl.pack(side="left")

        # 签到卡片
        self.check_card = tk.Frame(card, bg="#22304a", highlightbackground="#33456a",
                                   highlightthickness=1)
        self.check_card.pack(fill="x", padx=16, pady=12)
        tk.Label(self.check_card, text="今日签到", font=(F, 14, "bold"),
                 fg=TXT, bg="#22304a").pack(pady=(14, 2))
        self.check_btn = tk.Label(self.check_card, text="● 点击签到", font=(F, 15, "bold"),
                                  fg=GREEN, bg="#22304a")
        self.check_btn.pack(pady=(0, 4))
        self.check_sub = tk.Label(self.check_card, text="状态：待签到", font=(F, 11),
                                  fg=GRAY, bg="#22304a")
        self.check_sub.pack(pady=(0, 14))

        # 验证码区(Canvas)
        self.cap_frame = tk.Frame(card, bg="#26222f", highlightbackground="#4a3a5a",
                                  highlightthickness=1)
        self.cap_frame.pack(fill="x", padx=16, pady=(4, 8))
        tk.Label(self.cap_frame, text="安全验证", font=(F, 12, "bold"), fg=YELLOW,
                 bg="#26222f").pack(anchor="w", padx=12, pady=(8, 0))
        self.cap_lbl = tk.Label(self.cap_frame, text="请拖动滑块完成拼图", font=(F, 11),
                                fg=TXT, bg="#26222f")
        self.cap_lbl.pack(anchor="w", padx=12, pady=(2, 4))
        self.cap_canvas = tk.Canvas(self.cap_frame, height=56, bg="#2c2733",
                                    highlightthickness=0)
        self.cap_canvas.pack(fill="x", padx=12, pady=(0, 8))
        self._draw_slider(0)
        self.cap_frame.pack_forget()

        # 操作日志
        tk.Label(card, text="签到记录", font=(F, 12, "bold"), fg=TXT,
                 bg=PANEL2).pack(anchor="w", padx=16, pady=(8, 2))
        self.rec_box = tk.Text(card, height=4, width=40, bg=PANEL2, fg=GRAY, font=(F, 10),
                               relief="flat", state="disabled", wrap="word",
                               highlightthickness=0)
        self.rec_box.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    def _build_console(self, parent):
        tk.Label(parent, text="AI 智能体控制台", font=(F, 15, "bold"), fg=TXT,
                 bg=PANEL).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Label(parent, text="感知 -> 诊断 -> 决策 -> 自愈 闭环（实时）",
                 font=(F, 10), fg=GRAY, bg=PANEL).pack(anchor="w", padx=18)

        # 自愈闭环芯片
        loop = tk.Frame(parent, bg=PANEL)
        loop.pack(fill="x", padx=18, pady=12)
        self.chips = {}
        for name, color in [("监控", ACCENT), ("诊断", YELLOW), ("决策", PURPLE), ("自愈", GREEN)]:
            chip = tk.Label(loop, text=name, font=(F, 12, "bold"), fg=GRAY,
                            bg=PANEL2, padx=14, pady=8)
            chip.pack(side="left", padx=(0, 8))
            self.chips[name] = (chip, color)
            if name != "监控":
                tk.Label(loop, text="→", font=(F, 13, "bold"), fg=GRAY,
                         bg=PANEL).pack(side="left", padx=(0, 4))

        self.console = tk.Text(parent, bg="#0b101c", fg=TXT, font=("Consolas", 10),
                               relief="flat", state="disabled", wrap="word", width=42, height=12,
                               highlightthickness=0, padx=14, pady=10)
        self.console.pack(fill="both", expand=True, padx=18, pady=(4, 14))

    def _build_metrics(self, parent):
        items = [
            ("签到成功率", "0%", GREEN),
            ("成功/总", "0 / 0", ACCENT),
            ("自愈触发", "0 次", PURPLE),
            ("人工干预", "0 次", GRAY),
        ]
        self.metric_lbls = {}
        for name, val, color in items:
            box = tk.Frame(parent, bg=PANEL, highlightbackground="#2b3650",
                           highlightthickness=1)
            box.pack(side="left", fill="x", expand=True, padx=(0, 10))
            tk.Label(box, text=name, font=(F, 11), fg=GRAY, bg=PANEL).pack(
                pady=(10, 0))
            lbl = tk.Label(box, text=val, font=(F, 22, "bold"), fg=color, bg=PANEL)
            lbl.pack(pady=(0, 10))
            self.metric_lbls[name] = lbl

    # ---------- 事件处理 ----------
    def _poll(self):
        try:
            while True:
                ev = self.q.get_nowait()
                self._handle(ev)
        except queue.Empty:
            pass
        self.root.after(50, self._poll)

    def _handle(self, ev):
        kind = ev[0]
        if kind == "intro":
            self.banner.config(text="欢迎观看演示 · AI 智能体将依次应对：验证码拦截 · Cookie过期 · 加密升级 · 瞬时故障",
                               bg=ACCENT, fg="#0b1020")
            self.round_lbl.config(text="准备开始", fg=ACCENT)
            self._log("=" * 58, "#64748b")
            self._log("AI 辅助自动化生活类签到系统 · 可视化演示", ACCENT)
            self._log("目标：让签到系统在真实环境干扰下 不崩溃 · 可自愈 · 持续运行", GRAY)
        elif kind == "outro":
            _, ok, total, heals = ev
            rate = f"{ok/total*100:.0f}%" if total else "0%"
            self.banner.config(text=f"演示结束 · 共 {total} 个场景，成功 {ok} 个，成功率 {rate}，自愈 {heals} 次，人工干预 0 次",
                               bg=GREEN, fg="#0b1020")
            self.round_lbl.config(text="全部完成", fg=GREEN)
            self._log("=" * 58, "#64748b")
            self._log(f"✔ 演示完成：成功率 {rate} · 自愈触发 {heals} 次 · 人工干预 0 次", GREEN)
        elif kind == "round_start":
            _, i, n, title, desc = ev
            self.round = i
            self.round_lbl.config(text=f"第 {i}/{n} 轮 · 运行中", fg=YELLOW)
            self.banner.config(text=f"{title} — {desc}", bg="#22304a", fg=TXT)
            self._log("=" * 58, "#64748b")
            self._log(f"▶ {title}", ACCENT)
            self._log(f"   {desc}", GRAY)
            self._set_check("准备签到", "待执行")
        elif kind == "phase":
            self._flash("监控")
            self._set_check("AI 正在执行", "处理中")
        elif kind == "app":
            _, tag, status, body = ev
            self._on_app(tag, status, body)
        elif kind == "log":
            _, lvl, msg = ev
            color = {logging.ERROR: RED, logging.WARNING: YELLOW,
                     logging.INFO: TXT}.get(lvl, TXT)
            self._log(msg, color)
            if "诊断:" in msg:
                self._flash("诊断"); self._flash("决策")
                self._highlight_diag(msg)
            if "动作:" in msg or "[自愈]" in msg:
                self._flash("自愈")
        elif kind == "round_done":
            _, i, ok, attempts, heals = ev
            self._set_check("签到成功 ✓" if ok else "签到失败 ✗",
                            "已完成" if ok else "失败", ok)
            self._log(f"   → 第 {i} 个场景完成：{'成功' if ok else '失败'}"
                      f"（尝试 {attempts} 次）", GREEN if ok else RED)
            self._flash("自愈")
            self._reset_chips()
            # 签到记录
            self.rec_box.config(state="normal")
            self.rec_box.insert("end", f"场景{i}：{'✓ 成功' if ok else '✗ 失败'}（尝试{attempts}次）\n")
            self.rec_box.see("end")
            self.rec_box.config(state="disabled")
        elif kind == "metrics":
            _, ok, total, heals = ev
            self.ok, self.total, self.heals = ok, total, heals
            rate = f"{ok/total*100:.0f}%" if total else "0%"
            self.metric_lbls["签到成功率"].config(text=rate, fg=GREEN if rate != "0%" else GRAY)
            self.metric_lbls["成功/总"].config(text=f"{ok} / {total}")
            self.metric_lbls["自愈触发"].config(text=f"{heals} 次")
        elif kind == "finished":
            _, ok, total, heals = ev
            print("DBG body h=%d bottom y=%d h=%d win=%d" % (
                self._body.winfo_height(), self._bottom.winfo_y(),
                self._bottom.winfo_height(), self.root.winfo_height()))
            for i, c in enumerate(self._body.winfo_children()):
                print("DBG  panel%d y=%d h=%d" % (i, c.winfo_y(), c.winfo_height()))
            rate = f"{ok/total*100:.0f}%" if total else "0%"
            self.round_lbl.config(text=f"全部完成 · 成功率 {rate}", fg=GREEN)
            self._log("=" * 58, "#64748b")
            self._log(f"✔ 演示结束：共 {total} 个场景，成功 {ok} 个，"
                      f"成功率 {rate}，自愈触发 {heals} 次，人工干预 0 次", GREEN)
            self._stop_recording()
            if self.out:
                self.root.after(400, self._close)

    def _on_app(self, tag, status, body):
        if tag == "relogin":
            self._set_login(True)
            self._set_check("登录态已恢复", "重新登录")
            self._log(f"[执行] {body}", GREEN)
            return
        # checkin 响应
        if "验证码" in body:
            self._set_login(True)
            self._show_captcha(body)
            self._set_check("验证码拦截", "等待 AI 识别")
            self._log(f"[感知] 平台返回：{body}", YELLOW)
        elif "未登录" in body or status in (401, 403):
            self._set_login(False)
            self._set_check("登录失效", "Cookie 过期")
            self._log(f"[感知] 平台返回：{body}", YELLOW)
        elif "签名" in body or status == 400:
            self._set_check("加密升级", "签名校验失败")
            self._log(f"[感知] 平台返回：{body}", YELLOW)
        elif "超时" in body or status >= 500:
            self._set_check("瞬时故障", "网关超时")
            self._log(f"[感知] 平台返回：{body}", YELLOW)
        elif "签到成功" in body:
            self._set_check("签到成功 ✓", "今日积分已到账", True)
            self._hide_captcha()
            self._log(f"[执行] {body}", GREEN)
        else:
            self._log(f"[感知] 平台返回({status})：{body}", TXT)

    # ---------- UI 小助手 ----------
    def _log(self, msg, color):
        self.console.config(state="normal")
        self.console.insert("end", msg + "\n", ("c",))
        self.console.tag_config("c", foreground=color)
        self.console.see("end")
        self.console.config(state="disabled")

    def _flash(self, name):
        chip, color = self.chips[name]
        chip.config(fg=color)
        self.root.after(900, lambda n=name: (
            self.chips[n][0].config(fg=GRAY)))

    def _reset_chips(self):
        for name, (chip, color) in self.chips.items():
            chip.config(fg=GRAY)

    def _highlight_diag(self, msg):
        # 根据诊断信息高亮对应场景标签
        if "cookie" in msg or "登录" in msg:
            self._set_check("诊断：Cookie 过期 → 自动重登", "自愈中")
        elif "captcha" in msg:
            self._set_check("诊断：验证码拦截 → 语义识别", "自愈中")
        elif "encryption" in msg:
            self._set_check("诊断：加密升级 → 重新分析", "自愈中")
        elif "transient" in msg:
            self._set_check("诊断：瞬时故障 → 重试", "自愈中")

    def _set_login(self, ok):
        self.login_lbl.config(text="已登录" if ok else "未登录",
                              fg=GREEN if ok else RED)
        self.login_dot.delete("all")
        self.login_dot.create_oval(3, 3, 13, 13,
                                   fill=GREEN if ok else RED, outline="")

    def _set_check(self, txt, sub, ok=None):
        self.check_btn.config(text=f"● {txt}" if not txt.startswith("●") else txt,
                              fg=(GREEN if ok else YELLOW))
        self.check_sub.config(text=sub)

    def _draw_slider(self, x):
        c = self.cap_canvas
        c.delete("all")
        c.create_rectangle(10, 18, 420, 38, fill="#3a3342", outline="#5a4a6a")
        c.create_rectangle(12 + x, 14, 64 + x, 42, fill=ACCENT, outline="")
        c.create_text(38 + x, 28, text="◀", fill="#fff")

    def _show_captcha(self, body):
        self.cap_frame.pack(fill="x", padx=16, pady=(4, 8))
        self.cap_lbl.config(text="AI 正在语义识别滑块验证码 ...", fg=YELLOW)
        # 滑块动画
        self._slider_anim = 0
        self._anim()

    def _anim(self):
        self._slider_anim += 26
        if self._slider_anim <= 400:
            self._draw_slider(self._slider_anim)
            self.root.after(50, self._anim)
        else:
            self._draw_slider(400)
            self.cap_lbl.config(text="✓ 识别成功，已提交验证", fg=GREEN)

    def _hide_captcha(self):
        self.cap_frame.pack_forget()

    # ---------- 录制 ----------
    def _start_recording(self):
        if not self.recording:
            return
        self.frames_dir = tempfile.mkdtemp(prefix="aicheckin_frames_")
        self.frame_no = 0
        self._tick()

    def _tick(self):
        if not self.recording or self.frames_dir is None:
            return
        try:
            from PIL import ImageGrab
            x = self.root.winfo_rootx(); y = self.root.winfo_rooty()
            w = self.root.winfo_width(); h = self.root.winfo_height()
            if w > 50 and h > 50:
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                # 裁剪为偶数尺寸, 保证 yuv420p 编码
                w2, h2 = w - (w % 2), h - (h % 2)
                img = img.convert("RGB").crop((0, 0, w2, h2))
                img.save(
                    os.path.join(self.frames_dir, f"f{self.frame_no:05d}.jpg"),
                    quality=90)
                self.frame_no += 1
        except Exception as e:
            print("capture err", e)
        self.root.after(int(1000 / self.fps), self._tick)

    def _stop_recording(self):
        self.recording = False

    def _close(self):
        self._stop_recording()
        try:
            self.root.attributes("-topmost", False)
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def encode(self):
        if not self.out or not self.frames_dir:
            return
        try:
            import imageio_ffmpeg
            ff = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return
        out = self.out
        pattern = os.path.join(self.frames_dir, "f%05d.jpg")
        cmd = [ff, "-y", "-framerate", str(self.fps), "-i", pattern,
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "medium",
               "-crf", "20", "-movflags", "+faststart", out]
        import subprocess
        print("ENCODE:", " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        print("ffmpeg rc", r.returncode)
        if r.returncode != 0:
            print(r.stderr[-800:])
        else:
            print("OK ->", out)


def main():
    # 统一 DPI, 使 tkinter 与 PIL 屏幕捕获使用同一坐标系
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # 系统 DPI 感知
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", default=None, help="录制输出 mp4 路径")
    ap.add_argument("--no-record", action="store_true", help="不录制(交互演示)")
    args = ap.parse_args()
    out = args.record if (args.record and not args.no_record) else None

    q: "queue.Queue" = queue.Queue()
    logging.getLogger("aicheckin").setLevel(logging.INFO)
    h = QueueLogHandler(q)
    h.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("aicheckin").addHandler(h)
    logging.getLogger("aicheckin").propagate = False

    root = tk.Tk()
    app = App(root, q, out)
    runner = ScenarioRunner(q)
    root.after(600, runner.start)
    root.mainloop()
    app.encode()


if __name__ == "__main__":
    main()
