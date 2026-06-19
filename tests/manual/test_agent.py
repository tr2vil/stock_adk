"""간단한 에이전트 테스트 스크립트"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

import requests
import sys
import json


def test_agent(port: int, message: str, debug: bool = False):
    """A2A 에이전트에 메시지를 보내고 응답을 출력합니다."""
    url = f"http://localhost:{port}/"

    payload = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "message/send",
        "params": {
            "message": {
                "messageId": "m1",
                "role": "user",
                "parts": [{"kind": "text", "text": message}]
            }
        }
    }

    print(f"📡 Sending to port {port}: {message}")
    print("-" * 50)

    try:
        response = requests.post(url, json=payload, timeout=120)
        result = response.json()

        # 디버그 모드: 전체 응답 출력
        if debug:
            print("📦 Raw Response:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("-" * 50)

        if "result" in result:
            res = result["result"]

            # 방법 1: messages에서 텍스트 추출
            messages = res.get("messages", [])
            text_found = False
            for msg in messages:
                for part in msg.get("parts", []):
                    if part.get("kind") == "text":
                        print(part.get("text", ""))
                        text_found = True

            # 방법 2: artifacts에서 텍스트 추출 (A2A SDK 일부 버전)
            artifacts = res.get("artifacts", [])
            for artifact in artifacts:
                for part in artifact.get("parts", []):
                    if part.get("kind") == "text":
                        print(part.get("text", ""))
                        text_found = True

            # 방법 3: 직접 result에 text가 있는 경우
            if not text_found and "text" in res:
                print(res["text"])
                text_found = True

            if not text_found and not debug:
                print("⚠️ 텍스트 응답이 없습니다. --debug 옵션으로 전체 응답을 확인하세요.")

        elif "error" in result:
            print(f"❌ Error: {result['error']}")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False))

    except requests.exceptions.ConnectionError:
        print(f"❌ 연결 실패: localhost:{port}에 에이전트가 실행 중인지 확인하세요.")
    except Exception as e:
        print(f"❌ 오류: {e}")


if __name__ == "__main__":
    # 기본값
    port = 8003  # technical agent
    message = "Analyze technical indicators for AAPL"
    debug = False

    # 커맨드라인 인수 처리
    args = sys.argv[1:]

    # --debug 플래그 확인
    if "--debug" in args:
        debug = True
        args.remove("--debug")

    if len(args) >= 1:
        port = int(args[0])
    if len(args) >= 2:
        message = " ".join(args[1:])

    test_agent(port, message, debug)
