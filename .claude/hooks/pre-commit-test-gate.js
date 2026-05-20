#!/usr/bin/env node
// pre-commit-test-gate.js
// Hook: PreToolUse on Bash — 当检测到 git commit 时，先运行 pytest
// 输入: stdin JSON { tool_name, tool_input: { command } }

const fs = require('fs');
const { execSync } = require('child_process');

try {
  if (process.stdin.isTTY) {
    process.exit(0);
  }
  const input = JSON.parse(fs.readFileSync(0, 'utf8'));
  const command = input.tool_input?.command || '';

  if (!command.match(/git\s+commit/)) {
    process.exit(0);
  }

  if (command.includes('--no-verify') || command.includes('--amend')) {
    console.log('[hook] pre-commit-test-gate: --no-verify or --amend detected, skipping');
    process.exit(0);
  }

  // 检查是否有 tests 目录或 pytest 配置
  const hasTests = fs.existsSync('tests') || fs.existsSync('test');
  const hasPytestConfig = fs.existsSync('pytest.ini') || fs.existsSync('pyproject.toml');
  if (!hasTests && !hasPytestConfig) {
    console.log('[hook] pre-commit-test-gate: no test directory found, skipping');
    process.exit(0);
  }

  console.log('[hook] pre-commit-test-gate: running pytest before commit...');
  const result = execSync('python -m pytest --tb=short 2>&1', {
    encoding: 'utf8',
    timeout: 120000,
    stdio: 'pipe'
  });

  if (result.includes('FAILED') || result.includes('failed')) {
    const failedMatch = result.match(/(\d+)\s+failed/);
    const failCount = failedMatch ? failedMatch[1] : '?';
    console.error(`[hook] BLOCKED: ${failCount} test(s) failed. Fix tests before committing.`);
    console.error('[hook] Run `python -m pytest` to see details.');
    process.exit(2);
  }

  console.log('[hook] pre-commit-test-gate: all tests passed ✓');
  process.exit(0);
} catch (err) {
  if (err.status === 1 || (err.stdout && err.stdout.includes('FAILED'))) {
    console.error('[hook] BLOCKED: Tests failed. Fix before committing.');
    console.error('[hook] Run `python -m pytest` to see details.');
    process.exit(2);
  }
  console.log(`[hook] pre-commit-test-gate: warning - ${err.message}`);
  process.exit(0);
}
