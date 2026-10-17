import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import { mkdtempSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { reportPath } from '../test-support/report-path';
import { publishExclusiveJson } from '../test-support/exclusive-report';

test('浏览器验收报告写入调用方指定的目录', () => {
  const previous = process.env.CHATBI_CONTAINER_REPORT_DIR;
  process.env.CHATBI_CONTAINER_REPORT_DIR = 'private-acceptance-report';
  try {
    expect(reportPath('browser.json')).toContain('private-acceptance-report');
    expect(reportPath('browser.json').endsWith('browser.json')).toBe(true);
  } finally {
    if (previous === undefined) delete process.env.CHATBI_CONTAINER_REPORT_DIR;
    else process.env.CHATBI_CONTAINER_REPORT_DIR = previous;
  }
});

test('浏览器验收报告拒绝越出报告目录的文件名', () => {
  expect(() => reportPath('../credentials.env')).toThrow('报告文件名无效');
  expect(() => reportPath('..')).toThrow('报告文件名无效');
});

test('未配置目录时继续使用容器报告挂载点', () => {
  const previousContainer = process.env.CHATBI_CONTAINER_REPORT_DIR;
  const previousReal = process.env.CHATBI_REAL_E2E_REPORT_DIR;
  delete process.env.CHATBI_CONTAINER_REPORT_DIR;
  delete process.env.CHATBI_REAL_E2E_REPORT_DIR;
  try {
    expect(reportPath('browser.json')).toBe('/reports/browser.json');
  } finally {
    if (previousContainer !== undefined) {
      process.env.CHATBI_CONTAINER_REPORT_DIR = previousContainer;
    }
    if (previousReal !== undefined) process.env.CHATBI_REAL_E2E_REPORT_DIR = previousReal;
  }
});

test('容器报告目录为空时回退到 host real run 并能读取 start.json', () => {
  const previousContainer = process.env.CHATBI_CONTAINER_REPORT_DIR;
  const previousReal = process.env.CHATBI_REAL_E2E_REPORT_DIR;
  const directory = mkdtempSync(resolve(tmpdir(), 'chatbi-real-report-'));
  const expected = JSON.stringify({ run_id: 'host-real-run' });
  writeFileSync(resolve(directory, 'start.json'), expected, { mode: 0o600 });
  process.env.CHATBI_CONTAINER_REPORT_DIR = '  ';
  process.env.CHATBI_REAL_E2E_REPORT_DIR = directory;
  try {
    expect(reportPath('start.json')).toBe(resolve(directory, 'start.json'));
    expect(readFileSync(reportPath('start.json'), 'utf8')).toBe(expected);
  } finally {
    if (previousContainer === undefined) delete process.env.CHATBI_CONTAINER_REPORT_DIR;
    else process.env.CHATBI_CONTAINER_REPORT_DIR = previousContainer;
    if (previousReal === undefined) delete process.env.CHATBI_REAL_E2E_REPORT_DIR;
    else process.env.CHATBI_REAL_E2E_REPORT_DIR = previousReal;
    rmSync(directory, { recursive: true, force: true });
  }
});

test('非空容器报告目录优先于 host real run 目录', () => {
  const previousContainer = process.env.CHATBI_CONTAINER_REPORT_DIR;
  const previousReal = process.env.CHATBI_REAL_E2E_REPORT_DIR;
  process.env.CHATBI_CONTAINER_REPORT_DIR = 'container-reports';
  process.env.CHATBI_REAL_E2E_REPORT_DIR = 'host-real-reports';
  try {
    expect(reportPath('browser.json')).toContain('container-reports');
    expect(reportPath('browser.json')).not.toContain('host-real-reports');
  } finally {
    if (previousContainer === undefined) delete process.env.CHATBI_CONTAINER_REPORT_DIR;
    else process.env.CHATBI_CONTAINER_REPORT_DIR = previousContainer;
    if (previousReal === undefined) delete process.env.CHATBI_REAL_E2E_REPORT_DIR;
    else process.env.CHATBI_REAL_E2E_REPORT_DIR = previousReal;
  }
});

test('最终 JSON 报告以私有权限排他发布且不覆盖既有证据', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'chatbi-report-'));
  const path = resolve(directory, 'run.json');
  try {
    publishExclusiveJson(path, { status: 'passed' });
    const original = readFileSync(path);
    expect(statSync(path).mode & 0o777).toBe(0o600);
    expect(() => publishExclusiveJson(path, { status: 'failed' })).toThrow();
    expect(readFileSync(path)).toEqual(original);
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('最终报告发布成功后临时链接清理失败不改变报告结论', () => {
  const directory = mkdtempSync(resolve(tmpdir(), 'chatbi-report-'));
  const path = resolve(directory, 'run.json');
  const originalUnlink = fs.unlinkSync;
  let failedTemporaryCleanup = false;
  fs.unlinkSync = ((target: fs.PathLike) => {
    if (String(target).endsWith('.tmp')) {
      failedTemporaryCleanup = true;
      throw Object.assign(new Error('simulated temporary cleanup failure'), { code: 'EACCES' });
    }
    return originalUnlink(target);
  }) as typeof fs.unlinkSync;
  try {
    expect(() => publishExclusiveJson(path, { status: 'passed', exit_code: 0 })).not.toThrow();
    expect(failedTemporaryCleanup).toBe(true);
    expect(JSON.parse(readFileSync(path, 'utf8'))).toEqual({ status: 'passed', exit_code: 0 });
  } finally {
    fs.unlinkSync = originalUnlink;
    rmSync(directory, { recursive: true, force: true });
  }
});
