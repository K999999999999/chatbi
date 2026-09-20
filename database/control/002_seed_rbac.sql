-- ChatBI V1 固定角色和权限目录。
INSERT INTO roles(name, description)
VALUES
    ('admin', 'ChatBI 管理员'),
    ('analyst', 'ChatBI 查询用户')
ON CONFLICT (name) DO UPDATE
SET description = EXCLUDED.description;

INSERT INTO permissions(name, description)
VALUES
    ('query.execute', '执行 ChatBI 查询'),
    ('admin.users', '管理 ChatBI 用户'),
    ('admin.roles', '管理 ChatBI 角色和权限'),
    ('admin.audit', '查看 ChatBI 审计记录')
ON CONFLICT (name) DO UPDATE
SET description = EXCLUDED.description;

DELETE FROM role_permissions
WHERE role_id IN (SELECT id FROM roles WHERE name IN ('admin', 'analyst'));

INSERT INTO role_permissions(role_id, permission_id)
SELECT roles.id, permissions.id
FROM roles
JOIN permissions ON roles.name = 'admin'
WHERE permissions.name IN (
    'query.execute', 'admin.users', 'admin.roles', 'admin.audit'
)
ON CONFLICT DO NOTHING;

INSERT INTO role_permissions(role_id, permission_id)
SELECT roles.id, permissions.id
FROM roles
JOIN permissions ON roles.name = 'analyst'
WHERE permissions.name = 'query.execute'
ON CONFLICT DO NOTHING;
