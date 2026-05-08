#!/usr/bin/env node
/**
 * JavaScript runner entrypoint — spec §7.4.
 *
 * Reads /work/manifest.json, materializes code + test files,
 * runs jest with --json, emits trial JSON to stdout.
 *
 * wall_ns reported here is informational only.
 * The scheduler measures wall time externally (spec §7.3 point 1).
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execFileSync, spawnSync } = require('child_process');

const WORK = '/work';
const MANIFEST_PATH = path.join(WORK, 'manifest.json');

function emitTrial({ index, wall_ns, mem_kb, exit_code, framework_passed, sandbox_violation, stderr_snippet }) {
  process.stdout.write(JSON.stringify({
    index,
    wall_ns,
    mem_kb,
    exit_code,
    framework_passed,
    sandbox_violation,
    stderr_snippet: stderr_snippet ?? null,
  }) + '\n');
}

function emitError(msg) {
  emitTrial({ index: 0, wall_ns: 0, mem_kb: 0, exit_code: 1, framework_passed: false, sandbox_violation: false, stderr_snippet: msg });
}

function main() {
  if (!fs.existsSync(MANIFEST_PATH)) {
    emitError('manifest.json not found');
    return;
  }

  let manifest;
  try {
    manifest = JSON.parse(fs.readFileSync(MANIFEST_PATH, 'utf8'));
  } catch (e) {
    emitError(`manifest.json parse error: ${e.message}`);
    return;
  }

  const { code, test_suite, trial_index = 0 } = manifest;
  const { files = [], entrypoint = 'test.js' } = test_suite || {};

  // Materialise solution as solution.js (imported by tests).
  fs.writeFileSync(path.join(WORK, 'solution.js'), code, 'utf8');

  // Materialise test files.
  for (const tf of files) {
    const target = path.join(WORK, tf.name);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, tf.content, 'utf8');
  }

  // Write minimal jest config (no config file needed — inline via CLI).
  const timeoutMs = (parseInt(process.env.POLYEVAL_TIMEOUT_S ?? '30', 10) * 1000);

  const t0 = process.hrtime.bigint();

  const result = spawnSync(
    'jest',
    [
      '--no-coverage',
      '--json',
      '--testPathPattern', path.join(WORK, entrypoint),
      '--testTimeout', String(timeoutMs),
      '--forceExit',
    ],
    {
      cwd: WORK,
      timeout: timeoutMs + 5000,
      env: {
        ...process.env,
        // Prevent jest from trying to find config files up the tree.
        JEST_JASMINE2: '1',
      },
      encoding: 'utf8',
    }
  );

  const t1 = process.hrtime.bigint();
  const wall_ns = Number(t1 - t0);

  const exitCode = result.status ?? 1;
  let frameworkPassed = false;
  let stderrSnippet = (result.stderr ?? '').slice(0, 512);

  // jest --json writes the JSON report to stdout.
  try {
    const report = JSON.parse(result.stdout ?? '{}');
    frameworkPassed = report.success === true &&
                      (report.numFailedTests ?? 0) === 0 &&
                      (report.numFailedTestSuites ?? 0) === 0;
  } catch (_) {
    frameworkPassed = exitCode === 0;
  }

  emitTrial({
    index: trial_index,
    wall_ns,
    mem_kb: process.memoryUsage().rss / 1024 | 0,
    exit_code: exitCode,
    framework_passed: frameworkPassed,
    sandbox_violation: false,
    stderr_snippet: stderrSnippet || null,
  });
}

main();
