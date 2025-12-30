from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
import datetime
import hashlib
import hmac
import uuid


class AdminAuth(AuthenticationBackend):
    def __init__(self, admin_user, admin_password, session_lifetime_days=7, secret_key="your_secret_key"):
        super().__init__(secret_key)
        self.secret_key = secret_key
        self.admin_user = admin_user
        self.admin_password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
        self.session_lifetime_days = datetime.timedelta(days=session_lifetime_days)

    def generate_token(self, session_id):
        # Создание токена с использованием HMAC и секретного ключа
        token_string = f"{session_id}{self.secret_key}"
        token = hmac.new(self.secret_key.encode(), token_string.encode(), hashlib.sha256).hexdigest()
        return token

    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form["username"], form["password"]

        # Проверка имени пользователя и пароля
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        if username == self.admin_user and password_hash == self.admin_password_hash:
            session_id = str(uuid.uuid4())
            token = self.generate_token(session_id)
            expires_at = (datetime.datetime.utcnow() + self.session_lifetime_days).timestamp()
            # Обновление сессии
            request.session.update({
                "session_id": session_id,
                "token": token,
                "expires_at": expires_at
            })
            return True
        return False

    async def logout(self, request: Request) -> bool:
        # Очистка сессии
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        session_id = request.session.get("session_id")
        token = request.session.get("token")
        expires_at = request.session.get("expires_at")

        # Проверка наличия токена и срока действия
        if not session_id or not token or not expires_at:
            return False

        # Проверка срока действия токена
        if datetime.datetime.utcnow().timestamp() > expires_at:
            return False

        # Проверка подлинности токена
        valid_token = self.generate_token(session_id)
        if not hmac.compare_digest(token, valid_token):
            return False

        return True
