#!/bin/sh
# 后端容器入口脚本。
# 注意：这里【不自动执行 migrate】——迁移由 compose 中的一次性 migrate 服务完成，
# 避免多个 Web 实例并发执行迁移。
set -e

if [ "${WAIT_FOR_DB:-true}" = "true" ]; then
    echo "[entrypoint] waiting for database ${DB_HOST:-mysql}:${DB_PORT:-3306} ..."
    i=0
    until python - <<'PY'
import os, socket, sys
host = os.environ.get("DB_HOST", "mysql")
port = int(os.environ.get("DB_PORT", "3306"))
s = socket.socket()
s.settimeout(2)
try:
    s.connect((host, port))
except Exception:
    sys.exit(1)
finally:
    s.close()
PY
    do
        i=$((i + 1))
        if [ "$i" -ge "${WAIT_FOR_DB_RETRIES:-60}" ]; then
            echo "[entrypoint] database not reachable after ${i} attempts" >&2
            exit 1
        fi
        sleep 2
    done
    echo "[entrypoint] database is reachable"
fi

exec "$@"