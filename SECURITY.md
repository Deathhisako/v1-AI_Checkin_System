# 安全说明

## 重要：请勿在仓库中提交真实凭据

本系统处理真实登录凭据（账号、密码、Cookie）。**请务必遵守**：

1. 真实凭据只通过 **GitHub Secrets** 或本地 gitignore 的配置文件注入，
   **严禁** 提交到版本库。
2. `.gitignore` 已忽略 `config/local.yaml`、`config/credentials.yaml`。
3. `PLATFORMS_CONFIG` 等 Secrets 请设为 **仅限 Actions**，并定期轮换。
4. 日志（`logs/`）可能包含敏感信息，上传 artifact 前请脱敏。

## 使用合规
- 仅用于**个人**自动化签到，遵守目标平台的用户协议与法律法规。
- 避免对目标平台造成高频、恶意请求。

## 报告漏洞
如发现安全漏洞，请通过 PRIVATE 渠道联系维护者（见 README），
请勿在公开 issue 中披露敏感信息。
