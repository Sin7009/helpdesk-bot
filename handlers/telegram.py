from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.setup import new_session
from services.ticket_service import create_ticket
from database.models import Ticket, TicketStatus, User
from core.config import settings

router = Router()

# --- ДАННЫЕ ---
FAQ_DATA = {
    "wifi": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "вайфай": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "пароль": "🔑 Сбросить пароль: lk.mgpu.ru или каб. 205",
    "справк": "📄 Справки: Личный Кабинет -> Услуги",
    "стипенди": "💰 Стипендия: 25-го числа на карту МИР"
}

class TicketForm(StatesGroup):
    waiting_text = State()

# --- КЛАВИАТУРЫ ---
def get_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_study"),
         InlineKeyboardButton(text="📄 Справки", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / ЛК", callback_data="cat_it"),
         InlineKeyboardButton(text="🏠 Общежитие", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq")]
    ])

# --- ЛОГИКА ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыберите тему обращения:",
        reply_markup=get_menu_kb()
    )

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery):
    text = "\n".join([f"🔹 {v}" for v in FAQ_DATA.values()])
    await callback.message.answer(f"📚 <b>FAQ:</b>\n\n{text}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def select_cat(callback: types.CallbackQuery, state: FSMContext):
    cat_map = {"cat_study": "Учеба", "cat_docs": "Справки", "cat_it": "IT", "cat_dorm": "Общежитие"}
    category = cat_map.get(callback.data, "Общее")
    
    await state.update_data(category=category)
    await state.set_state(TicketForm.waiting_text)
    await callback.message.edit_text(f"Тема: <b>{category}</b>.\n✍️ Напишите ваш вопрос:", parse_mode="HTML")

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message, state: FSMContext, bot: Bot):
    # 1. Проверка FAQ (быстрый ответ)
    for k, v in FAQ_DATA.items():
        if k in message.text.lower():
            await message.answer(f"🤖 <b>Подсказка:</b>\n{v}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
            return

    # 2. Проверка состояния (ждет ли бот вопрос?)
    current_state = await state.get_state()
    
    # Если мы НЕ ждем вопрос (студент просто написал "Привет")
    if current_state != TicketForm.waiting_text:
        # Проверим, может у него уже есть ОТКРЫТЫЙ тикет?
        async with new_session() as session:
            # Ищем юзера и активный тикет
            # (Упрощенная логика: если тикет есть, добавляем сообщение. Если нет — просим категорию)
            result = await session.execute(select(User).where(User.external_id == message.from_user.id))
            user = result.scalar_one_or_none()
            
            has_active_ticket = False
            if user:
                res_t = await session.execute(select(Ticket).where(Ticket.user_id == user.id, Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS])))
                if res_t.first():
                    has_active_ticket = True
            
            if has_active_ticket:
                # Добавляем в существующий (через сервис)
                await create_ticket(session, message.from_user.id, "tg", message.text, bot, "Existing")
                await message.answer("✅ Сообщение добавлено к вашей заявке.")
                return
            else:
                # Тикета нет, состояние не установлено -> Показываем меню
                await message.answer(
                    "Чтобы задать вопрос, пожалуйста, сначала выберите категорию:",
                    reply_markup=get_menu_kb() # <--- ВОТ ОНО, СПАСЕНИЕ
                )
                return

    # 3. Создание нового тикета (если состояние waiting_text)
    data = await state.get_data()
    category = data.get("category", "Общее")
    
    async with new_session() as session:
        t = await create_ticket(session, message.from_user.id, "tg", message.text, bot, category)
    
    await message.answer(f"✅ <b>Заявка #{t.id} создана!</b>", parse_mode="HTML")
    await state.clear()

# --- АДМИНКА ---
@router.message(Command("reply"))
async def admin_reply(message: types.Message, bot: Bot):
    if message.from_user.id != settings.TG_ADMIN_ID: return
    try:
        _, t_id, text = message.text.split(" ", 2)
        async with new_session() as session:
            ticket = await session.get(Ticket, int(t_id))
            if ticket:
                await bot.send_message(ticket.user_id, f"👨‍💼 <b>Ответ:</b>\n{text}", parse_mode="HTML")
                ticket.status = TicketStatus.CLOSED
                await session.commit()
                await message.answer(f"Тикет #{t_id} закрыт.")
            else:
                await message.answer("Тикет не найден.")
    except:
        await message.answer("Ошибка. Пиши: /reply ID Текст")
