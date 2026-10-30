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

token 在 https://github.com/settings/tokens 生成（Tokens classic），公开仓库**只勾 `repo` 一项**即可
（其子项 `public_repo` 提供公开仓库写入权限）。

> ⚠️ **token 要粘在 git 的 Password 提示处，不要直接粘到命令行。**
> 直接粘到命令行会被 shell 当成命令执行（回显出来、且进 history），token 当场泄露，只能吊销重发。
> 正确顺序是先看到 `Username for 'https://github.com':` 再输入用户名，
> 出现 `Password for 'https://2072229241@github.com':` 时粘贴 token——**此处不回显，什么都不显示才是正常的**。

```bash
# 若不慎把 token 粘进了命令行：先吊销旧 token，再清理 history
# https://github.com/settings/tokens → Delete
LC_ALL=C sed -i '' '/ghp_/d' ~/.zsh_history      # 关闭该终端窗口后执行
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
| 终端里把 token 当成命令回显出来 | token 粘错了位置（见上文 HTTPS 提示）。吊销旧 token，用新 token 在 Password 提示处粘贴 |
| 推完没生效、反复要求输入凭据 | 钥匙串存了旧密码，先 `printf "protocol=https\nhost=github.com\n" \| git credential-osxkeychain erase` 再推 |
| `Recv failure: Operation timed out` | 终端的 git 不会自动跟随系统代理。用 `scutil --proxy` 查出端口，再配给 git（见下） |

### 让 git 走系统代理

浏览器能打开 GitHub、终端却超时，通常是这个原因：系统代理是开着的，但 git 不读它。

```bash
scutil --proxy                       # 查看 HTTPSPort / HTTPSProxy，如 127.0.0.1:12334
git config http.proxy  http://127.0.0.1:12334     # 只对当前仓库生效
git config https.proxy http://127.0.0.1:12334
git config --global http.proxy  http://127.0.0.1:12334   # 想对所有仓库生效就加 --global
git config --global https.proxy http://127.0.0.1:12334
```

更换代理软件后端口会变，需要同步更新；不用代理时删掉：

```bash
git config --global --unset http.proxy
git config --global --unset https.proxy
```

若 HTTP 代理不通，可改用 SOCKS（同一端口通常也支持）：`git config http.proxy socks5://127.0.0.1:12334`。
