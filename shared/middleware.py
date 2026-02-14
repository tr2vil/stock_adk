"""
ASGI Middleware for logging A2A JSON-RPC request/response payloads.
Designed to wrap the Starlette app returned by google.adk's to_a2a().
"""
import json
import time

from starlette.types import ASGIApp, Receive, Scope, Send

from shared.logger import get_logger

logger = get_logger("a2a.middleware")

# A2A response text 최대 로깅 길이
_MAX_RESPONSE_PREVIEW = 2000


class A2ALoggingMiddleware:
    """A2A JSON-RPC 요청/응답을 로깅하는 ASGI 미들웨어.

    - message/send: 요청 텍스트 + 응답 텍스트 + 소요시간 전체 로깅
    - message/stream: 요청 텍스트 + 스트림 완료 마커만 로깅 (버퍼링 안 함)
    """

    def __init__(self, app: ASGIApp, agent_name: str = "unknown") -> None:
        self.app = app
        self.agent_name = agent_name

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # POST 요청만 인터셉트 (A2A JSON-RPC 엔드포인트)
        method = scope.get("method", "")
        path = scope.get("path", "")
        if method != "POST" or path not in ("/", "", "/adk/", "/adk"):
            await self.app(scope, receive, send)
            return

        start_time = time.monotonic()

        # 요청 body 읽기 및 캐싱
        request_body = await self._read_body(receive)
        req_data = self._safe_json_parse(request_body)

        rpc_method = req_data.get("method", "unknown")
        request_id = req_data.get("id")
        message_text = self._extract_message_text(req_data)

        logger.info(
            "a2a_request",
            agent=self.agent_name,
            method=rpc_method,
            message_preview=message_text[:200] if message_text else "",
            request_id=request_id,
        )

        # body를 다시 replay할 수 있도록 receive 래핑
        body_sent = False

        async def receive_wrapper() -> dict:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {
                    "type": "http.request",
                    "body": request_body,
                    "more_body": False,
                }
            return await receive()

        # message/send (non-streaming): 응답 body 캡처
        if rpc_method == "message/send":
            response_parts: list[bytes] = []
            response_status = 200

            async def send_wrapper(message: dict) -> None:
                nonlocal response_status
                if message["type"] == "http.response.start":
                    response_status = message.get("status", 200)
                elif message["type"] == "http.response.body":
                    body = message.get("body", b"")
                    if body:
                        response_parts.append(body)
                await send(message)

            await self.app(scope, receive_wrapper, send_wrapper)

            duration_ms = (time.monotonic() - start_time) * 1000
            full_body = b"".join(response_parts)
            response_text = self._extract_response_text(full_body)

            logger.info(
                "a2a_response",
                agent=self.agent_name,
                method=rpc_method,
                status=response_status,
                duration_ms=round(duration_ms, 1),
                response_length=len(full_body),
                response_preview=response_text[:_MAX_RESPONSE_PREVIEW]
                if response_text
                else "",
                request_id=request_id,
            )
        else:
            # message/stream (SSE): 버퍼링 없이 패스스루
            await self.app(scope, receive_wrapper, send)
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.info(
                "a2a_stream_complete",
                agent=self.agent_name,
                method=rpc_method,
                duration_ms=round(duration_ms, 1),
                request_id=request_id,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _read_body(receive: Receive) -> bytes:
        """ASGI receive에서 전체 body를 읽어 반환."""
        chunks: list[bytes] = []
        while True:
            message = await receive()
            body = message.get("body", b"")
            if body:
                chunks.append(body)
            if not message.get("more_body", False):
                break
        return b"".join(chunks)

    @staticmethod
    def _safe_json_parse(data: bytes) -> dict:
        try:
            return json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    @staticmethod
    def _extract_message_text(req_data: dict) -> str:
        """JSON-RPC 요청에서 사용자 메시지 텍스트를 추출."""
        try:
            parts = req_data.get("params", {}).get("message", {}).get("parts", [])
            return parts[0].get("text", "") if parts else ""
        except (KeyError, IndexError, AttributeError):
            return ""

    @staticmethod
    def _extract_response_text(body: bytes) -> str:
        """JSON-RPC 응답에서 에이전트 분석 결과 텍스트를 추출."""
        try:
            resp_data = json.loads(body)
            result = resp_data.get("result", {})

            # A2A: result.artifacts[].parts[].text
            artifacts = result.get("artifacts", [])
            if artifacts:
                parts = artifacts[0].get("parts", [])
                if parts:
                    text = parts[0].get("text", "")
                    if text:
                        return text

            # Fallback: result.status.message.parts[].text
            status_msg = result.get("status", {}).get("message", {})
            if isinstance(status_msg, dict):
                parts = status_msg.get("parts", [])
                if parts:
                    return parts[0].get("text", "")

            return ""
        except (json.JSONDecodeError, KeyError, IndexError, AttributeError):
            return body[:500].decode("utf-8", errors="replace") if body else ""
