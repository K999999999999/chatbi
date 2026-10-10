"""PG16 客户端 Adapter：dump 与全表指纹共用 exported snapshot。"""

import json
import os
import selectors
import subprocess
import time
from pathlib import Path


class DatabaseBackupFailed(RuntimeError):
    pass


def pg_environment(database):
    env = dict(os.environ)
    env.update(
        PGHOST=os.environ.get("POSTGRES_HOST", "postgres"),
        PGPORT=os.environ.get("POSTGRES_PORT", "5432"),
        PGUSER=os.environ.get("POSTGRES_MIGRATOR_USER", "chatbi_migrator"),
        PGPASSWORD=os.environ["POSTGRES_MIGRATOR_PASSWORD"],
        PGDATABASE=database,
        PGCONNECT_TIMEOUT="5",
        PGOPTIONS="-c statement_timeout=60000 -c lock_timeout=5000",
    )
    return env


class Snapshot:
    def __init__(self, database, *, timeout=180):
        self._env = pg_environment(database)
        self._deadline = time.monotonic() + timeout
        self._process = None

    def __enter__(self):
        self._process = subprocess.Popen(
            ["psql", "-X", "--no-password", "-qAt", "-v", "ON_ERROR_STOP=1"],
            env=self._env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
        )
        try:
            self.query("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;", result=False)
            self.id = self.query("SELECT pg_export_snapshot();")
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self._process is not None:
            self._process.stdin.close()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=2)
            self._process.stdout.close()

    def query(self, sql, *, result=True):
        process = self._process
        try:
            process.stdin.write((sql + "\n").encode())
            if not result:
                return None
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                data = bytearray()
                while True:
                    remaining = self._deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise DatabaseBackupFailed("BACKUP_TIMEOUT")
                    char = process.stdout.read(1)
                    if char == b"\n":
                        return data.decode()
                    if not char or len(data) >= 1024**2:
                        raise DatabaseBackupFailed("BACKUP_DATABASE_FAILED")
                    data.extend(char)
        except (OSError, UnicodeError):
            raise DatabaseBackupFailed("BACKUP_DATABASE_FAILED") from None

    def fingerprints(self):
        tables = json.loads(
            self.query("""
SELECT COALESCE(json_agg(json_build_array(n.nspname,c.relname) ORDER BY n.nspname,c.relname),'[]'::json)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE c.relkind='r' AND n.nspname NOT IN ('pg_catalog','information_schema')
AND n.nspname NOT LIKE 'pg_toast%';
""")
        )
        result = {}
        for schema, table in tables:
            identifier = ".".join(
                '"' + name.replace('"', '""') + '"' for name in (schema, table)
            )
            # Catalog identifiers are double-quote escaped before this fixed query is formatted.
            query = """
SELECT json_build_object('rows',count(*),'sha256',encode(sha256(convert_to(
COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb)::text,'UTF8')),'hex'))
FROM {identifier} t;
""".format(identifier=identifier)  # nosec B608
            value = self.query(query)
            result[f"{schema}.{table}"] = json.loads(value)
        if not result:
            raise DatabaseBackupFailed("BACKUP_DATABASE_FAILED")
        return result

    def approved_roles(self):
        roles = json.loads(
            self.query("""
SELECT COALESCE(json_agg(json_build_object('name',rolname,'superuser',rolsuper,
'create_database',rolcreatedb,'create_role',rolcreaterole,'login',rolcanlogin,
'replication',rolreplication,'bypass_rls',rolbypassrls) ORDER BY rolname),'[]'::json)
FROM pg_roles WHERE left(rolname,3) <> 'pg_';
""")
        )
        migrator = self._env["PGUSER"]
        expected = {migrator, "chatbi_app", "chatbi_control_user"}
        if {role["name"] for role in roles} != expected:
            raise DatabaseBackupFailed("BACKUP_SOURCE_CHANGED")
        for role in roles:
            if role["name"] != migrator and any(
                role[key]
                for key in (
                    "superuser",
                    "create_database",
                    "create_role",
                    "replication",
                    "bypass_rls",
                )
            ):
                raise DatabaseBackupFailed("BACKUP_SOURCE_CHANGED")
            if not role["login"]:
                raise DatabaseBackupFailed("BACKUP_SOURCE_CHANGED")
        return roles

    def dump(self, path):
        try:
            subprocess.run(
                [
                    "pg_dump",
                    "--no-password",
                    "--format=custom",
                    "--snapshot",
                    self.id,
                    "--file",
                    str(path),
                ],
                env=self._env,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=max(0.01, self._deadline - time.monotonic()),
            )
        except subprocess.TimeoutExpired:
            raise DatabaseBackupFailed("BACKUP_TIMEOUT") from None
        except (OSError, subprocess.CalledProcessError):
            raise DatabaseBackupFailed("BACKUP_DATABASE_FAILED") from None


def verify_dump(path):
    try:
        subprocess.run(
            ["pg_restore", "--list", str(Path(path))],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        raise DatabaseBackupFailed("BACKUP_INVALID") from None
