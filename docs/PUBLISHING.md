# 发布到 GitHub（维护者指南）

本文档记录从「本地目录」到「公开仓库可克隆」的完整命令，地址已按实际账号填好：

- 仓库地址：`https://github.com/2072229241/personal-finance-assistant`
- 仓库名：`personal-finance-assistant`，可见性 Public

## 0. 发布前检查清单

```bash
cd personal-finance-assistant
make check && make test        # 语法检查 + 冒烟测试必须全绿
```

- [x] `README.md` / `docs/PUBLISHING.md` 中的仓库地址已替换为 `2072229241`
- [ ] `LICENSE` 中的 `Copyright (c) 2026 personal-finance-assistant contributors` 已替换为你的名字/组织
- [ ] 仓库内不含真实账目数据（账本默认在 `~/.personal-finance-assistant/`，不在仓库内）
- [ ] 已确认无密钥、无内链、无个人绝对路径

自查敏感信息（应无输出）：

```bash
grep -rniE "(api[_-]?key|secret|token|password|sk-[A-Za-z0-9]{10,})" . || echo "无密钥"
grep -rnE "(/Users/[a-z0-9_.-]+|C:\\\\Users\\\\|/home/[a-z0-9_-]+)" . || echo "无个人绝对路径"
```

## 1. 在 GitHub 上创建仓库

- 打开 https://github.com/new
- Repository name：`personal-finance-assistant`
- 可见性：**Public**
- **不要**勾选 "Add a README file" / ".gitignore" / "Choose a license"（本地已有，否则首次推送会冲突）

创建完成后页面会给出仓库地址，下面用 `git@github.com:2072229241/personal-finance-assistant.git`（SSH）
或 `https://github.com/2072229241/personal-finance-assistant.git`（HTTPS，推荐新手）。

## 2. 初始化本地仓库并首次推送

```bash
cd personal-finance-assistant

git init -b main
git add .
git commit -m "feat: 开源首发 personal-finance-assistant v1.0.0"

git remote add origin git@github.com:2072229241/personal-finance-assistant.git
git push -u origin main
```

HTTPS 方式（会提示输入 GitHub 用户名与 **Personal Access Token**，不再是登录密码）：

```bash
git remote add origin https://github.com/2072229241/personal-finance-assistant.git
git push -u origin main
```

> 若提示 `gh auth login` 更省事：安装 [GitHub CLI](https://cli.github.com/) 后执行 `gh auth login`，
> 然后 `gh repo create personal-finance-assistant --public --source=. --push` 可一步完成创建与推送。

## 3. 后续迭代

```bash
git checkout -b feat/weekly-report
# ... 改动 ...
make test
git add . && git commit -m "feat: 支持按周生成消费报告"
git push -u origin feat/weekly-report
# 在 GitHub 上开 PR → 合并后
git checkout main && git pull
```

## 4. 发版

1. 更新 `scripts/finance_engine.py` 的 `__version__` 与 `SKILL.md` frontmatter 的 `version`
2. 在 `CHANGELOG.md` 增加新版本条目
3. 打 tag 并推送：

```bash
git tag -a v1.1.0 -m "v1.1.0: 支持按周报表"
git push origin v1.1.0
```

4. 在 GitHub Releases 页面基于该 tag 创建 Release，粘贴 CHANGELOG 对应条目

## 5. 提升被发现的概率（可选）

- 仓库 About 中填写简介与 Topics：`finance`、`bookkeeping`、`budgeting`、`personal-finance`、`agent-skills`、`llm`、`skill`
- 在 About 的 Website 字段填写你的主页或文档链接
- 勾选 "Include this repository in search results"

## 6. 常见推送问题

| 现象 | 原因 / 处理 |
|------|-------------|
| `Permission denied (publickey)` | 未配置 SSH key。执行 `gh auth login` 或改用 HTTPS |
| `Support for password authentication was removed` | 需改用 Personal Access Token（Settings → Developer settings → Tokens → 勾选 `repo`） |
| `refusing to merge unrelated histories` | 远端已有 README/LICENSE。先 `git pull origin main --allow-unrelated-histories` 再推送 |
| `Updates were rejected because the remote contains work` | 先 `git pull --rebase origin main` 再 `git push` |
