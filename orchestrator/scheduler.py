"""
Scheduler - APScheduler 기반 정기 분석 스케줄러
주기적으로 관심 종목을 분석하고 알림을 전송
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler()

# 워처 잡 ID (수동 토글로 add/remove)
WATCHER_JOB_ID = "swing_price_watcher"
WATCHER_INTERVAL_MIN = 5  # 장중 5분 폴링


async def analyze_watchlist():
    """관심 종목 리스트를 분석합니다.

    TODO: 실제 구현 시 아래 내용 추가
    1. 데이터베이스에서 관심 종목 리스트 조회
    2. 각 종목에 대해 orchestrator 분석 실행
    3. 결과를 저장하고 필요시 알림 전송
    """
    logger.info("Scheduled watchlist analysis started")
    # Placeholder for actual implementation
    pass


async def check_market_open():
    """시장 개장 여부를 확인합니다.

    한국: 09:00 - 15:30 KST
    미국: 09:30 - 16:00 EST (한국시간 23:30 - 06:00)
    """
    # TODO: 실제 시장 개장 시간 체크 로직 구현
    return True


def setup_scheduler():
    """스케줄러를 설정하고 작업을 등록합니다."""

    # 한국 시장 분석 (월-금 09:00, 14:00 KST)
    scheduler.add_job(
        analyze_watchlist,
        CronTrigger(day_of_week="mon-fri", hour="9,14", minute=0, timezone="Asia/Seoul"),
        id="kr_market_analysis",
        name="Korean Market Watchlist Analysis",
        replace_existing=True,
    )

    # 미국 시장 분석 (월-금 09:30 EST = 23:30 KST)
    scheduler.add_job(
        analyze_watchlist,
        CronTrigger(day_of_week="tue-sat", hour=23, minute=30, timezone="Asia/Seoul"),
        id="us_market_analysis",
        name="US Market Watchlist Analysis",
        replace_existing=True,
    )

    # 자가진화 분석 (월-금 16:00 KST, 장 마감 후) — 설계서 5.2
    scheduler.add_job(
        _evolution_job,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=0, timezone="Asia/Seoul"),
        id="daily_evolution",
        name="Daily Strategy Evolution (16:00 KST)",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler jobs configured")


async def _evolution_job():
    """장 마감 후 자가진화 분석 트리거. 제안은 HiL 승인 대기로 들어간다."""
    from orchestrator.evolution_runner import run_evolution_analysis
    try:
        result = await run_evolution_analysis(lookback_days=30, trigger="daily_schedule")
        logger.info(f"Evolution job done: {result.get('status')}")
    except Exception as e:  # 잡 예외가 스케줄러를 죽이지 않도록
        logger.error(f"Evolution job failed: {e}")


def start_scheduler():
    """스케줄러를 시작합니다."""
    if not scheduler.running:
        setup_scheduler()
        scheduler.start()
        logger.info("Scheduler started")


# ── 스윙 가격 워처 (수동 토글) ──

async def _watcher_job():
    """APScheduler가 5분마다 호출하는 워처 잡 래퍼."""
    from execution.watcher import run_watcher_tick
    try:
        await run_watcher_tick()
    except Exception as e:  # 잡 예외가 스케줄러를 죽이지 않도록
        logger.error(f"Watcher tick failed: {e}")


def start_watcher() -> dict:
    """워처 인터벌 잡 등록(수동 시작). 스케줄러가 꺼져 있으면 함께 기동."""
    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started (for watcher)")
    scheduler.add_job(
        _watcher_job,
        IntervalTrigger(minutes=WATCHER_INTERVAL_MIN),
        id=WATCHER_JOB_ID,
        name="Swing Price Watcher (5min)",
        replace_existing=True,
        max_instances=1,         # tick 겹침 방지
        coalesce=True,
        next_run_time=datetime.now(),  # 등록 즉시 1회 실행
    )
    logger.info("Watcher job started")
    return _watcher_job_info()


def stop_watcher() -> dict:
    """워처 인터벌 잡 제거(수동 중지)."""
    if scheduler.get_job(WATCHER_JOB_ID):
        scheduler.remove_job(WATCHER_JOB_ID)
        logger.info("Watcher job stopped")
    return {"running": False, "next_run": None}


def _watcher_job_info() -> dict:
    """워처 잡 등록 여부/다음 실행 시각."""
    job = scheduler.get_job(WATCHER_JOB_ID) if scheduler.running else None
    return {
        "running": job is not None,
        "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
    }


def get_watcher_job_info() -> dict:
    return _watcher_job_info()


def stop_scheduler():
    """스케줄러를 중지합니다."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Scheduler stopped")
