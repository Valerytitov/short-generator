# youtube_client.py (версия для "ручной" авторизации)
import os
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

CLIENT_SECRETS_FILE = '/data/client_secrets.json'
TOKEN_PICKLE_FILE = '/data/token.pickle'
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

class YouTubeClient:
    def __init__(self):
        self.creds = self._load_credentials()
        self.youtube_service = self._build_service()
        self.flow = None # Для хранения состояния между шагами авторизации

    def _load_credentials(self):
        creds = None
        if os.path.exists(TOKEN_PICKLE_FILE):
            with open(TOKEN_PICKLE_FILE, 'rb') as token:
                creds = pickle.load(token)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    def _build_service(self):
        if self.creds and self.creds.valid:
            return build('youtube', 'v3', credentials=self.creds)
        return None

    def initiate_authorization(self):
        """Начинает процесс ручной авторизации и возвращает URL."""
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
        self.flow = flow # Сохраняем flow для следующего шага
        auth_url, _ = self.flow.authorization_url(prompt='consent')
        return auth_url

    def complete_authorization(self, pasted_url: str):
        """Завершает авторизацию, используя URL от пользователя."""
        if not self.flow:
            return False
        try:
            # Указываем localhost, так как это Desktop App Flow
            self.flow.redirect_uri = "http://localhost"
            self.flow.fetch_token(authorization_response=pasted_url)
            self.creds = self.flow.credentials
            with open(TOKEN_PICKLE_FILE, 'wb') as token:
                pickle.dump(self.creds, token)
            self.youtube_service = self._build_service()
            return True
        except Exception as e:
            print(f"Ошибка при завершении авторизации: {e}")
            return False

    def is_authorized(self):
        return self.creds and self.creds.valid

    def upload_video(self, file_path, title, description, tags, privacy_status="public"):
        if not self.is_authorized() or not self.youtube_service:
            raise Exception("Клиент YouTube не авторизован.")

        body = {
            'snippet': { 'title': title, 'description': description, 'tags': tags, 'categoryId': '22' },
            'status': { 'privacyStatus': privacy_status }
        }
        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = self.youtube_service.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Загружено {int(status.progress() * 100)}%")

        return response