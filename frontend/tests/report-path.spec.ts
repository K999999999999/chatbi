import { test, expect } from '@playwright/test';
import { reportPath } from '../test-support/report-path';

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
  const previous = process.env.CHATBI_CONTAINER_REPORT_DIR;
  delete process.env.CHATBI_CONTAINER_REPORT_DIR;
  try {
    expect(reportPath('browser.json')).toBe('/reports/browser.json');
  } finally {
    if (previous !== undefined) process.env.CHATBI_CONTAINER_REPORT_DIR = previous;
  }
});
