"""隔离真实 PG16/age 备份验证；资源只属于本次随机 run。"""

import json
import os
import secrets
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    result = subprocess.run(args, capture_output=True, timeout=300, **kwargs)
    if result.returncode:
        error = ROOT / ".local" / "r7-backup-last-error.log"
        fd = os.open(error, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(result.stderr)
        raise RuntimeError(
            "隔离验证失败；受限诊断记录于 .local/r7-backup-last-error.log"
        )
    return result.stdout


def main():
    tag = "chatbi-local-operations:r7-development"
    run_id = "chatbi-r7-backup-" + uuid.uuid4().hex[:12]
    network, pg = run_id + "-network", run_id + "-pg"
    created_network = created_pg = False
    try:
        with tempfile.TemporaryDirectory(
            prefix=run_id + "-", dir=ROOT / ".local"
        ) as directory:
            base = Path(directory)
            os.chmod(base, 0o700)
            envfile = base / "tool.env"
            password = secrets.token_hex(24)
            envfile.write_text(
                "POSTGRES_PASSWORD="
                + password
                + "\nPOSTGRES_MIGRATOR_PASSWORD="
                + password
                + "\n"
                "POSTGRES_USER=chatbi_migrator\nPOSTGRES_MIGRATOR_USER=chatbi_migrator\n"
                "POSTGRES_HOST="
                + pg
                + "\nPOSTGRES_DB=business\nPOSTGRES_CONTROL_DB=control\n"
            )
            os.chmod(envfile, 0o600)
            run(
                "docker",
                "network",
                "create",
                "--label",
                "com.chatbi.verification=" + run_id,
                network,
            )
            created_network = True
            run(
                "docker",
                "run",
                "-d",
                "--name",
                pg,
                "--network",
                network,
                "--label",
                "com.chatbi.verification=" + run_id,
                "--env-file",
                str(envfile),
                "postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777",
            )
            created_pg = True
            for _ in range(60):
                check = subprocess.run(
                    [
                        "docker",
                        "exec",
                        pg,
                        "pg_isready",
                        "-h",
                        "127.0.0.1",
                        "-U",
                        "chatbi_migrator",
                        "-d",
                        "postgres",
                    ],
                    capture_output=True,
                )
                if check.returncode == 0:
                    break
                time.sleep(0.5)
            else:
                raise RuntimeError("isolated PG startup timed out")
            run(
                "docker",
                "exec",
                "-i",
                pg,
                "psql",
                "-X",
                "-U",
                "chatbi_migrator",
                "-v",
                "ON_ERROR_STOP=1",
                "-d",
                "postgres",
                input=b"CREATE ROLE chatbi_app LOGIN;\nCREATE ROLE chatbi_control_user LOGIN;\nCREATE DATABASE control;\nCREATE DATABASE verify_control;\n",
            )
            for db in ("business", "control"):
                run(
                    "docker",
                    "exec",
                    "-i",
                    pg,
                    "psql",
                    "-X",
                    "-U",
                    "chatbi_migrator",
                    "-d",
                    db,
                    "-v",
                    "ON_ERROR_STOP=1",
                    input=b"CREATE TABLE records (id integer primary key, value text); INSERT INTO records VALUES (1,'initial');",
                )
            verification = base / "verification.py"
            verification.write_text(CONTAINER_VERIFICATION)
            verification.chmod(0o644)
            state = base / "state"
            state.mkdir(mode=0o700)
            output = run(
                "docker",
                "run",
                "--rm",
                "--name",
                run_id + "-tool",
                "--label",
                "com.chatbi.verification=" + run_id,
                "--network",
                network,
                "--user",
                f"{os.getuid()}:{os.getgid()}",
                "--env-file",
                str(envfile),
                "--mount",
                f"type=bind,source={state},target=/state",
                "--mount",
                f"type=bind,source={verification},target=/verification.py,readonly",
                "--entrypoint",
                "python3",
                tag,
                "/verification.py",
            )
            result = json.loads(output)
            (ROOT / ".local" / "r7-backup-verification.json").write_text(
                json.dumps(result, indent=2)
            )
            (ROOT / ".local" / "r7-backup-last-error.log").unlink(missing_ok=True)
            print(json.dumps(result, sort_keys=True))
    finally:
        subprocess.run(
            ["docker", "rm", "-f", run_id + "-tool"], capture_output=True, timeout=30
        )
        if created_pg:
            run("docker", "rm", "-fv", pg)
        if created_network:
            run("docker", "network", "rm", network)


CONTAINER_VERIFICATION = r"""
import json, os, subprocess, threading, time, sys
sys.path.insert(0,'/workspace')
from datetime import UTC, datetime
from pathlib import Path
from scripts.local_backup import BackupStore, BackupFailed, atomic_json, secure_directory
from scripts.local_backup_archive import digest_file
from scripts.local_backup_postgres import Snapshot, pg_environment, DatabaseBackupFailed, verify_dump
root=Path('/state')
os.umask(0o077)
store=BackupStore(root)
assert store.initialize_key() == 'initialized'
keyhash=digest_file(store.keys/'identity.txt')
store.initialize_key()
assert digest_file(store.keys/'identity.txt') == keyhash
source=secure_directory(store.operations/'source')
identity={'format':1,'source_commit':'a'*40,'api_image_id':'sha256:'+'b'*64,
'database_image_id':'sha256:'+'c'*64,'captured_at':datetime.now(UTC).isoformat()}
atomic_json(source/'identity.json',identity)
for name in ('config.env','secrets.env','release.env','rag-current.json','rag-manifest.json','compatibility.json'):
    (source/name).write_text('sensitive:'+name)
    (source/name).chmod(0o600)
stop=threading.Event()
counts=[]
def writer():
    for index in range(2,400):
        if stop.is_set(): return
        completed=subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1','-c',
            f"INSERT INTO records VALUES ({index},'concurrent')"],env=pg_environment('control'),
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if completed.returncode: raise RuntimeError('writer failed')
        counts.append(index)
        time.sleep(.01)
thread=threading.Thread(target=writer)
thread.start()
try:
    entry=store.backup(source,require_live=False)
finally:
    stop.set();thread.join()
assert counts, 'no concurrent control write happened'
target=root/'restore'
target.mkdir(mode=0o700)
manifest=store.decrypt(entry['id'],target)
subprocess.run(['pg_restore','--no-owner','--no-privileges','--exit-on-error','--dbname','verify_control',
    str(target/'control.dump')],env=pg_environment('verify_control'),check=True,
    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
with Snapshot('verify_control') as snapshot:
    restored=snapshot.fingerprints()
assert restored == manifest['databases']['control']['tables']
with Snapshot('control') as snapshot: live=snapshot.fingerprints()
assert live['public.records']['rows'] >= restored['public.records']['rows']
# Unknown ID, damaged cipher and wrong identity all refuse; previous catalog is preserved.
for unknown in ('../identity.txt','d'*32):
    try: store.known_artifact(unknown)
    except BackupFailed: pass
    else: raise AssertionError('unknown backup accepted')
artifact=store.backups/(entry['id']+'.age')
original=artifact.read_bytes()
artifact.write_bytes(original[:-1]+bytes([original[-1]^1]))
try: store.known_artifact(entry['id'])
except BackupFailed: pass
else: raise AssertionError('corrupt cipher accepted')
artifact.write_bytes(original)
# age encrypts for anyone with a public key; the trusted catalog protects origin.
other=store.keys/'wrong.txt'
subprocess.run(['age-keygen','-o',str(other)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
result=subprocess.run(['age','-d','-i',str(other),'-o',str(root/'wrong.zip'),str(artifact)],
                     stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
assert result.returncode != 0
original_key=(store.keys/'identity.txt').read_bytes()
(store.keys/'identity.txt').write_bytes(other.read_bytes())
try: store.backup(source,require_live=False)
except BackupFailed: pass
else: raise AssertionError('wrong store identity accepted')
(store.keys/'identity.txt').write_bytes(original_key)
corrupt=root/'corrupt.dump'
corrupt.write_bytes(b'not a PostgreSQL custom dump')
try: verify_dump(corrupt)
except DatabaseBackupFailed: pass
else: raise AssertionError('corrupt dump TOC accepted')
subprocess.run(['psql','-X','-q','-v','ON_ERROR_STOP=1','-c','CREATE ROLE stranger LOGIN;'],
    env=pg_environment('control'),check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
try: store.backup(source,require_live=False)
except DatabaseBackupFailed: pass
else: raise AssertionError('unknown database role accepted')
assert len(store.catalog()['backups']) == 1
assert not list(store.staging.iterdir())
print(json.dumps({'status':'PASS','tool_age':'v1.3.2','pg':'16','key_idempotence':'PASS',
    'snapshot_restore_fingerprints':'PASS','concurrent_writes':len(counts),
    'captured_control_rows':restored['public.records']['rows'],
    'live_control_rows':live['public.records']['rows'],'corrupt_wrong_key_unknown_id':'PASS','unknown_role_and_dump_toc':'PASS',
    'plaintext_staging_cleanup':'PASS','scope':'isolated synthetic databases; full ChatBI restore in Ticket05'}))
"""

if __name__ == "__main__":
    main()
