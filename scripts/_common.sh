#!/usr/bin/env bash
#
# _common.sh — start.sh / stop.sh / restart.sh 공통 함수 모음 (source 전용)
#
# 엔진: Podman Desktop. docker-compose는 macOS 키체인(credsStore) 충돌이 있어
#       podman-compose를 사용한다. (memory: podman-compose-startup)
#
set -euo pipefail

# ── 환경 ──
export PATH="/opt/podman/bin:/opt/homebrew/bin:$PATH"

# 프로젝트 루트 = scripts/ 의 상위 디렉터리
_COMMON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$_COMMON_DIR")"
cd "$PROJECT_ROOT"

HEALTH_URL="http://localhost:8000/api/health"
FRONTEND_URL="http://localhost:5173"

# ── 유틸 ──
log() { printf '\033[1;36m[trading]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[trading] ERROR:\033[0m %s\n' "$*" >&2; }

require_tools() {
    command -v podman >/dev/null 2>&1 || { err "podman 미설치 (Podman Desktop 확인)"; exit 1; }
    command -v podman-compose >/dev/null 2>&1 || { err "podman-compose 미설치 → brew install podman-compose"; exit 1; }
}

ensure_machine() {
    if ! podman machine inspect --format '{{.State}}' 2>/dev/null | grep -q running; then
        log "podman 머신이 꺼져 있어 기동합니다..."
        podman machine start
    fi
}

wait_health() {
    log "orchestrator 헬스 대기 중... ($HEALTH_URL)"
    for _ in $(seq 1 30); do
        if [ "$(curl -s -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null)" = "200" ]; then
            log "✅ orchestrator healthy"
            return 0
        fi
        sleep 2
    done
    err "헬스 체크 타임아웃 (60s). 'podman ps' / logs 로 확인하세요."
    return 1
}

# ── 동작 ──
start_stack() {
    require_tools
    ensure_machine
    log "빌드 + 기동 (podman-compose up -d --build)..."
    podman-compose up -d --build
    wait_health || true
    echo
    log "Frontend : $FRONTEND_URL  (override: http://localhost:15173)"
    log "API      : $HEALTH_URL"
    log "Grafana  : http://localhost:3001"
}

stop_stack() {
    require_tools
    log "종료 (podman-compose down)..."
    podman-compose down || true
    # down 경합으로 남는 컨테이너 방어적 정리
    if [ "$(podman ps -q | wc -l | tr -d ' ')" != "0" ]; then
        log "잔여 컨테이너 정리..."
        podman stop -a >/dev/null 2>&1 || true
        podman-compose down >/dev/null 2>&1 || true
    fi
    log "✅ 종료 완료 (Redis 볼륨 데이터는 보존됨)"
}
