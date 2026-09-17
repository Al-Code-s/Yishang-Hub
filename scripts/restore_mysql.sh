#!/usr/bin/env bash
# 意尚智造集成平台 —— MySQL 恢复脚本
#
# ⚠️ 本脚本【未在本轮环境中执行验证】。恢复属于高风险操作，执行前必须：
#   1. 确认目标库与备份文件（本脚本会二次确认）；
#   2. 停止应用与 Worker/Beat，避免恢复期间产生新数据；
#   3. 阅读 docs/backup-restore.md 的完整恢复步骤与一致性核对要求。
#
# 注意：恢复【不会】自动回滚代码侧的迁移；恢复后需按目标版本执行 migrate。
#
# 用法：
#   DB_HOST=... DB_USER=... DB_PASSWORD=*** DB_NAME=yishang_platform \
#   BACKUP_FILE=/srv/backups/mysql/yishang_yishang_platform_20260917T010000Z.sql.gz \
#   CONFIRM_RESTORE=yes ./restore_mysql.sh
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-yishang_platform}"
DB_USER="${DB_USER:-yishang_app}"
DB_PASSWORD="${DB_PASSWORD:?必须通过环境变量提供 DB_PASSWORD}"
BACKUP_FILE="${BACKUP_FILE:?必须指定 BACKUP_FILE}"

if [ "${CONFIRM_RESTORE:-no}" != "yes" ]; then
    echo "拒绝执行：恢复会覆盖目标库 ${DB_NAME} 的数据。" >&2
    echo "确认无误后请设置 CONFIRM_RESTORE=yes 重新执行。" >&2
    exit 2
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "备份文件不存在：${BACKUP_FILE}" >&2
    exit 2
fi

echo "[restore] target=${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "[restore] source=${BACKUP_FILE}"
echo "[restore] 请确认应用与 Worker/Beat 已停止。5 秒后开始 ..."
sleep 5

if [[ "$BACKUP_FILE" == *.gpg ]]; then
    echo "[restore] decrypting ..."
    gpg --batch --yes --decrypt "$BACKUP_FILE" | gunzip | \
        MYSQL_PWD="$DB_PASSWORD" mysql --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
            --default-character-set=utf8mb4 "$DB_NAME"
else
    gunzip -c "$BACKUP_FILE" | \
        MYSQL_PWD="$DB_PASSWORD" mysql --host="$DB_HOST" --port="$DB_PORT" --user="$DB_USER" \
            --default-character-set=utf8mb4 "$DB_NAME"
fi

echo "[restore] done. 后续必须执行："
echo "  1) python manage.py migrate            # 对齐到目标代码版本"
echo "  2) 核对数据库记录与附件对象存储的一致性"
echo "  3) python manage.py reconcile_inventory      # 阶段 2 提供"
echo "  4) python manage.py rebuild_energy_summary   # 阶段 5 提供"
echo "  5) 健康检查 /healthz /readyz 与关键业务抽查"
echo "  6) 记录本次实际 RTO 与数据丢失区间"