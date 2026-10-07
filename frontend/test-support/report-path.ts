import { basename, resolve } from 'node:path';

export function reportPath(file: string): string {
  if (!file || file === '.' || file === '..' || file.includes('/') || file.includes('\\') || basename(file) !== file) {
    throw new Error('报告文件名无效');
  }
  const root = process.env.CHATBI_CONTAINER_REPORT_DIR?.trim() || '/reports';
  return resolve(root, file);
}
