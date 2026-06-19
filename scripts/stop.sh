#!/usr/bin/env bash
#
# stop.sh — 트레이딩 스택 종료 (Redis 볼륨 데이터는 보존)
#
# 사용법: ./scripts/stop.sh
#
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

stop_stack
