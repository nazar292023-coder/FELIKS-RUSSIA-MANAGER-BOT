import os
import asyncio
import logging
from datetime import datetime, date
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv
from database import Database

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
DB = Database(os.getenv("DATABASE_PATH", "feliks.db"))

if not TOKEN:
    raise RuntimeError("Set BOT_TOKEN in the hosting environment variables.")
if not ADMIN_IDS:
    logging.warning("ADMIN_IDS is empty. Admin features will not be accessible.")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class Apply(StatesGroup):
    channel = State()
    subscribers = State()
    views = State()
    videos = State()

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

async def ask_ai(question: str) -> str:
    if not OPENAI_API_KEY:
        return "🤖 ИИ-помощник пока не настроен. Добавьте OPENAI_API_KEY в переменные хостинга. Вы можете обратиться к администрации."
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": "Ты дружелюбный помощник игрового проекта FELIKS RUSSIA. Отвечай кратко и не выдумывай официальные правила, цены или решения администрации. Если не знаешь, предложи обратиться к администрации."},
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
        "Вы можете подать заявление на вступление в медиа-команду проекта или связаться с администрацией по любым вопросам.\n\n"
        "↗️ <b>Полезные ссылки:</b>\n"
        '• Форум: <a href="https://forum-feliks-russia.samp.date/index.php">FELIKS RUSSIA</a>\n'
        '• Канал: <a href="https://t.me/crmp_feliksrussia">FELIKS RUSSIA</a>\n\n'
        "Выберите действие из меню ниже:", reply_markup=main_kb(), disable_web_page_preview=True)

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
        await call.message.answer("🔴 Сейчас набор в медиа-команду закрыт. Следите за новостями проекта.", reply_markup=home_kb())
    elif DB.has_pending_application(call.from_user.id):
        await call.message.answer("⏳ У вас уже есть заявление на рассмотрении.", reply_markup=home_kb())
    else:
        await state.set_state(Apply.channel)
        await call.message.answer("🎬 <b>Сотрудничество с FELIKS RUSSIA</b>\n\nКритерии:\n1. На канале есть 3 видео про наш проект.\n2. Стабильно 700–800+ просмотров.\n3. От 30+ подписчиков.\n4. Тематика роликов — SAMP / CRMP.\n\nПришлите ссылку на ваш канал:", reply_markup=home_kb())
    await call.answer()

@dp.message(Apply.channel)
async def apply_channel(message: Message, state: FSMContext):
    await state.update_data(channel=message.text or "")
    await state.set_state(Apply.subscribers)
    await message.answer("👥 Сколько подписчиков на вашем канале?")

@dp.message(Apply.subscribers)
async def apply_subs(message: Message, state: FSMContext):
    await state.update_data(subscribers=message.text or "")
    await state.set_state(Apply.views)
    await message.answer("👁 Сколько просмотров обычно набирают ваши видео?")

@dp.message(Apply.views)
async def apply_views(message: Message, state: FSMContext):
    await state.update_data(views=message.text or "")
    await state.set_state(Apply.videos)
    await message.answer("🎥 Отправьте ссылки на 3 видео про FELIKS RUSSIA (можно одним сообщением).")

@dp.message(Apply.videos)
async def apply_videos(message: Message, state: FSMContext):
    data = await state.get_data()
    app_id = DB.create_application(message.from_user.id, message.from_user.full_name,
                                   message.from_user.username or "", data.get("channel",""),
                                   data.get("subscribers",""), data.get("views",""), message.text or "")
    await state.clear()
    await message.answer("✅ Заявление отправлено администрации. Ожидайте решения.", reply_markup=main_kb())
    text = (f"🎬 <b>Новая заявка FELIKS RUSSIA №{app_id}</b>\n\n"
            f"👤 {message.from_user.full_name}\n🆔 <code>{message.from_user.id}</code>\n"
            f"🔗 Канал: {data.get('channel')}\n👥 Подписчики: {data.get('subscribers')}\n"
            f"👁 Просмотры: {data.get('views')}\n🎥 Видео: {message.text}")
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Одобрить", callback_data=f"approve:{app_id}"),
        InlineKeyboardButton(text="❌ Отказать", callback_data=f"reject:{app_id}")
    ]])
    for admin_id in ADMIN_IDS:
        try: await bot.send_message(admin_id, text, reply_markup=kb, disable_web_page_preview=True)
        except Exception: logging.exception("Could not notify admin")

@dp.callback_query(F.data == "support")
async def support_menu(call: CallbackQuery):
    await call.message.answer(
        "📌 <b>Служба поддержки FELIKS RUSSIA</b>\n\n"
        "Здесь вы можете задать вопрос ИИ или администрации проекта, а также просмотреть историю обращений.\n\n"
        f"✅ Лимит на сегодня: {DB.questions_today(call.from_user.id)} из 3 использовано\n"
        "⏰ Время ответа администрации зависит от загруженности.", reply_markup=support_kb())
    await call.answer()

@dp.callback_query(F.data.in_({"support_ai", "support_admin"}))
async def support_begin(call: CallbackQuery, state: FSMContext):
    mode = "ai" if call.data == "support_ai" else "admin"
    if DB.questions_today(call.from_user.id) >= 3:
        await call.message.answer("⛔ Вы использовали лимит 3 обращения на сегодня. Попробуйте завтра.", reply_markup=home_kb())
    else:
        await state.update_data(support_mode=mode)
        await state.set_state(Support.question)
        prompt = "🤖 Напишите вопрос для ИИ одним сообщением:" if mode == "ai" else "🖋 <b>Новое обращение в поддержку</b>\n\nОпишите подробно ваш вопрос одним сообщением:"
        await call.message.answer(prompt, reply_markup=home_kb())
    await call.answer()

@dp.message(Support.question)
async def support_question(message: Message, state: FSMContext):
    if DB.questions_today(message.from_user.id) >= 3:
        await state.clear()
        return await message.answer("⛔ Лимит 3 обращения на сегодня исчерпан.", reply_markup=main_kb())
    data = await state.get_data()
    mode = data.get("support_mode", "admin")
    qid = DB.create_question(message.from_user.id, message.text or "", mode)
    await state.clear()
    if mode == "ai":
        answer = await ask_ai(message.text or "")
        DB.set_ai_answer(qid, answer)
        await message.answer(answer, reply_markup=support_kb())
    else:
        await message.answer("✅ Ваше обращение отправлено администрации. Ответ придёт сюда.", reply_markup=support_kb())
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✍️ Ответить", callback_data=f"reply:{qid}")]])
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, f"💬 <b>Новое обращение №{qid}</b>\nОт: {message.from_user.full_name} (<code>{message.from_user.id}</code>)\n\n{message.text}", reply_markup=kb)
            except Exception: logging.exception("Could not forward support request")

@dp.callback_query(F.data == "history")
async def history(call: CallbackQuery):
    rows = DB.user_questions(call.from_user.id)
    if not rows:
        text = "📁 <b>История вопросов пуста</b>\n\nВы ещё не отправляли обращений в службу поддержки."
    else:
        parts = ["📜 <b>История обращений</b>"]
        for qid, created, mode, question, answer in rows[:10]:
            parts.append(f"\n<b>№{qid}</b> · {created} · {'ИИ' if mode == 'ai' else 'Администрация'}\nВопрос: {question[:250]}\nОтвет: {(answer or 'Ожидает ответа')[:250]}")
        text = "\n".join(parts)
    await call.message.answer(text, reply_markup=home_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("approve:"))
async def approve(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    app_id = int(call.data.split(":")[1])
    user_id = DB.decide_application(app_id, "approved")
    if not user_id: return await call.answer("Заявка уже обработана или не найдена", show_alert=True)
    DB.set_status(user_id, "🎬 Медиа")
    try: await bot.send_message(user_id, "🎉 Ваша заявка одобрена! Добро пожаловать в медиа-команду FELIKS RUSSIA.\n\n🎖 Вам присвоен статус: <b>🎬 Медиа</b>")
    except Exception: pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"✅ Заявка №{app_id} одобрена. Пользователю выдан статус 🎬 Медиа.")
    await call.answer("Одобрено")

@dp.callback_query(F.data.startswith("reject:"))
async def reject(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    app_id = int(call.data.split(":")[1])
    user_id = DB.decide_application(app_id, "rejected")
    if not user_id: return await call.answer("Заявка уже обработана или не найдена", show_alert=True)
    try: await bot.send_message(user_id, "❌ К сожалению, ваша заявка в медиа-команду FELIKS RUSSIA отклонена администрацией.")
    except Exception: pass
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(f"❌ Заявка №{app_id} отклонена.")
    await call.answer("Отказано")

@dp.callback_query(F.data == "set_open")
async def set_open(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    DB.set_media_open(True)
    await call.message.answer("🟢 Набор на медиа открыт.")
    await call.answer()

@dp.callback_query(F.data == "set_closed")
async def set_closed(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    DB.set_media_open(False)
    await call.message.answer("🔴 Набор на медиа закрыт.")
    await call.answer()

@dp.callback_query(F.data == "stats")
async def stats(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    s = DB.stats()
    await call.message.answer(f"📊 <b>Статистика FELIKS RUSSIA</b>\n\n👥 Пользователей: {s['users']}\n🎬 Всего заявок: {s['apps']}\n✅ Одобрено: {s['approved']}\n❌ Отказано: {s['rejected']}\n⏳ На рассмотрении: {s['pending']}\n💬 Обращений: {s['questions']}\n\nНабор: {'🟢 открыт' if DB.is_media_open() else '🔴 закрыт'}")
    await call.answer()

@dp.callback_query(F.data == "admin_apps")
async def admin_apps(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    rows = DB.recent_apps()
    if not rows: text = "Заявок пока нет."
    else:
        text = "📋 <b>Последние заявки</b>\n\n" + "\n".join([f"№{r[0]} · {r[2]} · {r[3]} · {r[4]}" for r in rows])
    await call.message.answer(text, reply_markup=admin_kb())
    await call.answer()

@dp.callback_query(F.data == "admin_questions")
async def admin_questions(call: CallbackQuery):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
    rows = DB.recent_questions()
    if not rows: text = "Обращений пока нет."
    else: text = "💬 <b>Последние обращения</b>\n\n" + "\n\n".join([f"№{r[0]} · ID {r[1]} · {r[2]}\n{r[3][:350]}" for r in rows])
    await call.message.answer(text, reply_markup=admin_kb())
    await call.answer()

@dp.callback_query(F.data.startswith("reply:"))
async def reply_start(call: CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id): return await call.answer("Нет доступа", show_alert=True)
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
        try: await bot.send_message(user_id, f"👨‍💻 <b>Ответ администрации на обращение №{qid}:</b>\n\n{message.text}")
        except Exception: await message.answer("Не удалось доставить ответ пользователю.")
        await message.answer("✅ Ответ отправлен.")
    else:
        await message.answer("Обращение не найдено.")

async def main():
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
