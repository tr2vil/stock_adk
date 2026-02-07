"""A2A Server for Expert Agent."""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from .agent import root_agent

A2A_PORT = int(os.getenv("EXPERT_AGENT_PORT", "8004"))
app = to_a2a(root_agent, port=A2A_PORT)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
