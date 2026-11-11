# 配置说明

## 1. 本地运行
- `config.yaml`：应用配置 + 演示平台（安全，无凭据）。
- 复制为 `local.yaml` 填入真实平台（已 gitignore，不会提交）。

## 2. GitHub Actions 部署（无人值守）
在仓库 **Settings → Secrets and variables → Actions** 中添加密钥，二选一：

### 方式 A：`PLATFORMS_CONFIG`（推荐）
把 `platforms.example.json` 的内容整体填入该 Secret。
> 注意：真实密码/Cookie 也放这里，因此务必把该 Secret 设为仅限 Actions，
> 且不要在仓库任何明文文件中保存凭据。

### 方式 B：逐平台独立变量
```
PLATFORM_MYFORUM_KEY=my_forum
PLATFORM_MYFORUM_TYPE=forum
PLATFORM_MYFORUM_USERNAME=xxx
PLATFORM_MYFORUM_PASSWORD=yyy
PLATFORM_MYFORUM_EXTRA={"cookie_ttl":4,"encrypt_ttl":6,"captcha_rate":0.35}
```

## 3. 平台类型
| type | 说明 |
|---|---|
| `forum` | 论坛 |
| `app` | App |
| `pt` | PT站 |
| `school` | 校园/健康打卡 |
| `custom` | 自定义 |
| `demo` | 演示平台（模拟干扰，用于验证） |

## 4. 真实平台适配器
实现 `aicheckin/platforms/template.py` 的 `CheckinPlatform` 接口并用 `@register(类型)` 注册。
