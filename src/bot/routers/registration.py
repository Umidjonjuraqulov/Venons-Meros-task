import re

from aiogram import Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardRemove

from src.configuration import conf

from src.bot.structures.fsm import Registration
from src.classes.cls_const import AccessLevelConst
from src.bot.util.templates import to_user_main_menu
from src.bot.structures.keyboards import phone_rkb, create_confirm_ikb

from src.i18n.locales import LANGUAGE_CHOICES
from src.i18n.i18n import translator, translate as _

from src.db.models import User as UserModel


registration_router = Router(name="registration")

REG_STATUS_WAIT = "🕐 Ожидает доступа"
REG_NOTIFY_ANS = """🆕 Создан новый пользователь Bitrix bot
👤 ФИО: {name}
💼 Должность: {job_title}
📱 Номер телефона: {phone}
👤 Пользователь: {user}

{stage}
"""


@registration_router.message(Registration.language)
async def get_language(message: Message, state: FSMContext, access: str):
    if message.text in LANGUAGE_CHOICES.keys():
        choose_language = LANGUAGE_CHOICES[message.text]

        if access:
            user = await conf.bitrix_db.get_user(tg_id=message.from_user.id)
            if user:
                user = user[0]
                user.language = choose_language
                await conf.bitrix_db.update_user(user)
                conf.user_manager.update_user(message.from_user.id, language=choose_language)

                await to_user_main_menu(message, state, choose_language)

        else:
            await message.answer(_("reg.name", choose_language), reply_markup=ReplyKeyboardRemove())
            await state.update_data({"language": choose_language})
            await state.set_state(Registration.name)

    else:
        await message.answer(_("not_valid", translator.default_language))


@registration_router.message(Registration.name)
async def registration_name(message: Message, state: FSMContext):
    data = await state.get_data()
    language = data["language"]

    if message.text and 5 > len(message.text.split()) > 1:
        await state.update_data({"name": message.text})
        await state.set_state(Registration.job_title)
        await message.answer(_("reg.job_title", language))
    else:
        await message.answer(_("wrong_format", language))


@registration_router.message(Registration.job_title)
async def registration_job_title(message: Message, state: FSMContext):
    data = await state.get_data()
    language = data["language"]

    if message.text:
        await state.update_data({"job_title": message.text})
        await state.set_state(Registration.phone)
        await message.answer(_("reg.phone", language), reply_markup=phone_rkb(language))
    else:
        await message.answer(_("wrong_format", language))


@registration_router.message(Registration.phone)
async def registration_phone(message: Message, state: FSMContext, bot: Bot):
    def check_phone_numbers(phone_numbers):
        pattern = re.compile(r'998\s\d{2}\s\d{3}\s\d{2}\s\d{2}')
        result = pattern.findall(phone_numbers)
        return result

    async def save_registration(phone_number, name, job_title, lang: str):
        await state.set_state(Registration.checking)
        await message.answer(_("reg.done", language), reply_markup=ReplyKeyboardRemove())

        user = await conf.bitrix_db.add_user(
            full_name=name,
            access_level=AccessLevelConst.USER,
            tg_id=message.from_user.id,
            job_title=job_title,
            phone=phone_number,
            language=language,
        )
        conf.user_manager.update_user(message.from_user.id, AccessLevelConst.USER, lang)

        notify = REG_NOTIFY_ANS.format(
            name=name,
            job_title=job_title,
            phone=phone_number,
            user=message.from_user.full_name if not message.from_user.username else f"@{message.from_user.username}",
            stage=REG_STATUS_WAIT + f' <a href="{conf.project_url}/admin/user/edit/{user.id}">Открыть</a>'

        )
        ## remove confirmation
        # await bot.send_message(conf.notify_chat_id, notify, reply_markup=create_confirm_ikb(message.from_user.id))

        # confirm user immediently
        user = await conf.bitrix_db.update_user(update_to=UserModel(access_level=user.access_level), tg_id=int(user.tg_id))
        conf.user_manager.update_user(tg_id=int(user.tg_id), access_level=user.access_level)
        

    data = await state.get_data()
    language = data["language"]

    if message.text and check_phone_numbers(message.text):
        data = await state.get_data()
        await save_registration(message.text, data["name"], data["job_title"], data["language"])

    elif message.contact:
        data = await state.get_data()
        await save_registration(message.contact.phone_number, data["name"], data["job_title"], language)

    else:
        await message.answer(_("wrong_format", language))
