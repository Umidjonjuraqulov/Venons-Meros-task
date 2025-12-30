from datetime import datetime, timedelta
from typing import Dict, Any, Awaitable, Callable

from aiogram import BaseMiddleware, types

from src.i18n.locales import ANTISPAM_MESSAGE

def inline_results() -> list[types.InlineQueryResultArticle]:
    return [
        types.InlineQueryResultArticle(
            id="antispam",
            title="————————————————",
            description=ANTISPAM_MESSAGE,
            input_message_content=types.InputTextMessageContent(message_text=ANTISPAM_MESSAGE),
        )
    ]

class AntispamMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 9, interval: int = 3):
        self.limit = limit
        self.interval = interval
        self.user_timestamps: Dict[int, list[datetime]] = {}

    async def __call__(
            self,
            handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: types.update.Update,
            data: Dict[str, Any],
    ) -> Any:
        user_id = event.event.from_user.id
        now = datetime.now()

        self.user_timestamps.setdefault(user_id, [])
        self.user_timestamps[user_id].append(now)  # Add current timestamp
        self.user_timestamps[user_id] = [
            ts for ts in self.user_timestamps[user_id] if ts > now - timedelta(seconds=self.interval)
        ]

        # Check message count within the interval
        len_messages = len(self.user_timestamps[user_id])
        if len_messages >= self.limit:
            if len_messages == self.limit:
                update_event = event.event
                if isinstance(update_event, (types.Message, types.CallbackQuery)):
                    await update_event.answer(ANTISPAM_MESSAGE)

                elif isinstance(update_event, types.InlineQuery):
                    await update_event.answer(inline_results(), cache_time=5)
            return None

        # Pass control to the next handler
        return await handler(event, data)
