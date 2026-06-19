#!/usr/bin/env bash
#
# start.sh — 트레이딩 스택 빌드 + 백그라운드 기동 + 헬스 대기
#
# 사용법: ./scripts/start.sh
#
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

start_stack
