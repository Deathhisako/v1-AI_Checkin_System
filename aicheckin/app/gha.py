"""GitHub Actions 集成: 结果摘要 + 日志归档。

用于无人值守定时签到(GitHub Actions cron):
  - 从环境变量注入平台(Secrets, 不落盘)
  - 运行签到
  - 写 GITHUB_STEP_SUMMARY (Markdown 摘要)
  - 供 actions/upload-artifact 上传日志
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import List

from ..models import CheckinResult


class GhaReporter:
    """把结果写到 GitHub Actions 的 Step Summary 文件。"""

    def __init__(self, summary_file: str | None = None, logger: logging.Logger | None = None) -> None:
        self.summary_file = summary_file or os.environ.get("GITHUB_STEP_SUMMARY", "")
        self.log = logger or logging.getLogger("aicheckin.gha")

    def report(self, results: List[CheckinResult]) -> None:
        if not self.summary_file:
            self.log.info("未检测到 GITHUB_STEP_SUMMARY, 跳过摘要输出")
            return
        try:
            ok = sum(1 for r in results if r.ok)
            total = len(results)
            lines = [
                "## AI 签到结果",
                "",
                f"**平台数**: {total}　**成功**: {ok}　**成功率**: {100.0 * ok / max(1, total):.1f}%",
                "",
                "| 平台 | 结果 | 尝试 | 自愈事件 | 消息 |",
                "|---|---|---|---|---|",
            ]
            for r in results:
                status = "✅" if r.ok else "❌"
                heals = "; ".join(r.heal_events) or "-"
                lines.append(
                    f"| {r.platform_key} | {status} | {r.attempts} | {len(r.heal_events)} | "
                    f"{r.message.replace('|', '/')} |"
                )
            lines.append("")
            lines.append(f"<sub>生成时间: {_now_str()}</sub>")
            Path(self.summary_file).parent.mkdir(parents=True, exist_ok=True)
            with open(self.summary_file, "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            self.log.info("GitHub Step Summary 已写入: %s", self.summary_file)
        except Exception as exc:  # noqa: BLE001
            self.log.warning("写入 GitHub Summary 失败: %s", exc)


def _now_str() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
