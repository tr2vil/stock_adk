import os
import json
import vertexai
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()

def init_vertex_ai():
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    service_account_json = os.getenv("GOOGLE_KEY")

    if service_account_json:
        try:
            # Handle both file path and JSON string
            if service_account_json.startswith('{'):
                credentials_info = json.loads(service_account_json)
                credentials = service_account.Credentials.from_service_account_info(credentials_info)
            else:
                credentials = service_account.Credentials.from_service_account_file(service_account_json)

            vertexai.init(project=project_id, location=location, credentials=credentials)
            return True
        except Exception as e:
            print(f"Error initializing Vertex AI with service account: {e}")
            return False
    else:
        # Fallback to default credentials
        vertexai.init(project=project_id, location=location)
        return True
