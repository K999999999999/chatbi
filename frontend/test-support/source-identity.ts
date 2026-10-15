import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';

export type SourceIdentity = {
  verified: boolean;
  git_commit: string | null;
  git_dirty: boolean | null;
  tracked_changes_hash: string | null;
};

export function captureSourceIdentity(repositoryRoot: string): SourceIdentity {
  try {
    const git = (args: string[]) => execFileSync('git', ['-C', repositoryRoot, ...args], { encoding: 'utf8' }).trim();
    const commit = git(['rev-parse', '--verify', 'HEAD']);
    const dirty = git(['status', '--porcelain=v1', '-z']).length > 0;
    const diff = execFileSync('git', ['-C', repositoryRoot, 'diff', '--binary', '--no-ext-diff', 'HEAD', '--']);
    if (!/^[0-9a-f]{40,64}$/.test(commit)) throw new Error('Git commit identity is invalid');
    return {
      verified: true,
      git_commit: commit,
      git_dirty: dirty,
      tracked_changes_hash: createHash('sha256').update(diff).digest('hex'),
    };
  } catch {
    return { verified: false, git_commit: null, git_dirty: null, tracked_changes_hash: null };
  }
}
