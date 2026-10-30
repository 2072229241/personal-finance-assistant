# personal-finance-assistant · 常用任务
# 用法：make help

PYTHON     ?= python3
ENGINE     := scripts/finance_engine.py
SKILL_DIR  ?= $(HOME)/.claude/skills/personal-finance-assistant

.PHONY: help check test quickstart install clean

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

check: ## 语法检查（仅用标准库 py_compile）
	@$(PYTHON) -m py_compile $(ENGINE) && echo "✅ 语法检查通过"

test: check ## 冒烟测试（覆盖全部子命令，使用临时数据目录）
	@bash tests/test_engine.sh

quickstart: ## 端到端示例演示
	@bash examples/quickstart.sh

install: ## 安装为通用 Agent Skill（覆盖安装前请先备份你的数据目录）
	@mkdir -p "$(SKILL_DIR)"
	@cp -R SKILL.md README.md LICENSE CHANGELOG.md assets references scripts examples "$(SKILL_DIR)/"
	@echo "✅ 已安装到 $(SKILL_DIR)"
	@echo "   WorkBuddy 用户请改用：make install SKILL_DIR=~/.workbuddy/skills/personal-finance-assistant"

clean: ## 清理缓存与临时产物
	@rm -rf __pycache__ tmp.* .pytest_cache
	@find . -name "*.pyc" -delete
	@echo "✅ 已清理"
