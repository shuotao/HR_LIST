# -*- coding: utf-8 -*-
"""
PreToolUse hook：攔截違反 CLAUDE.md 唯一腳本原則的寫入。

對應 CLAUDE.md 第 5 / 5a / 5b 條：
- 禁止 scratch/ 內任何 .py 或 .txt
- 禁止專案根目錄裸 .py（必須位於 .agent/skills/<skill>/scripts/）
- 例外：.agent/、.claude/、web/、scripts/、tests/ 等子目錄

Hook 透過 stdin 收 JSON，回傳 exit code 2 + stderr 訊息來阻擋。
"""

import json
import os
import sys

# CLAUDE.md gotcha #1：Windows cp950 encoding
sys.stderr.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# 允許 .py 存在的目錄白名單（相對 ROOT）
ALLOWED_DIRS = (
    '.agent' + os.sep,
    '.claude' + os.sep,
    'web' + os.sep,
)


def is_violation(file_path: str) -> tuple[bool, str]:
    """判斷檔案路徑是否違反唯一腳本原則。返回 (是否違規, 訊息)。"""
    if not file_path:
        return False, ""

    abs_path = os.path.abspath(file_path)

    try:
        rel = os.path.relpath(abs_path, ROOT)
    except ValueError:
        return False, ""

    if rel.startswith('..'):
        return False, ""

    rel_norm = rel.replace('/', os.sep)
    parts = rel_norm.split(os.sep)

    if parts[0] == 'scratch':
        return True, (
            f"❌ 違反 CLAUDE.md 第 5 條（唯一腳本原則）：禁止在 scratch/ 寫入任何檔案。\n"
            f"   嘗試寫入：{rel}\n"
            f"   替代方案：\n"
            f"     - 一次性檢視 → 用 Read / Grep / Bash one-liner\n"
            f"     - 重複使用 3 次以上 → 升格至 .agent/skills/<skill>/scripts/ 並更新 CLAUDE.md\n"
            f"   工具缺口回報請走 CLAUDE.md 第 5b 條程序。"
        )

    if rel_norm.endswith('.py') and len(parts) == 1:
        return True, (
            f"❌ 違反 CLAUDE.md 第 5/5a 條：禁止在專案根目錄寫入裸 .py 檔。\n"
            f"   嘗試寫入：{rel}\n"
            f"   正式腳本必須放於：.agent/skills/<skill>/scripts/<name>.py\n"
            f"   臨時檢視一律使用 Read / Grep / Bash one-liner，不落地成 .py。"
        )

    return False, ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    if tool_name not in ('Write', 'Edit', 'MultiEdit', 'NotebookEdit'):
        sys.exit(0)

    tool_input = data.get('tool_input', {})
    file_path = tool_input.get('file_path') or tool_input.get('notebook_path') or ''

    violated, msg = is_violation(file_path)
    if violated:
        print(msg, file=sys.stderr)
        sys.exit(2)

    sys.exit(0)


if __name__ == '__main__':
    main()
