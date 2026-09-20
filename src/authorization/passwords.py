"""ChatBI 密码策略和 Argon2id 哈希。"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_PASSWORD_LENGTH = 12

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=2,
)


def validate_password(password: str) -> None:
    """验证 V1 密码策略，不记录或返回密码内容。"""

    if not isinstance(password, str) or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"密码长度不能少于 {MIN_PASSWORD_LENGTH} 位")


def hash_password(password: str) -> str:
    """生成 Argon2id 密码哈希。"""

    validate_password(password)
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码；所有不匹配或非法哈希都返回 False。"""

    if not isinstance(password, str) or not isinstance(password_hash, str):
        return False
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False
