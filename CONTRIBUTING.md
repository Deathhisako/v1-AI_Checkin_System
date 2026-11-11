# 贡献指南

感谢你参与 **AI辅助自动化生活类签到系统** 的开发！

## 开发环境

```bash
git clone <你的仓库地址>
cd AI_Checkin_System
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 常用命令

```bash
python -m unittest discover -s tests -v   # 运行测试
python main.py --demo 20                  # 自愈演示
python main.py --compare 100              # 对比实验
```

## 分支与提交

1. 从 `main` 拉取新分支：`git checkout -b feat/xxx`
2. 提交信息遵循 [Conventional Commits](https://www.conventionalcommits.org/)：
   - `feat:` 新功能
   - `fix:` 修复
   - `docs:` 文档
   - `test:` 测试
   - `refactor:` 重构
3. 提交前运行测试，确保通过。

## 新增真实平台

1. 复制 `aicheckin/platforms/template.py` 为 `aicheckin/platforms/<name>.py`
2. 实现 `CheckinPlatform` 接口：
   - `validate_login(cookie)` / `relogin()`
   - `do_checkin(cookie, sign_fn)` → `(status_code, body)`
   - `solve_captcha(captcha, sign_fn)`（可选）
3. `@register("<type>")` 注册，并在 `aicheckin/platforms/__init__.py` 导入。
4. 添加对应单元测试。

## 代码风格
- 类型注解（PEP 484）
- 模块 docstring
- 不使用未使用的导入
