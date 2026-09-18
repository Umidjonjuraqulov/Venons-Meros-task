START_MESSAGE = "🇷🇺 Выберите язык\n🇺🇿 Tilni tanlang"
TO_REGISTRATION = "👤 Пройдите регистрацию\n👤 Ro'yxatdan o'ting"
ANTISPAM_MESSAGE = "⚠️ Too many messages\n⚠️ Слишком много сообщений\n⚠️ Juda ko'p xabarlar"
BLOCKED_MESSAGES = "❗️Access is denied\n❗️Доступ запрещён\n❗️Kirish taqiqlangan"
LANGUAGE_CHOICES = {
    "🇷🇺 Русский": "ru",
    "🇺🇿 O'zbek tili": "uz",
}

translations = {
    "ru": {
        "b.back": "◀️Назад",
        "b.cancel": "❌Отменить",
        "b.confirm": "✅Подтвердить",
        "b.send_phone": "📱Отправить телефон",

        "b.create_task": "📝Создать",
        "b.my_tasks": "📖Мои задачи",
        "b.observed_tasks": "📓Наблюдаемые задачи",
        "b.group_status": "❇️Свободные слоты",
        "b.write_review": "🗒Написать анонимный отзыв",

        "b.open_task": "📋Открыть",
        "b.write_comment": "💬Ответить",
        "b.done_task": "✅Перенести на готово",

        "b.skip": "⏩Пропустить",

        "b.previous": "⬅️Предыдущая",
        "b.next": "➡️Следующая",
        "b.closed": "✅Завершенные",
        "b.by_stage": "🎯По стадиям",

        "b.get_files": "📁Получить файлы",
        "b.comments": "💬Комментарии",
        "b.change_stage": "🔄Изменить стадию",
        "b.delete_task": "🗑Удалить задачу",
        "b.delete_confirm": "🗑Да удалить",

        "wrong_format": "❗️Не правильный формат",
        "menu": "🏠Меню",
        "choose": "Выберите⬇️",
        "group_status": "ℹ️Текущее состояние задач <b>{group}</b>\n"
            "{stages_info}\n"
            "🆓<b>Есть свободных мест: {free}/{max}</b>",

        "choose_group": "Выберите подразделение ⬇️",
        "max_active_tasks": "❗️Вы превысили лимит активных задач <b>({num})</b> в подразделении <b>{group}</b>\n\n"
                     "ℹ️Чтобы создать новую задачу, вам необходимо удалить или перевести на оценку свои старые задачи",

        "reg.name": "👤 Введите Ф.И.О",
        "reg.job_title": "💼 Введите вашу должность",
        "reg.phone": "📱 Отправьте или введите номер телефона (можно и несколько через запятую)\n"
                     "В таком формате: +998 ** *** ** **",
        "reg.done": "✅️Успешно зарегистрирован в базе данных.\n"
                    "🕐 Запрос на доступ ожидает подтверждения от администратора",
        "reg.checking": "ℹ️Ваша заявка регистрации отправлена!\nПожалуйста подождите подтверждения",
        "reg.success": "✅Вам предоставлен доступ.\nНажмите /start",
        "reg.failed": "❌Вы не прошли регистрацию",
        "reg.blocked": "❗️Доступ запрещён",
        "reg.not_accept_users": "❗️У вас нет прав для принятия пользователей",

        "task.title": "📋 Введите название задачи",
        "task.title_not": "❗️Отправьте название задачи до 128 символов",
        "task.choose_region": "🌍 Выберите регион",
        "task.choose_executor": "🧑🏻‍💻 Выберите исполнителя",
        "task.description": "✍️ Введите описание задачи",
        "task.file": "📁 Отправьте файл(ы) задачи",
        "task.file_get": "✅️Файл получен. Можете загрузить ещё или продолжить.",
        "task.file_err": "❗️Ошибка загрузки файла",
        "task.upload": "🚀Загрузка...",
        "task.done": "✅Задача успешно создана.",
        "task.err": "❌Ошибка загрузки задачи.",

        "task.custom_text": "✍️ Введите значение для поля <b>{field}</b>",
        "task.custom_select": "⬇️ Выберите значение для поля <b>{field}</b>",
        "task.custom_text_err": "❗️Отправьте текст для поля <b>{field}</b>",
        "task.custom_select_err": "❗️Выберите значение из предложенных вариантов",
        "task.custom_required": "❗️Поле <b>{field}</b> обязательно для заполнения"

    },

    "uz": {
        "b.back": "◀️Orqaga",
        "b.cancel": "❌Bekor qilish",
        "b.confirm": "✅Tasdiqlash",
        "b.send_phone": "📱Telefon raqamini yuborish",

        "b.create_task": "📝Yaratish",
        "b.my_tasks": "📖Mening vazifalarim",
        "b.observed_tasks": "📓Kuzatilayotgan vazifalar",
        "b.group_status": "❇️Bo‘sh joylar",
        "b.write_review": "🗒Anonim fikr yozish",

        "b.open_task": "📋Ochish",
        "b.write_comment": "💬Javob berish",
        "b.done_task": "✅Bajarilganga o‘tkazish",

        "b.skip": "⏩O‘tkazib yuborish",

        "b.previous": "⬅️Oldingi",
        "b.next": "➡️Keyingi",
        "b.closed": "✅Yakunlangan",
        "b.by_stage": "🎯Bosqichlar bo‘yicha",

        "b.get_files": "📁Fayllarni olish",
        "b.comments": "💬Izohlar",
        "b.change_stage": "🔄Bosqichni o‘zgartirish",
        "b.delete_task": "🗑Vazifani o‘chirish",
        "b.delete_confirm": "🗑Ha, o‘chirilsin",

        "wrong_format": "❗️Noto‘g‘ri format",
        "menu": "🏠Menu",
        "choose": "Tanlang⬇️",
        "group_status": "ℹ️Vazifalarning joriy holati <b>{group}</b>\n"
            "{stages_info}\n"
            "🆓<b>Bo‘sh o‘rinlar: {free}/{max}</b>",

        "choose_group": "Bo‘limni tanlang ⬇️",
        "max_active_tasks": "❗️Siz <b>({num})</b> ta faol vazifa limitidan oshib ketdingiz <b>{group}</b> bo‘limida\n\n"
                            "ℹ️Yangi vazifa yaratish uchun eski vazifalaringizni o‘chirishingiz yoki baholashga yuborishingiz kerak",

        "reg.name": "👤 F.I.Sh kiriting",
        "reg.job_title": "💼 Lavozimingizni kiriting",
        "reg.phone": "📱 Telefon raqamingizni yuboring yoki kiriting (bir nechta bo‘lsa, vergul bilan ajrating)\n"
                     "Quyidagi formatda: +998 ** *** ** **",
        "reg.done": "✅️Ma’lumotlar bazasiga muvaffaqiyatli ro‘yxatdan o‘tdingiz.\n"
                    "🕐 Kirish uchun so‘rov administrator tasdig‘ini kutmoqda",
        "reg.checking": "ℹ️Ro‘yxatdan o‘tish arizangiz yuborildi!\nIltimos, tasdiqlashni kuting",
        "reg.success": "✅ Sizga ruxsat berildi.\n/start tugmasini bosing",
        "reg.failed": "❌Siz ro‘yxatdan o‘ta olmadingiz",
        "reg.blocked": "❗️Kirish taqiqlangan",
        "reg.not_accept_users": "❗️Siz foydalanuvchilarni qabul qilish huquqiga ega emassiz",

        "task.title": "📋 Vazifa/Taklif nomini kiriting",
        "task.title_not": "❗️Vazifa/Taklif nomini 128 ta belgidan oshmagan holda yuboring",
        "task.choose_region": "🌍 Hududni tanlang",
        "task.choose_executor": "🧑🏻‍💻 Ijrochini tanlang",
        "task.description": "📝 Vazifa/Taklifni batafsil tasvirlab bering\n\n"
                            "❗ Qanday muammolarni ko‘ryapsiz?\n"
                            "💡 Ularni hal qilish bo‘yicha qanday yechimlaringiz bor?",
        "task.file": "📁 Vazifa/Taklif fayl(lar)ini yuboring",
        "task.file_get": "✅️Fayl qabul qilindi. Yana yuklashingiz yoki davom etishingiz mumkin.",
        "task.file_err": "❗️Fayl yuklashda xatolik",
        "task.upload": "🚀Yuklanmoqda...",
        "task.done": "✅Vazifa/Taklif muvaffaqiyatli yaratildi.",
        "task.err": "❌Vazifa/Taklif yuklashda xatolik.",

        "task.custom_text": "✍️ <b>{field}</b> maydoni uchun qiymat kiriting",
        "task.custom_select": "⬇️ <b>{field}</b> maydoni uchun qiymatni tanlang",
        "task.custom_text_err": "❗️<b>{field}</b> maydoni uchun matn yuboring",
        "task.custom_select_err": "❗️Taklif qilingan variantlardan birini tanlang",
        "task.custom_required": "❗️<b>{field}</b> maydoni to‘ldirilishi shart"
    }
}