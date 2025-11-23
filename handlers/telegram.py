from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.setup import new_session
from services.ticket_service import create_ticket
from database.models import Ticket
from core.config import settings

router = Router()

# FAQ Словарь (Ключевое слово -> Ответ)
FAQ_DB = {
    "стипенди": "💰 Стипендия приходит 25-го числа. Проверьте карту МИР.",
    "справк": "📄 Заказать справку можно в ЛК студента или в 105 кабинете.",
    "вайфай": "📶 Сеть: MGPU_Student, Пароль: mgpu2024",
    "wifi": "📶 Сеть: MGPU_Student, Пароль: mgpu2024",
    "пароль": "🔑 Для сброса пароля обратитесь в IT-отдел (каб. 202)."
}

# Машина состояний
class SupportState(StatesGroup):
    waiting_category = State()
    waiting_question = State()

# --- КЛАВИАТУРЫ ---
def get_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба / Экзамены", callback_data="cat_study")],
        [InlineKeyboardButton(text="📄 Справки / Документы", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / Личный кабинет", callback_data="cat_it")],
        [InlineKeyboardButton(text="🏠 Общежитие / Быт", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="🔍 Частые вопросы (FAQ)", callback_data="show_faq")]
    ])

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот поддержки департамента. Выберите тему вопроса:",
        reply_markup=get_main_kb()
    )

@router.callback_query(F.data == "show_faq")
async def show_faq_list(callback: types.CallbackQuery):
    text = "<b>📚 Частые вопросы:</b>\n\n"
    for k, v in FAQ_DB.items():
        text += f"❓ <i>...{k}...</i>\n👉 {v}\n\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def category_selected(callback: types.CallbackQuery, state: FSMContext):
    category_map = {
        "cat_study": "Учеба", "cat_docs": "Документы",
        "cat_it": "IT", "cat_dorm": "Общежитие"
    }
    category = category_map.get(callback.data, "Общее")
    
    await state.update_data(category=category)
    await state.set_state(SupportState.waiting_question)
    
    await callback.message.edit_text(f"Выбрана тема: <b>{category}</b>.\n✍️ Напишите ваш вопрос одним сообщением:", parse_mode="HTML")

@router.message(SupportState.waiting_question)
async def process_question(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text.lower()
    
    # 1. Проверка FAQ перед созданием тикета
    for key, answer in FAQ_DB.items():
        if key in text:
            await message.answer(f"🤖 <b>Авто-ответ:</b>\n{answer}\n\nЕсли это не помогло, напишите вопрос еще раз, переформулировав его.", parse_mode="HTML")
            return # Не создаем тикет

    # 2. Создание тикета
    data = await state.get_data()
    category = data.get("category", "Общее")
    
    async with new_session() as session:
        ticket = await create_ticket(
            session, 
            message.from_user.id, 
            "tg", 
            message.text, 
            bot,
            category=category
        )
        
    await message.answer(f"✅ <b>Заявка #{ticket.id} принята!</b>\nКатегория: {category}\nМы ответим в ближайшее время.", parse_mode="HTML")
    await state.clear()

# --- АДМИНКА ---
@router.message(Command("reply"))
async def admin_reply(message: types.Message, bot: Bot):
    if message.from_user.id != settings.TG_ADMIN_ID:
        return

    try:
        args = message.text.split(" ", 2)
        ticket_id = int(args[1])
        answer_text = args[2]
        
        async with new_session() as session:
            ticket = await session.get(Ticket, ticket_id)
            if ticket:
                # Отправляем ответ студенту
                await bot.send_message(ticket.user_id, f"🔔 <b>Ответ на заявку #{ticket.id}:</b>\n\n{answer_text}", parse_mode="HTML")
                ticket.status = "closed" # Закрываем тикет
                await session.commit()
                await message.answer(f"Ответ отправлен. Тикет #{ticket_id} закрыт.")
            else:
                await message.answer("Тикет не найден.")
    except Exception as e:
        await message.answer(f"Ошибка: /reply ID ТЕКСТ ({e})")
