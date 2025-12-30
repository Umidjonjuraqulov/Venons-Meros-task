from typing import Sequence

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

from src.classes.cls_const import AccessLevelConst

from src.i18n.i18n import translate as _
from src.i18n.locales import LANGUAGE_CHOICES


class RegCallback(CallbackData, prefix="reg"):
    user_id: int
    status: str


class CompleteTaskCallback(CallbackData, prefix="complete_task"):
    task_id: int


def back_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("b.back", language))]],
        resize_keyboard=True
    )

def back_and_cancel_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("b.back", language)), KeyboardButton(text=_("b.cancel", language))]],
        resize_keyboard=True
    )


def choose_language(language: str="ru", back_bt=True) -> ReplyKeyboardMarkup:
    result = ReplyKeyboardBuilder()
    for button in LANGUAGE_CHOICES.keys():
        result.add(KeyboardButton(text=button))

    if back_bt:
        result.add(KeyboardButton(text=_("b.back", language)))

    result.adjust(2)
    return result.as_markup(resize_keyboard=True)


def create_confirm_ikb(user_id: int) -> InlineKeyboardMarkup:
    confirm_ikb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Принять",
                        callback_data=RegCallback(user_id=user_id, status=AccessLevelConst.USER).pack()
                    ),
                    InlineKeyboardButton(
                        text="Заблокировать",
                        callback_data=RegCallback(user_id=user_id, status=AccessLevelConst.BLOCKED).pack()
                    )
                ]
            ]
        )
    return confirm_ikb


def comment_answer_ikb(task_db_id: int, language: str, complete_bt: bool = False) -> InlineKeyboardMarkup:
    buttons = [[
        InlineKeyboardButton(text=_("b.open_task", language), callback_data=f"open_task|{task_db_id}"),
        InlineKeyboardButton(text=_("b.write_comment", language), callback_data=f"answer_comment|{task_db_id}")
    ]]
    if complete_bt:
        buttons.append(
            [InlineKeyboardButton(text=_("b.done_task", language), callback_data=CompleteTaskCallback(task_id=task_db_id).pack())]
        )

    confirm_ikb = InlineKeyboardMarkup(inline_keyboard=buttons)
    return confirm_ikb


def test_answer_ikb(task_db_id: int, language: str) -> InlineKeyboardMarkup:
    confirm_ikb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=_("b.open_task", language), callback_data=f"open_task|{task_db_id}")],
            [InlineKeyboardButton(text=_("b.done_task", language), callback_data=CompleteTaskCallback(task_id=task_db_id).pack())]
        ]
    )
    return confirm_ikb


def build_tasks_rkb(
        p: int, p_lines: int, t_size: int, language: str, s_num: int = 1, c_bt=False, by_stage=False
) -> ReplyKeyboardMarkup:
    """
    :param p: current page number, starting from 1
    :param p_lines: max lines of page
    :param t_size: max tasks size
    :param language: language
    :param s_num: start number of range 0 or 1 (default 1)
    :param c_bt: add closed button (default False)
    :param by_stage: add stages button (default False)
    :return:
    """
    kb = [
        str(i) for i in
        range((p-1) * p_lines + s_num, min(t_size, p_lines * p) + s_num)
    ]

    if 1 < p:
        kb.append(_("b.previous", language))

    if (t_size / p_lines) > p:
        kb.append(_("b.next", language))

    if by_stage:
        kb.append(_("b.by_stage", language))

    if c_bt:
        kb.append(_("b.closed", language))

    return build_rkb(kb, language, adjust=3)


def build_rkb(buttons: Sequence[str], language: str, back: bool = True, adjust: int = 2) -> ReplyKeyboardMarkup:
    result = ReplyKeyboardBuilder()
    for button in buttons:
        result.add(KeyboardButton(text=button))

    if back:
        result.add(KeyboardButton(text=_("b.back", language)))

    result.adjust(adjust)
    return result.as_markup(resize_keyboard=True)


def build_ikb(buttons: dict[str, str] | Sequence[str], adjust: int = 3) -> InlineKeyboardMarkup:
    result = InlineKeyboardBuilder()
    if isinstance(buttons, dict):
        for text, data in buttons.items():
            result.add(InlineKeyboardButton(text=text, callback_data=data))

    else:
        for text in buttons:
            result.add(InlineKeyboardButton(text=text, callback_data=text))

    result.adjust(adjust)
    return result.as_markup()


def back_and_confirm_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("b.back", language)), KeyboardButton(text=_("b.confirm", language))],
            [KeyboardButton(text=_("b.cancel", language))]
        ],
        resize_keyboard=True
    )

def user_main_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("b.my_tasks", language)), KeyboardButton(text=_("b.create_task", language))],
            [KeyboardButton(text=_("b.observed_tasks", language)), KeyboardButton(text=_("b.group_status", language))],
            [KeyboardButton(text=_("b.write_review", language))]
        ],
        resize_keyboard=True
    )

def phone_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=_("b.send_phone", language), request_contact=True)]],
        resize_keyboard=True
    )


def task_info_rkb(language: str, can_delete: bool = False) -> ReplyKeyboardMarkup:
    if can_delete:
        return ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text=_("b.get_files", language)), KeyboardButton(text=_("b.comments", language))],
                [KeyboardButton(text=_("b.change_stage", language)), KeyboardButton(text=_("b.delete_task", language))],
                [KeyboardButton(text=_("b.back", language))]
            ],
            resize_keyboard=True
        )

    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("b.get_files", language)), KeyboardButton(text=_("b.comments", language))],
            [KeyboardButton(text=_("b.change_stage", language)), KeyboardButton(text=_("b.back", language))]
        ],
        resize_keyboard=True
    )


def delete_config_rkb(language: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_("b.delete_confirm", language)), KeyboardButton(text=_("b.back", language))],
        ],
        resize_keyboard=True
    )
