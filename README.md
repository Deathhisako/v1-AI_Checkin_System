# AI辅助自动化生活类签到系统

> AI-Assisted Automated Life Check-in System
> 开题报告配套系统原型 · 商汤日日新 `SensenNova-v6.8-Flash-Lite`
> 汇报人：刘佳灿　指导教师：王博文　日期：2026-10-27

<div align="center">

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![CI](https://github.com/Deathhisako/v1-AI_Checkin_System/actions/workflows/ci.yml/badge.svg)
![Checkin](https://github.com/Deathhisako/v1-AI_Checkin_System/actions/workflows/checkin.yml/badge.svg)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
![Version](https://img.shields.io/badge/version-0.6.8-orange)

**大模型 · OCR · 计算机视觉 驱动的智能签到**

</div>

---

## 一、项目定位

**核心结论**：AI 的价值不在"让脚本跑起来"，而在**让脚本在真实环境中不那么容易崩**，
处理硬编码逻辑应付不了的情况。

| 传统脚本（硬编码） | AI 辅助方案 |
|---|---|
| 固定模板OCR，一变即失效 | 语义理解 + 视觉识别，泛化强 |
| Cookie 失效即崩 | 检测 + 自愈 + 自动适配 |
| 加密升级即报废 | 识别变化-重析-生成新逻辑-验证 |
| 一崩就停，无监控 | 监控-诊断-自愈 闭环 |

## 二、架构（四层）

```
┌─────────────────────────────────────────────────┐
│ 应用层  Runner / Scheduler / Notifier            │
│         用户配置 · 任务编排 · 结果通知            │
├─────────────────────────────────────────────────┤
│ 决策层  Diagnostician / LLM(语义理解) / Parser   │
│         LLM语义理解 · 页面解析 · 异常诊断与处置决策 │
├─────────────────────────────────────────────────┤
│ 感知层  OCR / Vision / CaptchaSolver             │
│         OCR(PaddleOCR) · 视觉大模型 · 验证码识别   │
├─────────────────────────────────────────────────┤
│ 执行层  Requester / Browser / Cookie / Crypto    │
│         请求构造 · 浏览器自动化 · Cookie管理 · 加密 │
└─────────────────────────────────────────────────┘
```

对应开题报告技术路线：需求分析 → 场景建模 → 数据采集 → 接口梳理 →
**AI感知层** → **决策层** → **执行层** → 评估优化。

## 三、四大核心能力（对应四大痛点）

| 痛点 | 传统做法 | AI 方案 | 代码位置 |
|---|---|---|---|
| (1) 验证码与风控对抗 | 固定模板OCR/坐标 | 视觉大模型语义匹配 + 拟人轨迹 | `perception/providers.py` |
| (2) Cookie 失效自适应 | 定时刷新，失效即崩 | 状态码+页面语义监测，自动重登 | `execution/cookie_manager.py` |
| (3) 动态加密对抗 | 静态逆向写死 | LLM辅助逆向，检测失败自动重建 | `execution/crypto_adapter.py` |
| (4) 长期稳定运行 | 单点无异常处理 | 监控-诊断-决策-自愈闭环 | `core/self_heal.py` |

## 四、快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 1) 单轮签到(演示模式, 无需账号/API Key)
python main.py

# 2) 连续 N 轮, 观察自愈闭环
python main.py --demo 20

# 3) 对比实验: AI方案 vs 传统硬编码脚本
python main.py --compare 100
```

**输出**：
- 控制台实时日志（诊断/动作/结果）
- `logs/aicheckin.log` 运行日志
- `experiments/results.json` + `experiments/results.md` 实验数据

## 五、演示效果（示例）

```
演示完成: 共40次签到, 成功39次, 成功率97.5%
  诊断: kind=captcha_required     action=solve_captcha   检测到验证码
  诊断: kind=cookie_expired       action=relogin         登录态失效
  诊断: kind=dynamic_encryption   action=re_analyze      参数加密规则变化
  诊断: kind=transient            action=retry           瞬时网络抖动
```

对比实验（100 次/方案，相同干扰场景）：

| 指标 | 传统脚本(硬编码) | AI辅助方案 |
|---|---|---|
| 签到成功率 | 1.0% | **99.0%** |
| 人工干预次数 | 98 | **1** |
| 平均尝试次数/签到 | - | 2.13 |
| 自愈触发事件数 | - | 216 |

## 六、接入真实平台

实现 `aicheckin/core/platform.py` 中的 `CheckinPlatform` 接口，并注册：

```python
# my_platform.py
from aicheckin.registry import register
from aicheckin.models import Platform as Config
from aicheckin.execution import CookieManager, CryptoAdapter

@register("my_forum")   # 对应配置 platforms[].type 或 .key
class MyForumPlatform:
    def __init__(self, config: Config, runner=None):
        self.config = config
        self.cookie_mgr = CookieManager(config, login_fn=self.relogin,
                                        validate_fn=self.validate_login)
        self.crypto = CryptoAdapter(algorithm="md5", seed="my-secret")
        self.crypto.set_builder(self._build_sign)
        self.crypto.set_reanalyzer(self._reanalyze)

    def validate_login(self, cookie): ...      # 校验Cookie
    def relogin(self): ...                     # 重新登录/扫码
    def do_checkin(self, cookie, sign_fn=None): ...  # 执行签到 -> (status, body)
    def solve_captcha(self, captcha, sign_fn=None): ...
```

配置 `config/config.yaml` 添加平台项，`type` 设为注册键即可。

> 真实 LLM/OCR/视觉接入：设置 `ai.llm_provider / ocr_provider / vision_provider`，
> 并在 `decision/llm.py`、`perception/providers.py` 的 `build_*` 工厂中注入你的实现。

## 七、目录结构

```
AI_Checkin_System/
├── main.py                      # 入口(单轮/演示/对比/GitHub)
├── pyproject.toml               # 打包配置(pip install)
├── requirements.txt             # 运行依赖
├── requirements-dev.txt         # 开发依赖
├── Makefile                     # 常用命令
├── .github/workflows/           # CI + 定时签到 + 实验 工作流
├── config/
│   ├── config.yaml              # 应用+平台配置(演示)
│   ├── platforms.example.json   # GitHub Secrets 平台示例
│   └── README.md                # 配置/Secrets 说明
├── aicheckin/
│   ├── models/                  # 领域模型(枚举/实体)
│   ├── app/                     # 应用层: Runner/Scheduler/Notifier/Gha
│   ├── decision/                # 决策层: LLM/Parser/Diagnostician
│   ├── perception/              # 感知层: OCR/Vision/Captcha
│   ├── execution/               # 执行层: Cookie/Crypto/Browser
│   ├── core/                    # 核心: 平台接口 + 自愈引擎
│   ├── platforms/               # 真实平台适配器(含模板)
│   └── demo/                    # 演示平台(模拟四大痛点)
├── experiments/                 # 对比实验 + 结果
├── tests/                       # 单元测试
└── docs/                        # 文档(架构/论文大纲)
```

## 八、评估指标体系（对应 PPT）

签到成功率 · 连续稳定运行时长 · 人工干预次数 · 验证码/风控识别准确率 · 响应与耗时

## 九、预期成果（对应 PPT）

- ✅ 系统原型：本仓库
- ✅ 核心方法：语义理解型验证码识别 + 异常自愈策略（`self_heal.py`）
- ✅ 实验数据：`experiments/results.json`（多平台长期运行对比）
- 📄 论文：见 `docs/论文大纲.md`
- 🔓 开源代码：本仓库（MIT 协议）

## 十、GitHub 部署（无人值守定时签到）

本仓库内置 GitHub Actions 工作流，上传即可**无人值守定时签到**：

| 工作流 | 触发 | 用途 |
|---|---|---|
| `.github/workflows/ci.yml` | push/PR | 单元测试 + 演示 + 实验（多 Python 版本） |
| `.github/workflows/checkin.yml` | cron 每日 + 手动 | 定时自动签到 + 日志归档 |
| `.github/workflows/experiment.yml` | 手动 | 重新生成对比实验数据 |

### 部署步骤

1. **上传仓库**：把本目录推到 GitHub。
2. **配置 Secrets**（Settings → Secrets and variables → Actions）：
   - `PLATFORMS_CONFIG`：填入 `config/platforms.example.json` 的完整 JSON（真实平台凭据）。
   - 或逐平台变量：`PLATFORM_<KEY>_TYPE/_USERNAME/_PASSWORD/_EXTRA`。
3. **查看结果**：Actions 运行页 → `Daily Check-in` → 下载 `checkin-logs` artifact，
   摘要显示在 job 的 Summary 中。
4. **调整时间**：修改 `checkin.yml` 中 `cron`（默认北京 09:30）。

> ⚠️ **安全**：真实凭据只放 Secrets，**严禁**提交到仓库；日志上传前请脱敏（见 `SECURITY.md`）。

### 徽章

徽章地址已指向本仓库（v1-AI_Checkin_System），CI/签到状态徽章即可显示。

## 十一、综合报告与演示视频

- **演示视频**：`demo/演示视频-生活化签到系统.mp4`（约27秒，可视化演示系统应用于"示例生活论坛"软件，依次应对验证码拦截、Cookie过期、加密升级、瞬时故障，全部自愈成功，成功率100%）
- **效果截图**：`demo/效果图1-验证码自愈.png`、`demo/效果图2-Cookie自愈.png`
- **可视化演示程序**：`scripts/demo_gui.py`（`python scripts/demo_gui.py` 交互演示；`python scripts/demo_gui.py --record out.mp4` 录制演示视频）
- **人工智能综合报告**：见 `docs/` 或提交文档（含封面、项目背景、小组分工、功能说明、效果展示、个人体会、参考文献与致谢）
- **提交链接**：本仓库（GitHub）即为可提交的项目链接；演示视频亦可单独上传作为演示视频链接。
