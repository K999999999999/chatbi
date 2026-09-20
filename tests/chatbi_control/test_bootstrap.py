"""ChatBI 应用库和首个管理员初始化测试。"""

from pathlib import Path
from unittest import TestCase

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from src.authorization.passwords import hash_password, verify_password
from src.chatbi_control.bootstrap import (
    BootstrapError,
    create_first_admin,
    seed_rbac,
)
from src.chatbi_control.database import (
    ControlDatabaseConfig,
    ControlDatabaseConfigurationError,
    ControlDatabaseMigrationError,
    verify_control_schema,
)
from src.chatbi_control.models import Base, Permission, Role, User


class PasswordSecurityTest(TestCase):
    def test_password_is_argon2id_and_only_the_original_can_verify(self) -> None:
        password_hash = hash_password("a-secure-password-123")

        self.assertTrue(password_hash.startswith("$argon2id$"))
        self.assertTrue(verify_password("a-secure-password-123", password_hash))
        self.assertFalse(verify_password("wrong-password", password_hash))
        self.assertNotIn("a-secure-password-123", password_hash)

    def test_password_policy_rejects_short_password(self) -> None:
        with self.assertRaises(ValueError):
            hash_password("short")


class ControlBootstrapTest(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine)

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_rbac_seed_is_fixed_and_repeatable(self) -> None:
        with Session(self.engine) as session:
            seed_rbac(session)
            session.commit()
            seed_rbac(session)
            session.commit()

            roles = session.scalars(select(Role).order_by(Role.name)).all()
            permissions = session.scalars(
                select(Permission).order_by(Permission.name)
            ).all()

        self.assertEqual([role.name for role in roles], ["admin", "analyst"])
        self.assertEqual(
            [permission.name for permission in permissions],
            ["admin.audit", "admin.roles", "admin.users", "query.execute"],
        )

    def test_first_admin_is_created_with_forced_password_change(self) -> None:
        with Session(self.engine) as session:
            user = create_first_admin(
                session,
                username=" Admin-1 ",
                password="initial-password-123",
            )
            session.commit()

            saved = session.scalar(select(User).where(User.username == "admin-1"))

        self.assertIsNotNone(saved)
        assert saved is not None
        self.assertEqual(user.id, saved.id)
        self.assertTrue(saved.must_change_password)
        self.assertTrue(saved.is_active)
        self.assertNotEqual(saved.password_hash, "initial-password-123")
        self.assertTrue(verify_password("initial-password-123", saved.password_hash))
        self.assertEqual([role.name for role in saved.roles], ["admin"])

    def test_first_admin_initialization_can_only_happen_once(self) -> None:
        with Session(self.engine) as session:
            create_first_admin(
                session,
                username="admin-1",
                password="initial-password-123",
            )
            session.commit()

            with self.assertRaises(BootstrapError):
                create_first_admin(
                    session,
                    username="admin-2",
                    password="another-password-123",
                )

    def test_bootstrap_sql_is_explicit_and_does_not_touch_business_database(
        self,
    ) -> None:
        root = Path(__file__).resolve().parents[2]
        schema = (root / "database" / "control" / "001_schema.sql").read_text(
            encoding="utf-8"
        )
        grants = (root / "database" / "control" / "003_grants.sql").read_text(
            encoding="utf-8"
        )

        self.assertIn("CREATE TABLE IF NOT EXISTS users", schema)
        self.assertIn("CREATE TABLE IF NOT EXISTS audit_events", schema)
        self.assertIn("REVOKE UPDATE, DELETE ON TABLE audit_events", grants)
        self.assertNotIn("DROP DATABASE", schema.upper())
        self.assertNotIn("chatbi_mvp", schema)

    def test_control_database_configuration_is_separate_from_business_account(
        self,
    ) -> None:
        values = {
            "POSTGRES_DB": "chatbi_mvp",
            "POSTGRES_HOST": "127.0.0.1",
            "POSTGRES_PORT": "5433",
            "POSTGRES_MIGRATOR_USER": "chatbi_migrator",
            "POSTGRES_MIGRATOR_PASSWORD": "migrator-password",
            "POSTGRES_CONTROL_APP_PASSWORD": "control-password",
        }

        config = ControlDatabaseConfig.from_environment(values)

        self.assertEqual(config.database, "chatbi_control")
        self.assertEqual(config.app_user, "chatbi_control_user")
        self.assertEqual(config.migrator_user, "chatbi_migrator")
        self.assertEqual(config.app_connection_kwargs()["dbname"], "chatbi_control")

        with self.assertRaises(ControlDatabaseConfigurationError):
            ControlDatabaseConfig.from_environment(
                {**values, "POSTGRES_CONTROL_DB": "chatbi_mvp"}
            )
        with self.assertRaises(ControlDatabaseConfigurationError):
            ControlDatabaseConfig.from_environment(
                {**values, "POSTGRES_CONTROL_APP_USER": "chatbi_app"}
            )
        with self.assertRaises(ControlDatabaseConfigurationError):
            ControlDatabaseConfig.from_environment(
                {**values, "POSTGRES_CONTROL_APP_USER": "chatbi_migrator"}
            )

    def test_runtime_schema_version_must_be_present(self) -> None:
        with self.assertRaises(ControlDatabaseMigrationError):
            verify_control_schema(self.engine)

        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE schema_migrations (version TEXT PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO schema_migrations(version) VALUES ('chatbi-control-v1')"
            )

        verify_control_schema(self.engine)
