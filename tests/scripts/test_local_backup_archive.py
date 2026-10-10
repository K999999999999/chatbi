import zipfile

import pytest

from scripts.local_backup_archive import BackupInvalid, validate_bundle


def test_bundle_rejects_path_traversal_before_any_extraction(tmp_path):
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("../private-key", "private data")
    with pytest.raises(BackupInvalid):
        validate_bundle(path)
    assert not (tmp_path.parent / "private-key").exists()


def test_bundle_rejects_unknown_members_and_duplicate_manifest(tmp_path):
    path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", "{}")
        archive.writestr("unexpected.sh", "private data")
    with pytest.raises(BackupInvalid):
        validate_bundle(path)


def make_bundle(tmp_path):
    from scripts.local_backup_archive import MEMBERS, write_bundle

    source = tmp_path / "source"
    source.mkdir()
    for name in MEMBERS:
        (source / name).write_bytes(("private:" + name).encode())
    path = tmp_path / "valid.zip"
    metadata = {"id": "a" * 32, "source": "b" * 40}
    manifest = write_bundle(source, path, metadata)
    return path, manifest


def test_complete_bundle_validates_and_extracts_only_fixed_members(tmp_path):
    from scripts.local_backup_archive import MEMBERS, extract_bundle

    path, manifest = make_bundle(tmp_path)
    assert validate_bundle(path, expected_id="a" * 32) == manifest
    target = tmp_path / "restore"
    target.mkdir(mode=0o700)
    assert extract_bundle(path, target, expected_id="a" * 32) == manifest
    assert set(p.name for p in target.iterdir()) == MEMBERS
    assert (target / "secrets.env").read_bytes() == b"private:secrets.env"
    with pytest.raises(BackupInvalid):
        extract_bundle(path, target, expected_id="a" * 32)


def test_wrong_registered_id_refuses_before_extraction(tmp_path):
    from scripts.local_backup_archive import extract_bundle

    path, _ = make_bundle(tmp_path)
    target = tmp_path / "restore"
    target.mkdir(mode=0o700)
    with pytest.raises(BackupInvalid):
        extract_bundle(path, target, expected_id="c" * 32)
    assert not list(target.iterdir())


def test_valid_zip_with_tampered_member_fails_hash(tmp_path):
    path, _ = make_bundle(tmp_path)
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(path) as source, zipfile.ZipFile(tampered, "w") as output:
        for member in source.infolist():
            data = source.read(member)
            output.writestr(
                member, b"changed" if member.filename == "control.dump" else data
            )
    with pytest.raises(BackupInvalid):
        validate_bundle(tampered)


def test_duplicate_and_symlink_members_refused(tmp_path):
    path, _ = make_bundle(tmp_path)
    with zipfile.ZipFile(path, "a") as archive:
        with pytest.warns(UserWarning):
            archive.writestr("manifest.json", "{}")
    with pytest.raises(BackupInvalid):
        validate_bundle(path)
