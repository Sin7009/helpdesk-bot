from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.setup import new_session
from services.ticket_service import create_ticket
from database.models import Ticket, TicketStatus
from core.config import settings

router = Router()

# --- НАСТРОЙКИ ---
FAQ_DATA = {
    "wifi": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "вайфай": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "пароль": "🔑 Сбросить пароль от ЛК можно в кабинете 205 или на сайте lk.mgpu.ru",
    "справк": "📄 Заказать справку можно через Личный Кабинет -> Раздел 'Услуги'.",
    "стипенди": "💰 Стипендия приходит 25-го числа каждого месяца на карту МИР."
}

class TicketForm(StatesGroup):
    waiting_category = State()
    waiting_text = State()

# --- КЛАВИАТУРЫ ---
def main_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_study"),
         InlineKeyboardButton(text="📄 Справки", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / ЛК", callback_data="cat_it"),
         InlineKeyboardButton(text="🏠 Общежитие", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="❓ Частые вопросы (FAQ)", callback_data="show_faq")]
    ])

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот поддержки. Выберите тему вопроса, и мы поможем:",
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery):
    text = "📚 <b>База знаний:</b>\n\n"
    for key, val in FAQ_DATA.items():
        text += f"🔹 {key.capitalize()}: {val}\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def select_category(callback: types.CallbackQuery, state: FSMContext):
    cats = {"cat_study": "Учеба", "cat_docs": "Документы", "cat_it": "IT", "cat_dorm": "Общежитие"}
    category = cats.get(callback.data, "Общее")
    
    await state.update_data(category=category)
    await state.set_state(TicketForm.waiting_text)
    
    await callback.message.edit_text(
        f"Тема: <b>{category}</b>.\n✍️ Опишите вашу проблему одним сообщением:",
        parse_mode="HTML"
    )

@router.message(TicketForm.waiting_text)
async def process_ticket_text(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text
    
    # Авто-проверка FAQ
    text_lower = text.lower()
    for key, answer in FAQ_DATA.items():
        if key in text_lower:
            await message.answer(f"🤖 <b>Возможно, это поможет:</b>\n{answer}\n\nЕсли нет — просто напишите вопрос еще раз.", parse_mode="HTML")
            return

    data = await state.get_data()
    category = data.get("category", "Общее")

    async with new_session() as session:
        ticket = await create_ticket(
            session, message.from_user.id, "tg", text, bot, category
        )
    
    await message.answer(f"✅ <b>Заявка #{ticket.id} принята!</b>\nМы скоро ответим.", parse_mode="HTML")
    await state.clear()

# --- АДМИНКА ---
@router.message(Command("reply"))
async def admin_reply(message: types.Message, bot: Bot):
    # Проверка на админа
    if message.from_user.id != settings.TG_ADMIN_ID:
        return

    try:
        # Парсим команду: /reply 123 Текст ответа
        args = message.text.split(" ", 2)
        if len(args) < 3:
            await message.answer("⚠️ Формат: `/reply ID Текст`")
            return
            
        ticket_id = int(args[1])
        reply_text = args[2]

        async with new_session() as session:
            ticket = await session.get(Ticket, ticket_id)
            if not ticket:
                await message.answer("❌ Тикет не найден.")
                return
            
            # Отправляем ответ юзеру
            try:
                await bot.send_message(
                    ticket.user_id, 
                    f"👨‍💼 <b>Ответ оператора:</b>\n\n{reply_text}", 
                    parse_mode="HTML"
                )
                ticket.status = TicketStatus.CLOSED
                await session.commit()
                await message.answer(f"✅ Ответ отправлен, тикет #{ticket_id} закрыт.")
            except Exception as e:
                await message.answer(f"❌ Ошибка отправки: {e}")

    except ValueError:
        await message.answer("❌ ID тикета должен быть числом.")
