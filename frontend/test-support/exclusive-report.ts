import fs from 'node:fs';
import {
  closeSync,
  fsyncSync,
  linkSync,
  openSync,
  writeFileSync,
} from 'node:fs';
import { randomUUID } from 'node:crypto';
import { basename, dirname, resolve } from 'node:path';

export function publishExclusiveJson(path: string, value: unknown): void {
  const target = resolve(path);
  const name = basename(target);
  if (!/^[A-Za-z0-9][A-Za-z0-9_.-]{0,122}\.json$/.test(name)) {
    throw new Error('报告文件名无效');
  }

  const temporary = resolve(dirname(target), `.${name}.${randomUUID()}.tmp`);
  let descriptor: number | undefined;
  let published = false;
  try {
    descriptor = openSync(temporary, 'wx', 0o600);
    writeFileSync(descriptor, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
    fsyncSync(descriptor);
    closeSync(descriptor);
    descriptor = undefined;
    // A hard link publishes complete bytes atomically and fails if the target exists.
    linkSync(temporary, target);
    published = true;
  } finally {
    if (descriptor !== undefined) closeSync(descriptor);
    try {
      fs.unlinkSync(temporary);
    } catch (error) {
      // The final path already references complete bytes; a private staging link must not
      // make the published report disagree with the command's exit status.
      if (!published && (error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
    }
  }
}
