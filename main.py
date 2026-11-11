"""AI辅助自动化生活类签到系统 - 入口。

用法:
    python main.py                        # 读取 config/config.yaml 运行一轮
    python main.py --demo N               # 运行演示: 连续执行 N 轮, 验证自愈闭环
    python main.py --compare M            # 实验对比: AI方案 vs 传统脚本, M 轮
    python main.py --config path.yaml     # 指定配置文件
    python main.py --github               # GitHub Actions 模式(环境变量注入平台+写摘要)

GitHub Actions 模式说明(无人值守):
    - 平台凭据经 PLATFORMS_CONFIG 或 PLATFORM_* 环境变量注入(Secrets, 不落盘)
    - 结果写入 $GITHUB_STEP_SUMMARY, 日志由 upload-artifact 归档
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from aicheckin.app import GhaReporter, Runner, Scheduler
from aicheckin.config import AppConfig, load_platforms, load_platforms_from_env
from aicheckin.logger import build_logger
from aicheckin.demo import DemoPlatform  # noqa: F401  (注册 demo 适配器)

from experiments.compare import run_comparison, run_demo


def run_github(cfg: AppConfig, log) -> int:
    """GitHub Actions 无人值守模式。"""
    platforms = load_platforms_from_env()
    if not platforms:
        # 回退: 无注入时使用 demo 平台(安全默认), 便于验证工作流
        platforms = load_platforms("config/config.yaml")
        log.warning("未检测到环境变量注入的平台, 使用演示平台(仅用于验证)")
    runner = Runner(cfg, platforms, logger=log)
    results = runner.run_once()
    GhaReporter(logger=log).report(results)
    ok = sum(1 for r in results if r.ok)
    log.info("GitHub 模式完成: %d/%d 成功", ok, len(results))
    return 0 if ok == len(results) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="AI辅助自动化生活类签到系统")
    ap.add_argument("--config", default="config/config.yaml", help="配置文件路径")
    ap.add_argument("--demo", type=int, default=0, help="连续运行 N 轮演示")
    ap.add_argument("--compare", type=int, default=0, help="实验对比: AI方案 vs 传统脚本, 每轮次数")
    ap.add_argument("--github", action="store_true", help="GitHub Actions 模式")
    args = ap.parse_args()

    cfg = AppConfig.load(args.config)
    log, bus = build_logger("aicheckin", cfg.log_dir)
    log.info("=" * 60)
    log.info("AI辅助自动化生活类签到系统 启动 (v0.6.8)")
    log.info("=" * 60)

    if args.github:
        return run_github(cfg, log)
    if args.compare:
        return run_comparison(cfg, rounds=args.compare, log=log)

    platforms = load_platforms(args.config)
    runner = Runner(cfg, platforms, logger=log)

    if args.demo:
        return run_demo(cfg, runner, rounds=args.demo, log=log)

    scheduler = Scheduler(
        interval_seconds=cfg.scheduler["interval_seconds"],
        once=cfg.scheduler["once"],
        run_count=cfg.scheduler["run_count"],
    )
    scheduler.run(runner.run_once)
    log.info("全部任务执行完毕")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
