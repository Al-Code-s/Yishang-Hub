#!/usr/bin/env bash
# 意尚智造集成平台 —— MySQL 逻辑备份脚本
#
# ⚠️ 本脚本【未在本轮环境中执行验证】（本机无 Docker、未配置生产库）。
#    首次使用前请在测试库演练一次，确认备份可用、可恢复。
#
# 要求（任务书 16.4）：
#   * 备份加密与访问控制
#   * 明确保留周期
#   * 记录备份状态并纳入监控
#   * 数据库与附件恢复后需核对引用一致性
#
# 用法：
#   DB_HOST=127.0.0.1 DB_USER=yishang_app DB_PASSWORD=*** DB_NAME=yishang_platform \
#   BACKUP_DIR=/srv/backups/mysql ./backup_mysql.sh
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-yishang_platform}"
DB_USER="${DB_USER:-yishang_app}"
DB_PASSWORD="${DB_PASSWORD:?必须通过环境变量提供 DB_PASSWORD，不要在脚本里写死密码}"
BACKUP_DIR="${BACKUP_DIR:-/srv/backups/mysql}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
GPG_RECIPIENT="${GPG_RECIPIENT:-}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
plain="$BACKUP_DIR/yishang_${DB_NAME}_${timestamp}.sql"
archive="${plain}.gz"

echo "[backup] dumping ${DB_NAME} from ${DB_HOST}:${DB_PORT} ..."
MYSQL_PWD="$DB_PASSWORD" mysqldump \
    --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
    --single-transaction --quick --routines --triggers --events \
    --set-gtid-purged=OFF \
    --default-character-set=utf8mb4 \
    "$DB_NAME" > "$plain"

gzip -9 "$plain"
echo "[backup] wrote ${archive} ($(stat -c%s "$archive" 2>/dev/null || echo '?') bytes)"

# 加密：生产环境必须配置 GPG_RECIPIENT
if [ -n "$GPG_RECIPIENT" ]; then
    gpg --batch --yes --encrypt --recipient "$GPG_RECIPIENT" "$archive"
    rm -f "$archive"
    echo "[backup] encrypted -> ${archive}.gpg"
else
    echo "[backup] WARNING: 未配置 GPG_RECIPIENT，备份未加密；生产环境不允许长期保留明文备份" >&2
fi

# 保留周期清理（仅清理本脚本产生的文件）
echo "[backup] pruning backups older than ${RETENTION_DAYS} days ..."
find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name "yishang_${DB_NAME}_*.sql.gz" -o -name "yishang_${DB_NAME}_*.sql.gz.gpg" \) \
    -mtime "+${RETENTION_DAYS}" -print -delete

echo "[backup] done at ${timestamp}"