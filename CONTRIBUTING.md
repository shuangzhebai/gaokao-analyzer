# 贡献指南

感谢你考虑为 gaokao-analyzer 做出贡献！

## 开发环境

1. Fork 并克隆仓库
2. 创建虚拟环境：`python -m venv .venv && source .venv/bin/activate`
3. 安装依赖：`pip install -r requirements.txt -r requirements-dev.txt`
4. 安装 pre-commit：`pre-commit install`

## 代码风格

- 使用 `ruff` 做 lint，`black` 做格式化（line-length=100）
- 所有公共函数必须有类型注解（mypy strict）
- 提交前运行：`pre-commit run --all-files`

## 提交 PR

1. 从 main 创建新分支：`git checkout -b feat/my-feature`
2. 编写代码并添加测试
3. 确保 `pytest tests/ -q` 全部通过
4. 确保 `mypy --strict app.py` 无错误
5. 提交并推送：`git push origin feat/my-feature`
6. 创建 Pull Request 到 main 分支

## PR 模板

请使用 `.github/PULL_REQUEST_TEMPLATE.md` 中的模板。

## 报告问题

使用 Issue 模板：[Bug 报告](.github/ISSUE_TEMPLATE/bug_report.md) | [功能请求](.github/ISSUE_TEMPLATE/feature_request.md)
