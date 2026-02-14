"""
Orchestrator Tools - 병렬 Sub-Agent 호출 도구
5개 전문 에이전트를 동시에 호출하여 종합 분석 데이터를 수집합니다.
"""
import asyncio
import json
import os
import uuid

import httpx

from shared.logger import get_logger

logger = get_logger("orchestrator.tools")

# Per-agent call timeout (seconds)
AGENT_CALL_TIMEOUT = float(os.getenv("AGENT_CALL_TIMEOUT", "90"))

# Max response text length per agent (to keep total under 15KB)
MAX_RESPONSE_LENGTH = 3000

AGENT_CONFIG = [
    {
        "name": "news_agent",
        "host_env": "NEWS_AGENT_HOST",
        "port_env": "NEWS_AGENT_PORT",
        "default_host": "localhost",
        "default_port": "8001",
        "message_template": "다음 종목의 뉴스와 시황을 분석해주세요: {ticker} ({market})",
    },
    {
        "name": "fundamental_agent",
        "host_env": "FUNDAMENTAL_AGENT_HOST",
        "port_env": "FUNDAMENTAL_AGENT_PORT",
        "default_host": "localhost",
        "default_port": "8002",
        "message_template": "다음 종목의 재무제표를 분석해주세요: {ticker} ({market})",
    },
    {
        "name": "technical_agent",
        "host_env": "TECHNICAL_AGENT_HOST",
        "port_env": "TECHNICAL_AGENT_PORT",
        "default_host": "localhost",
        "default_port": "8003",
        "message_template": "다음 종목의 기술적 분석을 해주세요: {ticker} ({market})",
    },
    {
        "name": "expert_agent",
        "host_env": "EXPERT_AGENT_HOST",
        "port_env": "EXPERT_AGENT_PORT",
        "default_host": "localhost",
        "default_port": "8004",
        "message_template": "다음 종목의 전문가 신호를 수집해주세요: {ticker} ({market})",
    },
    {
        "name": "risk_agent",
        "host_env": "RISK_AGENT_HOST",
        "port_env": "RISK_AGENT_PORT",
        "default_host": "localhost",
        "default_port": "8005",
        "message_template": "현재 계좌 상태를 고려하여 리스크를 평가해주세요: {ticker} ({market})",
    },
]


def _build_a2a_request(message: str) -> dict:
    """A2A JSON-RPC 2.0 요청 페이로드를 생성합니다."""
    req_id = uuid.uuid4().hex[:8]
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": f"m-{req_id}",
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
            }
        },
    }


def _extract_response_text(response_json: dict) -> str:
    """A2A JSON-RPC 응답에서 에이전트 분석 결과 텍스트를 추출합니다."""
    result = response_json.get("result", {})

    # Path 1: result.artifacts[].parts[].text
    artifacts = result.get("artifacts", [])
    if artifacts:
        parts = artifacts[0].get("parts", [])
        if parts:
            text = parts[0].get("text", "")
            if text:
                return text

    # Path 2: result.status.message.parts[].text
    status_msg = result.get("status", {}).get("message", {})
    if isinstance(status_msg, dict):
        parts = status_msg.get("parts", [])
        if parts:
            return parts[0].get("text", "")

    return ""


async def _call_single_agent(
    client: httpx.AsyncClient,
    agent_name: str,
    url: str,
    message: str,
) -> dict:
    """단일 sub-agent에게 A2A JSON-RPC 요청을 보냅니다."""
    logger.info("agent_call_start", agent=agent_name, url=url)
    try:
        payload = _build_a2a_request(message)
        response = await client.post(url, json=payload, timeout=AGENT_CALL_TIMEOUT)
        response.raise_for_status()
        resp_json = response.json()

        if "error" in resp_json:
            error_msg = str(resp_json["error"])
            logger.warning("agent_rpc_error", agent=agent_name, error=error_msg)
            return {"status": "error", "agent": agent_name, "error": error_msg}

        text = _extract_response_text(resp_json)
        if not text:
            logger.warning("agent_empty_response", agent=agent_name)
            return {"status": "error", "agent": agent_name, "error": "Empty response"}

        if len(text) > MAX_RESPONSE_LENGTH:
            text = text[:MAX_RESPONSE_LENGTH] + "\n... (truncated)"

        logger.info("agent_call_success", agent=agent_name, response_length=len(text))
        return {"status": "success", "agent": agent_name, "analysis": text}

    except httpx.TimeoutException:
        logger.error("agent_call_timeout", agent=agent_name, timeout=AGENT_CALL_TIMEOUT)
        return {
            "status": "error",
            "agent": agent_name,
            "error": f"Timeout after {AGENT_CALL_TIMEOUT}s",
        }
    except httpx.ConnectError:
        logger.error("agent_call_connect_error", agent=agent_name, url=url)
        return {
            "status": "error",
            "agent": agent_name,
            "error": f"Connection refused: {url}",
        }
    except Exception as e:
        logger.error("agent_call_error", agent=agent_name, error=str(e))
        return {"status": "error", "agent": agent_name, "error": str(e)}


async def analyze_all_agents(ticker: str, market: str) -> dict:
    """5개 전문 에이전트를 동시에 호출하여 종합 분석 데이터를 수집합니다.

    모든 sub-agent (news, fundamental, technical, expert, risk)에게
    동시에 A2A 요청을 보내고 결과를 수집합니다.

    Args:
        ticker: 종목코드 (예: AAPL, 005930, 삼성전자)
        market: 시장 구분 (US 또는 KR)

    Returns:
        dict: 각 에이전트의 분석 결과를 포함하는 딕셔너리
    """
    logger.info("parallel_analysis_start", ticker=ticker, market=market)

    async with httpx.AsyncClient() as client:
        tasks = []
        for cfg in AGENT_CONFIG:
            host = os.getenv(cfg["host_env"], cfg["default_host"])
            port = os.getenv(cfg["port_env"], cfg["default_port"])
            url = f"http://{host}:{port}/"
            message = cfg["message_template"].format(ticker=ticker, market=market)
            tasks.append(_call_single_agent(client, cfg["name"], url, message))

        results = await asyncio.gather(*tasks, return_exceptions=True)

    agent_results = {}
    success_count = 0
    for i, result in enumerate(results):
        agent_name = AGENT_CONFIG[i]["name"]
        if isinstance(result, Exception):
            agent_results[agent_name] = {
                "status": "error",
                "agent": agent_name,
                "error": str(result),
            }
        else:
            agent_results[agent_name] = result
            if result.get("status") == "success":
                success_count += 1

    logger.info(
        "parallel_analysis_complete",
        ticker=ticker,
        market=market,
        success_count=success_count,
        total_count=len(AGENT_CONFIG),
    )

    return {
        "ticker": ticker,
        "market": market,
        "success_count": success_count,
        "total_count": len(AGENT_CONFIG),
        "agents": agent_results,
    }
