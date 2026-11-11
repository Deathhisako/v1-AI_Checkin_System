"""领域枚举: 任务状态、异常类型、处置决策、平台类型。"""
from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"          # 待执行
    RUNNING = "running"          # 执行中
    SUCCESS = "success"          # 成功
    FAILED = "failed"            # 失败（最终）
    RECOVERED = "recovered"      # 自愈后成功


class PlatformType(str, Enum):
    FORUM = "forum"              # 论坛
    APP = "app"                  # App
    PT = "pt"                    # PT站
    SCHOOL = "school"            # 校园/健康打卡
    CUSTOM = "custom"            # 自定义
    DEMO = "demo"                # 演示平台(模拟真实环境干扰)


class ErrorKind(str, Enum):
    """异常类型分类 —— 决策层 LLM 语义分类的结果。"""
    COOKIE_EXPIRED = "cookie_expired"        # Cookie过期：可自愈(重新登录)
    DYNAMIC_ENCRYPTION = "dynamic_encryption"  # 动态加密升级：可自愈(重新分析)
    CAPTCHA_REQUIRED = "captcha_required"    # 验证码拦截：可自愈(语义识别)
    RISK_CONTROL = "risk_control"            # 风控升级：需降级/等待
    TRANSIENT = "transient"                  # 瞬时网络/服务抖动：可重试
    NEED_HUMAN = "need_human"                # 需人工介入：报警
    UPGRADED = "upgraded"                    # 平台升级：需重新分析
    UNKNOWN = "unknown"


class HealAction(str, Enum):
    """自愈处置动作 —— 决策层输出的决策。"""
    RETRY = "retry"                  # 直接重试
    RELOGIN = "relogin"              # 重新登录(刷新Cookie)
    RE_ANALYZE = "re_analyze"        # 重新分析加密/页面逻辑
    SOLVE_CAPTCHA = "solve_captcha"  # 识别并提交验证码
    FALLBACK_BROWSER = "fallback_browser"  # 降级到浏览器自动化
    WAIT = "wait"                    # 退避等待
    ALERT = "alert"                  # 报警给人工
    NONE = "none"


class HealOutcome(str, Enum):
    """自愈结果。"""
    SUCCESS = "success"
    RETRYING = "retrying"
    EXHAUSTED = "exhausted"          # 重试耗尽
    NEED_HUMAN = "need_human"
