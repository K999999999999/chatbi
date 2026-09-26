-- Roles for the local Sales Mart and Control DB, created only on an empty dev volume.
CREATE ROLE :"app_user" LOGIN PASSWORD :'app_password';
CREATE ROLE :"control_app_user" LOGIN PASSWORD :'control_app_password';

REVOKE CONNECT ON DATABASE :"business_db" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"business_db" TO :"app_user";
REVOKE CONNECT ON DATABASE postgres FROM PUBLIC;
REVOKE CONNECT ON DATABASE template1 FROM PUBLIC;
