from typing import Dict, Any, Awaitable, Callable

from aiogram import BaseMiddleware, types
from aiogram.fsm.context import FSMContext

from src.bot.util.templates import to_registration
from src.bot.structures.fsm import Registration
from src.bot.util.user_manager import UsersManager

from src.i18n.i18n import translate as _
from src.i18n.locales import BLOCKED_MESSAGES, TO_REGISTRATION, START_MESSAGE

from src.classes.cls_const import AccessLevelConst

def inline_results(language: str) -> list[types.InlineQueryResultArticle]:
    return [
        types.InlineQueryResultArticle(
            id="blocked",
            title="blocked",
            input_message_content=types.InputTextMessageContent(message_text=_("reg.blocked", language)),
        )
    ]

class AccessMiddleware(BaseMiddleware):
    def __init__(self, user_manager: UsersManager):
        self.user_manager = user_manager

    async def __call__(
            self,
            handler: Callable[[types.TelegramObject, Dict[str, Any]], Awaitable[Any]],
            event: types.update.Update,
            data: Dict[str, Any],
    ) -> Any:
        update_event = event.event
        user_id = event.event.from_user.id
        user_info = await self.user_manager.get_bot_user(user_id)
        if user_info:
            user_access = user_info[0]
            language = user_info[1]
        else:
            user_access = None
            language = None

        if user_access == AccessLevelConst.BLOCKED:
            if isinstance(update_event, (types.Message, types.CallbackQuery)):
                await update_event.answer(_("reg.blocked", BLOCKED_MESSAGES))

            elif isinstance(update_event, types.InlineQuery):
                await update_event.answer(inline_results(BLOCKED_MESSAGES), cache_time=5)

            return None

        if not user_access or not  language:
            if data.get("state"):
                state: FSMContext = data["state"]
                if not (await state.get_state() in Registration.__all_states__):
                    if isinstance(update_event, types.CallbackQuery):
                        await update_event.answer(START_MESSAGE if user_access else TO_REGISTRATION)

                    elif isinstance(update_event, types.InlineQuery):
                        await update_event.answer(
                            inline_results(START_MESSAGE if user_access else TO_REGISTRATION), cache_time=5
                        )

                    await to_registration(event.event.from_user.id, state)
                    return None

        # Pass control to the next handler
        data["language"] = language
        data["access"] = user_access
        return await handler(event, data)
