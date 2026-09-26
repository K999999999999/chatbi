-- ChatBI 应用运行时账号权限。
-- 该文件在 chatbi_control 内执行；chatbi_app 不应出现在本文件中。
REVOKE CONNECT ON DATABASE chatbi_control FROM PUBLIC;
GRANT CONNECT ON DATABASE chatbi_control TO chatbi_control_user;
GRANT USAGE ON SCHEMA public TO chatbi_control_user;

GRANT SELECT, INSERT, UPDATE ON TABLE users TO chatbi_control_user;
GRANT SELECT, UPDATE ON TABLE roles TO chatbi_control_user;
GRANT SELECT ON TABLE permissions TO chatbi_control_user;
GRANT SELECT, INSERT, DELETE ON TABLE user_roles TO chatbi_control_user;
GRANT SELECT, INSERT, DELETE ON TABLE role_permissions TO chatbi_control_user;
GRANT SELECT, INSERT, UPDATE ON TABLE sessions TO chatbi_control_user;
GRANT SELECT, INSERT ON TABLE audit_events TO chatbi_control_user;
GRANT SELECT ON TABLE schema_migrations TO chatbi_control_user;

REVOKE DELETE ON TABLE users FROM chatbi_control_user;
REVOKE INSERT, UPDATE, DELETE ON TABLE permissions FROM chatbi_control_user;
REVOKE UPDATE, DELETE ON TABLE audit_events FROM chatbi_control_user;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO chatbi_control_user;
