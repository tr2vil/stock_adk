"""A2A Server for Risk Agent."""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

import os
from dotenv import load_dotenv

load_dotenv()

from starlette.requests import Request
from starlette.responses import JSONResponse

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from shared.middleware import A2ALoggingMiddleware
from shared.redis_client import aget_prompt
from shared.logger import get_logger
from .agent import root_agent

_logger = get_logger("risk_agent.server")

A2A_HOST = os.getenv("A2A_HOST", "localhost")
A2A_PORT = int(os.getenv("RISK_AGENT_PORT", "8005"))
app = to_a2a(root_agent, host=A2A_HOST, port=A2A_PORT)
app.add_middleware(A2ALoggingMiddleware, agent_name="risk_agent")


async def reload_prompt(request: Request) -> JSONResponse:
    """Reload prompt from Redis and apply to agent."""
    new_prompt = await aget_prompt("risk_agent")
    if new_prompt:
        root_agent.instruction = new_prompt
        _logger.info("prompt_reloaded", agent="risk_agent", length=len(new_prompt))
        return JSONResponse({"status": "reloaded", "agent": "risk_agent"})
    return JSONResponse({"status": "no_change", "agent": "risk_agent"})


app.add_route("/reload", reload_prompt, methods=["POST"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
