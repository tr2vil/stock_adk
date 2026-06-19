#!/usr/bin/env bash
#
# restart.sh — 트레이딩 스택 종료 후 재기동
#
# 사용법: ./scripts/restart.sh
#
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

stop_stack
echo
start_stack
