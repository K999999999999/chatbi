FROM postgres:16-alpine@sha256:57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777
ARG CHATBI_SOURCE_COMMIT
RUN printf '%s' "$CHATBI_SOURCE_COMMIT" | grep -Eq '^[0-9a-f]{40}$' && apk add --no-cache python3 ca-certificates
# age release bytes are verified before either executable is installed.
RUN python3 - <<'PY'
import hashlib, io, tarfile, urllib.request
url = 'https://github.com/FiloSottile/age/releases/download/v1.3.2/age-v1.3.2-linux-amd64.tar.gz'
with urllib.request.urlopen(url, timeout=60) as response:
    data = response.read(32 * 1024**2)
assert hashlib.sha256(data).hexdigest() == 'cbe24006683f8eb669266162894b9a522a1af52f2665fbc63a4bb032ed26ac10'
with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
    for name in ('age', 'age-keygen'):
        member = archive.getmember('age/' + name)
        assert member.isfile()
        with archive.extractfile(member) as source, open('/usr/local/bin/' + name, 'xb') as target:
            target.write(source.read())
        import os
        os.chmod('/usr/local/bin/' + name, 0o755)
PY
RUN test "$(age --version)" = 'v1.3.2' && pg_dump --version | grep -q 'PostgreSQL) 16\.'
LABEL org.opencontainers.image.revision=$CHATBI_SOURCE_COMMIT
WORKDIR /workspace
COPY scripts/__init__.py scripts/local_backup*.py ./scripts/
USER 1000:1000
ENTRYPOINT ["python3", "-m", "scripts.local_backup"]
