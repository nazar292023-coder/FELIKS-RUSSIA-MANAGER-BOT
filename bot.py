import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from database import Database

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DB = Database(os.getenv("DATABASE_PATH", "feliks.db"))

if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN in the hosting environment variables.")
if not ADMIN_IDS:
    logging.warning("ADMIN_IDS is empty. Admin features will not be accessible.")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class Apply(StatesGroup):
    answers = State()
    screenshot = State()


class Support(StatesGroup):
    question = State()
    admin_reply = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎬 Заявление на медиа", callback_data="apply")],
        [InlineKeyboardButton(text="💬 Задать вопрос", callback_data="support")],
        [InlineKeyboardButton(text="🎖 Мой статус", callback_data="my_status")]
    ])


def home_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 На главную", callback_data="home")]
    ])


def support_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 Задать вопрос ИИ", callback_data="support_ai")],
        [InlineKeyboardButton(text="👨‍💻 Обратиться к администрации", callback_data="support_admin")],
        [InlineKeyboardButton(text="📜 История обращений", callback_data="history")],
        [InlineKeyboardButton(text="🏠 На главную", callback_data="home")]
    ])


def admin_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Открыть набор", callback_data="set_open"),
         InlineKeyboardButton(text="🔴 Закрыть набор", callback_data="set_closed")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton(text="📋 Последние заявки", callback_data="admin_apps")],
        [InlineKeyboardButton(text="💬 Последние обращения", callback_data="admin_questions")]
    ])


def media_application_text() -> str:
    return (
        "🎬 <b>ЗАЯВЛЕНИЕ НА СОТРУДНИЧЕСТВО С FELIKS RUSSIA</b>\n\n"
        "Заполните все пункты одним сообщением:\n\n"
        "<b>1. Сколько у вас просмотров?</b>\n"
        "Ответ:\n\n"
        "<b>2. Ваш игровой ник (если есть):</b>\n"
        "Ответ:\n\n"
        "<b>3. Сколько у вас подписчиков?</b>\n"
        "Ответ:\n\n"
        "<b>4. Какую зарплату хотите?</b>\n"
        "Игровую:\n"
        "Реальную:\n\n"
        "<b>5. Скриншот статистики за последние 7 дней:</b>\n"
        "После отправки анкеты прикрепите скриншот отдельным сообщением.\n\n"
        "<b>Как посмотреть статистику TikTok:</b>\n"
        "1. Откройте профиль TikTok.\n"
        "2. Нажмите ☰ → TikTok Studio.\n"
        "3. Откройте «Аналитика».\n"
        "4. Выберите период «Последние 7 дней».\n"
        "5. Сделайте скриншот просмотров.\n\n"
        "<b>6. Ссылка на ваш TikTok:</b>\n"
        "Ответ:\n\n"
        "<b>7. Ссылка на ваш YouTube:</b>\n"
        "Ответ:\n\n"
        "<b>8. Как с вами связаться?</b>\n"
        "Укажите ваш Telegram (@username) для связи или ссылку на страницу ВКонтакте.\n"
        "Ответ: (обязательно)\n\n"
        "❗ Все пункты обязательны. Если аккаунта нет, напишите «Нет»."
    )


async def ask_ai(question: str) -> str:
    if not OPENAI_API_KEY:
        return (
            "🤖 ИИ-помощник пока не настроен. Добавьте OPENAI_API_KEY "
            "в переменные хостинга. Вы можете обратиться к администрации."
        )
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты дружелюбный помощник игрового проекта FELIKS RUSSIA. "
                        "Отвечай кратко и не выдумывай официальные правила, цены "
                        "или решения администрации. Если не знаешь, предложи "
                        "обратиться к администрации."
                    )
                },
                {"role": "user", "content": question}
            ],
            max_tokens=350
        )
        return response.choices[0].message.content or "Не удалось сформировать ответ."
    except Exception:
        logging.exception("AI request failed")
        return "Не удалось получить ответ от ИИ. Попробуйте позже или обратитесь к администрации."


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    DB.ensure_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
    await message.answer(
        "🎮 <b>Добро пожаловать в FELIKS RUSSIA!</b>\n\n"
        "Вы можете подать заявление на вступление в медиа-команду проекта "
        "или связаться с администрацией по любым вопросам.\n\n"
        "↗️ <b>Полезные ссылки:</b>\n"
        '• Форум: <a href="https://forum-feliks-russia.samp.date/index.php">FELIKS RUSSIA</a>\n'
        '• Канал: <a href="https://t.me/crmp_feliksrussia">FELIKS RUSSIA</a>\n\n'
        "Выберите действие из меню ниже:",
        reply_markup=main_kb(),
        disable_web_page_preview=True
    )


@dp.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        return await message.answer("⛔ Нет доступа.")
    await message.answer("👑 <b>Панель управления FELIKS RUSSIA</b>", reply_markup=admin_kb())


@dp.callback_query(F.data == "home")
async def home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("🏠 Главное меню FELIKS RUSSIA:", reply_markup=main_kb())
    await call.answer()


@dp.callback_query(F.data == "my_status")
async def my_status(call: CallbackQuery):
    status = DB.get_status(call.from_user.id)
    await call.message.answer(f"🎖 Ваш статус: <b>{status}</b>", reply_markup=home_kb())
    await call.answer()


@dp.callback_query(F.data == "apply")
async def apply_start(call: CallbackQuery, state: FSMContext):
    if not DB.is_media_open():
        await call.message.answer(
            "🔴 Сейчас набор в медиа-команду закрыт. Следите за новостями проекта.",
            reply_markup=home_kb()
        )
    elif DB.has_pending_application(call.from_user.id):
        await call.message.answer(
            "⏳ У вас уже есть заявление на рассмотрении.",
            reply_markup=home_kb()
        )
    else:
        await state.set_state(Apply.answers)
        await call.message.answer(media_application_text(), reply_markup=home_kb())
        await call.message.answer(
            "✍️ Скопируйте пункты и заполните их одним сообщением. "
            "После этого я попрошу скриншот."
        )
    await call.answer()


@dp.message(Apply.answers)
async def apply_answers(message: Message, state: FSMContext):
    if not message.text or len(message.text.strip()) < 15:
        return await message.answer(
            "⚠️ Отправьте ответы текстом одним сообщением, заполнив все пункты."
        )
    if len(message.text) > 3500:
        return await message.answer("⚠️ Анкета слишком длинная. Сократите ответы и отправьте ещё раз.")

    await state.update_data(application_answers=message.text.strip())
    await state.set_state(Apply.screenshot)
    await message.answer(
        "📸 Теперь отправьте скриншот статистики профиля за последние 7 дней "
        "как фотографию или файл-документ.\n\n"
        "После получения скриншота я отправлю заявку администрации."
    )


async def forward_application_to_admins(message: Message, data: dict):
    answers = data["application_answers"]
    app_id = DB.create_application(
        message.from_user.id,
        message.from_user.full_name,
        message.from_user.username or "",
        channel=data.get("tiktok", ""),
        subs="Указано в анкете",
        views="Указано в анкете",
        videos=answers,
        screenshot_file_id=data.get("screenshot_file_id", ""),
        screenshot_kind=data.get("screenshot_kind", "")
    )

    admin_text = (
        f"🎬 <b>Новая заявка FELIKS RUSSIA №{app_id}</b>\n\n"
        f"👤 {message.from_user.full_name}\n"
        f"🆔 <code>{message.from_user.id}</code>\n"
        f"🔗 Telegram: @{message.from_user.username or 'не указан'}\n\n"
        f"<b>Анкета:</b>\n{answers}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve:{app_id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject:{app_id}")
    ]])

    sent_count = 0
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id, admin_text,
                disable_web_page_preview=True
            )
            file_id = data["screenshot_file_id"]
            if data["screenshot_kind"] == "photo":
                await bot.send_photo(
                    admin_id, file_id,
                    caption=f"📸 Скриншот к заявке №{app_id}",
                    reply_markup=kb
                )
            else:
                await bot.send_document(
                    admin_id, file_id,
                    caption=f"📸 Скриншот к заявке №{app_id}",
                    reply_markup=kb
                )
            sent_count += 1
        except Exception:
            logging.exception("Could not notify admin %s", admin_id)

    if sent_count == 0:
        await message.answer(
            "⚠️ Заявка сохранена, но уведомление не удалось доставить администраторам. "
            "Сообщите администрации проекта."
        )
    else:
        await message.answer(
            "✅ Заявление и скриншот отправлены администрации. Ожидайте решения.",
            reply_markup=main_kb()
        )


@dp.message(Apply.screenshot, F.photo)
async def apply_screenshot_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    data["screenshot_file_id"] = message.photo[-1].file_id
    data["screenshot_kind"] = "photo"
    await forward_application_to_admins(message, data)
    await state.clear()


@dp.message(Apply.screenshot, F.document)
async def apply_screenshot_document(message: Message, state: FSMContext):
    document = message.document
    if document and document.mime_type and not document.mime_type.startswith("image/"):
        return await message.answer("⚠️ Отправьте изображение JPG, PNG или скриншот как фото.")
    data = await state.get_data()
    data["screenshot_file_id"] = document.file_id
    data["screenshot_kind"] = "document"
    await forward_application_to_admins(message, data)
    await state.clear()


@dp.message(Apply.screenshot)
async def apply_screenshot_invalid(message: Message):
    await message.answer("📸 Пожалуйста, отправьте скриншот именно как фотографию или файл-изображение.")


@dp.callback_query(F.data == "support")
async def support_menu(call: CallbackQuery):
    await call.message.answer(
        "📌 <b>Служба поддержки FELIKS RUSSIA</b>\n\n"
        "Здесь вы можете задать вопрос ИИ или администрации проекта, "
        "а также просмотреть историю обращений.\n\n"
        f"✅ Лимит на сегодня: {DB.questions_today(call.from_user.id)} из 3 использовано\n"
        "⏰ Время ответа администрации зависит от загруженности.",
        reply_markup=support_kb()
    )
    await call.answer()


@dp.callback_query(F.data.in_({"support_ai", "support_admin"}))
async def support_begin(call: CallbackQuery, state: FSMContext):
    mode = "ai" if call.data == "support_ai" else "admin"
    if DB.questions_today(call.from_user.id) >= 3:
        await call.message.answer(
            "⛔ Вы использовали лимит 3 обращения на сегодня. Попробуйте завтра.",
            reply_markup=home_kb()
        )
    else:
        await state.update_data(support_mode=mode)
        await state.set_state(Support.question)
        prompt = (
            "🤖 Напишите вопрос для ИИ одним сообщением:"
            if mode == "ai"
            else "🖋 <b>Новое обращение в поддержку</b>\n\n"
                 "Опишите подробно ваш вопрос одним сообщением:"
        )
        await call.message.answer(prompt, reply_markup=home_kb())
    await call.answer()


@dp.message(Support.question)
async def support_question(message: Message, state: FSMContext):
    if DB.questions_today(message.from_user.id) >= 3:
        await state.clear()
        return await message.answer(
            "⛔ Лимит 3 обращения на сегодня исчерпан.",
            reply_markup=main_kb()
        )
    data = await state.get_data()
    mode = data.get("support_mode", "admin")
    question = message.text or message.caption or ""
    qid = DB.create_question(message.from_user.id, question, mode)
    await state.clear()
    if mode == "ai":
        answer = await ask_ai(question)
        DB.set_ai_answer(qid, answer)
        await message.answer(answer, reply_markup=support_kb())
    else:
        await message.answer(
            "✅ Ваше обращение отправлено администрации. Ответ придёт сюда.",
            reply_markup=support_kb()
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply:{qid}")
        ]])
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(
                    admin_id,
                    f"💬 <b>Новое обращение №{qid}</b>\n"
                    f"От: {message.from_user.full_name} "
                    f"(<code>{message.from_user.id}</code>)\n\n{question}",
                    reply_markup=kb
                )
            except Exception:
                logging.exception("Could not forward support request")


@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    rows = DB.user_questions(call.from_user.id)
    if not rows:
        text = (
            "📁 <b>История вопросов пуста</b>\n\n"
            "Вы ещё не отправляли обращений в службу поддержки."
        )
    else:
        parts = ["📜 <b>История обращений</b>"]
        for qid, created, mode, question, answer in rows[:10]:
            parts.append(
                f"\n<b>№{qid}</b> · {created} · {'ИИ' if mode == 'ai' else 'Администрация'}\n"
                f"Вопрос: {question[:250]}\n"
                f"Ответ: {(answer or 'Ожидает ответа')[:250]}"
            )
        text = "\n".join(parts)
    await call.message.answer(text, reply_markup=home_kb())
    await call.answer()


@dp.callback_query(F.data.startswith("approve:"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    app_id = int(call.data.split(":")[1])
    user_id = DB.decide_application(app_id, "approved")
    if not user_id:
        return await call.answer("Заявка уже обработана или не найдена", show_alert=True)
    DB.set_status(user_id, "🎬 Медиа")
    try:
        await bot.send_message(
            user_id,
            "🎉 Ваша заявка одобрена! Добро пожаловать в медиа-команду FELIKS RUSSIA.\n\n"
            "🎖 Вам присвоен статус: <b>🎬 Медиа</b>"
        )
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(
        f"✅ Заявка №{app_id} одобрена. Пользователю выдан статус 🎬 Медиа."
    )
    await call.answer("Одобрено")


@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    app_id = int(call.data.split(":")[1])
    user_id = DB.decide_application(app_id, "rejected")
    if not user_id:
        return await call.answer("Заявка уже обработана или не найдена", show_alert=True)
    try:
        await bot.send_message(
            user_id,
            "❌ К сожалению, ваша заявка в медиа-команду FELIKS RUSSIA отклонена администрацией."
        )
    except Exception:
        pass
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await call.message.answer(f"❌ Заявка №{app_id} отклонена.")
    await call.answer("Отказано")


@dp.callback_query(F.data == "set_open")
async def set_open(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    DB.set_media_open(True)
    await call.message.answer("🟢 Набор на медиа открыт.")
    await call.answer()


@dp.callback_query(F.data == "set_closed")
async def set_closed(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    DB.set_media_open(False)
    await call.message.answer("🔴 Набор на медиа закрыт.")
    await call.answer()


@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    s = DB.stats()
    await call.message.answer(
        f"📊 <b>Статистика FELIKS RUSSIA</b>\n\n"
        f"👥 Пользователей: {s['users']}\n"
        f"🎬 Всего заявок: {s['apps']}\n"
        f"✅ Одобрено: {s['approved']}\n"
        f"❌ Отказано: {s['rejected']}\n"
        f"⏳ На рассмотрении: {s['pending']}\n"
        f"💬 Обращений: {s['questions']}\n\n"
        f"Набор: {'🟢 открыт' if DB.is_media_open() else '🔴 закрыт'}"
    )
    await call.answer()


@dp.callback_query(F.data == "admin_apps")
async def admin_apps(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    rows = DB.recent_apps()
    if not rows:
        text = "Заявок пока нет."
    else:
        text = "📋 <b>Последние заявки</b>\n\n" + "\n".join(
            [f"№{r[0]} · {r[2]} · {r[3]} · {r[4]}" for r in rows]
        )
    await call.message.answer(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data == "admin_questions")
async def admin_questions(call: CallbackQuery):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    rows = DB.recent_questions()
    if not rows:
        text = "Обращений пока нет."
    else:
        text = "💬 <b>Последние обращения</b>\n\n" + "\n\n".join(
            [f"№{r[0]} · ID {r[1]} · {r[2]}\n{r[3][:350]}" for r in rows]
        )
    await call.message.answer(text, reply_markup=admin_kb())
    await call.answer()


@dp.callback_query(F.data.startswith("reply:"))
async def reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        return await call.answer("Нет доступа", show_alert=True)
    qid = int(call.data.split(":")[1])
    await state.update_data(reply_qid=qid)
    await state.set_state(Support.admin_reply)
    await call.message.answer(f"✍️ Напишите ответ на обращение №{qid}:")
    await call.answer()


@dp.message(Support.admin_reply)
async def reply_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await state.clear()
        return
    data = await state.get_data()
    qid = data.get("reply_qid")
    user_id = DB.answer_question(qid, message.text or "")
    await state.clear()
    if user_id:
        try:
            await bot.send_message(
                user_id,
                f"👨‍💻 <b>Ответ администрации на обращение №{qid}:</b>\n\n{message.text}"
            )
        except Exception:
            await message.answer("Не удалось доставить ответ пользователю.")
        await message.answer("✅ Ответ отправлен.")
    else:
        await message.answer("Обращение не найдено.")


async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
