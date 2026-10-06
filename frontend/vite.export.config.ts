import { createHash } from 'node:crypto';
import { readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const frontendRoot = process.cwd();
const outputRoot = path.join(frontendRoot, 'dist-export');

function filesUnder(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const absolute = path.join(directory, entry.name);
    if (entry.isSymbolicLink()) throw new Error(`export build input cannot be a symlink: ${absolute}`);
    if (entry.isDirectory()) return filesUnder(absolute);
    return entry.isFile() ? [absolute] : [];
  });
}

function sha256(content: Buffer | string): string {
  return createHash('sha256').update(content).digest('hex');
}

function integrityManifest(): Plugin {
  return {
    name: 'chatbi-export-integrity-manifest',
    closeBundle() {
      const inputs = [
        ...filesUnder(path.join(frontendRoot, 'src')),
        path.join(frontendRoot, 'export.html'),
        path.join(frontendRoot, 'vite.export.config.ts'),
        path.join(frontendRoot, 'tsconfig.json'),
        path.join(frontendRoot, 'package.json'),
        path.join(frontendRoot, 'package-lock.json'),
      ].sort();
      const sourceHash = createHash('sha256');
      for (const file of inputs) {
        sourceHash.update(path.relative(frontendRoot, file).replaceAll(path.sep, '/'));
        sourceHash.update('\0');
        sourceHash.update(readFileSync(file));
        sourceHash.update('\0');
      }
      const outputFiles = filesUnder(outputRoot).sort();
      const files = Object.fromEntries(outputFiles.map(file => {
        if (!statSync(file).isFile()) throw new Error(`export output is not a regular file: ${file}`);
        const relative = path.relative(outputRoot, file).replaceAll(path.sep, '/');
        const content = readFileSync(file);
        return [relative, { sha256: sha256(content), size: content.length }];
      }));
      const manifest = {
        version: 1,
        source_sha256: sourceHash.digest('hex'),
        package_lock_sha256: sha256(readFileSync(path.join(frontendRoot, 'package-lock.json'))),
        files,
      };
      writeFileSync(path.join(outputRoot, 'bundle-manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`, { mode: 0o644 });
    },
  };
}

export default defineConfig({
  root: frontendRoot,
  base: '/',
  plugins: [react(), integrityManifest()],
  build: {
    outDir: outputRoot,
    emptyOutDir: true,
    sourcemap: false,
    modulePreload: { polyfill: false },
    rollupOptions: { input: path.join(frontendRoot, 'export.html') },
  },
});
