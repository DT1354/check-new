#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 运行此脚本" >&2
  exit 1
fi

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_ROOT="/opt/check-new"
SERVICE_USER="check-new"

apt-get update
apt-get install -y python3 python3-venv python3-pip rsync xvfb ca-certificates curl sqlite3

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --home-dir "${APP_ROOT}" --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" -m 0750 "${APP_ROOT}/app"
install -d -o "${SERVICE_USER}" -g "${SERVICE_USER}" -m 0700 /var/lib/check-new
install -d -o root -g "${SERVICE_USER}" -m 0750 /etc/check-new

rsync -a \
  --exclude '.git' --exclude '.venv' --exclude '.env' \
  --exclude 'frontend/node_modules' --exclude 'frontend/dist' \
  "${SOURCE_DIR}/" "${APP_ROOT}/app/"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_ROOT}/app"

python3 -m venv "${APP_ROOT}/venv"
"${APP_ROOT}/venv/bin/pip" install --upgrade pip
"${APP_ROOT}/venv/bin/pip" install -r "${APP_ROOT}/app/requirements.txt"

if [[ ! -f /etc/check-new/check-new.env ]]; then
  install -o root -g "${SERVICE_USER}" -m 0640 \
    "${APP_ROOT}/app/deploy/check-new.env.example" /etc/check-new/check-new.env
  echo "已创建 /etc/check-new/check-new.env，请先修改域名和 CHROME_PATH。"
fi

if [[ ! -f /etc/check-new/app_master_key ]]; then
  (
    cd "${APP_ROOT}/app"
    "${APP_ROOT}/venv/bin/python" -m server.cli generate-key
  ) > /etc/check-new/app_master_key
  chown root:"${SERVICE_USER}" /etc/check-new/app_master_key
  chmod 0640 /etc/check-new/app_master_key
fi

install -o root -g root -m 0644 "${APP_ROOT}/app/deploy/systemd/"* /etc/systemd/system/
systemctl daemon-reload

echo
echo "代码和服务文件已安装。下一步："
echo "1. 安装 Google Chrome 或 Chromium，并修改 /etc/check-new/check-new.env 的 CHROME_PATH。"
echo "2. 按 README 创建管理员。"
echo "3. 启用服务：systemctl enable --now check-new-api check-new-worker check-new-scheduler.timer"
