#!/usr/bin/env python3
"""detect-debug-residue.py
Hook: PreToolUse on Edit|Write — 检测 Python 调试残留
输入: stdin JSON { tool_name, tool_input: { file_path, new_string } }
"""

import json
import re
import sys

PATTERNS = [
    (r'^\s*print\s*\(', 'print() 调试残留'),
    (r'^\s*breakpoint\s*\(', 'breakpoint() 调试残留'),
    (r'^\s*pdb\.', 'pdb 调试残留'),
    (r'#\s*TODO\s+HACK', 'TODO HACK 临时标记'),
    (r'#\s*FIXME', 'FIXME 未修复标记'),
]

SKIP_SUFFIXES = ('.md', '.json', '.yaml', '.yml', '.toml', '.cfg', '.ini')

try:
    data = json.loads(sys.stdin.read())
    file_path = data.get('tool_input', {}).get('file_path', '') or data.get('tool_input', {}).get('path', '')

    if not file_path or any(file_path.endswith(s) for s in SKIP_SUFFIXES):
        sys.exit(0)

    new_string = data.get('tool_input', {}).get('new_string', '')
    if not new_string:
        sys.exit(0)

    warnings = []
    for i, line in enumerate(new_string.split('\n'), 1):
        for pattern, desc in PATTERNS:
            if re.search(pattern, line):
                warnings.append(f'  L{i}: {desc} — {line.strip()[:60]}')

    if warnings:
        print('[hook] detect-debug-residue: WARNING — 检测到调试残留:', file=sys.stderr)
        for w in warnings:
            print(w, file=sys.stderr)
        # 警告但不阻断，由人工决定
        sys.exit(0)

except Exception as e:
    print(f'[hook] detect-debug-residue: warning - {e}', file=sys.stderr)

sys.exit(0)
