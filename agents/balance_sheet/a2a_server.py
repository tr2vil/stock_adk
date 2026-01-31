"""
A2A Server - Balance Sheet Agent

사용법:
    python -m agents.balance_sheet.a2a_server
    또는
    uvicorn agents.balance_sheet.a2a_server:app --host 0.0.0.0 --port 8002
"""
import os
from dotenv import load_dotenv

load_dotenv()

from google.adk.a2a.utils.agent_to_a2a import to_a2a

from .agent import root_agent

A2A_PORT = int(os.getenv("BALANCE_SHEET_AGENT_A2A_PORT", "8002"))

app = to_a2a(root_agent, port=A2A_PORT)

if __name__ == "__main__":
    import uvicorn

    print(f"Starting Balance Sheet A2A Server on port {A2A_PORT}")
    print(f"Agent Card: http://localhost:{A2A_PORT}/.well-known/agent.json")
    uvicorn.run(app, host="0.0.0.0", port=A2A_PORT)
