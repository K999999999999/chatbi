"""备份包固定格式与完整性检查；仅工具可访问明文 staging。"""

import hashlib
import json
import os
import re
import stat
import zipfile
from pathlib import Path

MEMBERS = frozenset(
    {
        "control.dump",
        "business.dump",
        "config.env",
        "secrets.env",
        "release.env",
        "rag-current.json",
        "rag-manifest.json",
        "compatibility.json",
    }
)
MAX_BYTES = 4 * 1024**3
MAX_MANIFEST = 1024**2
ID_PATTERN = re.compile(r"[0-9a-f]{32}")
SHA_PATTERN = re.compile(r"[0-9a-f]{64}")


class BackupInvalid(RuntimeError):
    """只传播安全分类，不传播 archive 内容或底层异常。"""


def digest_file(path):
    with open(path, "rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _load_manifest(archive):
    info = archive.getinfo("manifest.json")
    if info.file_size > MAX_MANIFEST:
        raise BackupInvalid("BACKUP_INVALID")
    value = json.loads(archive.read(info))
    if (
        not isinstance(value, dict)
        or value.get("format") != 1
        or not isinstance(value.get("id"), str)
        or not ID_PATTERN.fullmatch(value["id"])
        or not isinstance(value.get("members"), dict)
        or set(value["members"]) != MEMBERS
    ):
        raise BackupInvalid("BACKUP_INVALID")
    for member in value["members"].values():
        if (
            not isinstance(member, dict)
            or set(member) != {"sha256", "size"}
            or not isinstance(member["sha256"], str)
            or not SHA_PATTERN.fullmatch(member["sha256"])
            or type(member["size"]) is not int
            or not 0 < member["size"] <= MAX_BYTES
        ):
            raise BackupInvalid("BACKUP_INVALID")
    return value


def validate_bundle(path, *, expected_id=None):
    """完整读取每个允许成员并核对摘要；此步骤不写任何文件。"""
    try:
        with zipfile.ZipFile(path) as archive:
            items = archive.infolist()
            names = [item.filename for item in items]
            if len(names) != len(MEMBERS) + 1 or set(names) != MEMBERS | {
                "manifest.json"
            }:
                raise BackupInvalid("BACKUP_INVALID")
            if sum(item.file_size for item in items) > MAX_BYTES:
                raise BackupInvalid("BACKUP_INVALID")
            for item in items:
                mode = item.external_attr >> 16
                if (
                    item.is_dir()
                    or (stat.S_IFMT(mode) not in (0, stat.S_IFREG))
                    or item.flag_bits & 1
                    or item.compress_type != zipfile.ZIP_STORED
                ):
                    raise BackupInvalid("BACKUP_INVALID")
            manifest = _load_manifest(archive)
            if expected_id is not None and manifest["id"] != expected_id:
                raise BackupInvalid("BACKUP_INVALID")
            for name, expected in manifest["members"].items():
                if archive.getinfo(name).file_size != expected["size"]:
                    raise BackupInvalid("BACKUP_INVALID")
                with archive.open(name) as stream:
                    actual = hashlib.file_digest(stream, "sha256").hexdigest()
                if actual != expected["sha256"]:
                    raise BackupInvalid("BACKUP_INVALID")
            return manifest
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError):
        raise BackupInvalid("BACKUP_INVALID") from None


def write_bundle(directory, output, metadata):
    """构建固定成员 archive；调用者提供已捕获的敏感文件与身份。"""
    directory = Path(directory)
    manifest = dict(metadata, format=1, members={})
    for name in sorted(MEMBERS):
        path = directory / name
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= MAX_BYTES:
            raise BackupInvalid("BACKUP_INVALID")
        manifest["members"][name] = {"size": info.st_size, "sha256": digest_file(path)}
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(MEMBERS):
            archive.write(directory / name, arcname=name)
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
    return validate_bundle(output, expected_id=metadata["id"])


def extract_bundle(path, destination, *, expected_id):
    """先完整校验，再逐个排他写入空目录；从不使用 extractall。"""
    manifest = validate_bundle(path, expected_id=expected_id)
    target = Path(destination)
    if (
        not target.is_dir()
        or target.is_symlink()
        or any(target.iterdir())
        or target.stat().st_uid != os.getuid()
        or stat.S_IMODE(target.stat().st_mode) != 0o700
    ):
        raise BackupInvalid("BACKUP_INVALID")
    with zipfile.ZipFile(path) as archive:
        for name in sorted(MEMBERS):
            with archive.open(name) as source, (target / name).open("xb") as output:
                while chunk := source.read(1024**2):
                    output.write(chunk)
    return manifest
