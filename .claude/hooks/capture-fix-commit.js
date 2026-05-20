#!/usr/bin/env node
// capture-fix-commit.js
// Hook: PostToolUse on Bash — 当检测到 fix commit 时，捕获根因写入 memory
// 输入: stdin JSON { tool_name, tool_input: { command }, tool_result }

const fs = require('fs');
const path = require('path');

const MEMORY_DIR = 'C:/Users/星/.claude/projects/d--Code-Space-Meteor/memory';
const INCIDENTS_FILE = path.join(MEMORY_DIR, 'incidents.md');

try {
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const command = input.tool_input?.command || '';
  const result = input.tool_result || '';

  if (!command.match(/git\s+commit/)) {
    process.exit(0);
  }

  const msgMatch = command.match(/-m\s+["']?(fix\(?.*?\)?:?\s*.+)/i) ||
                   command.match(/-m\s+["']?(fix:.+)/i);
  if (!msgMatch) {
    process.exit(0);
  }

  const commitMsg = msgMatch[1].replace(/["']/g, '').trim();

  if (!fs.existsSync(MEMORY_DIR)) {
    fs.mkdirSync(MEMORY_DIR, { recursive: true });
  }

  let incidents = '';
  if (fs.existsSync(INCIDENTS_FILE)) {
    incidents = fs.readFileSync(INCIDENTS_FILE, 'utf8');
  }

  const today = new Date().toISOString().split('T')[0];
  const newEntry = `| ${today} | \`${commitMsg.substring(0, 40)}\` | [待分析] | [待关联] | hook 自动捕获 |`;

  if (incidents.includes('## 自进化统计')) {
    incidents = incidents.replace(
      '## 自进化统计',
      `${newEntry}\n\n## 自进化统计`
    );
    incidents = incidents.replace(
      /待提炼的新事件：(\d+)/,
      (_, count) => `待提炼的新事件：${parseInt(count) + 1}`
    );
  } else {
    incidents += `\n${newEntry}\n`;
  }

  fs.writeFileSync(INCIDENTS_FILE, incidents, 'utf8');
  console.log(`[hook] capture-fix-commit: recorded fix "${commitMsg.substring(0, 60)}" to memory`);
  process.exit(0);
} catch (err) {
  console.log(`[hook] capture-fix-commit: warning - ${err.message}`);
  process.exit(0);
}
