"""A2A Server for Technical Agent."""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="google.adk")

import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from shared.middleware import A2ALoggingMiddleware
from .agent import root_agent

A2A_HOST = os.getenv("A2A_HOST", "localhost")
A2A_PORT = int(os.getenv("TECHNICAL_AGENT_PORT", "8003"))
app = to_a2a(root_agent, host=A2A_HOST, port=A2A_PORT)
app.add_middleware(A2ALoggingMiddleware, agent_name="technical_agent")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
