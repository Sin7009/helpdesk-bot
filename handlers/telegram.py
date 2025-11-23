from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.setup import new_session
from services.ticket_service import create_ticket
from database.models import Ticket, TicketStatus, User, FAQ, SourceType

router = Router()

class TicketForm(StatesGroup):
    waiting_text = State()

# --- КЛАВИАТУРЫ ---
def get_menu_kb():
    # В идеале кнопки тоже брать из БД (таблица Categories), но пока оставим хардкод для старта
    # Или можно сделать select(Category) если таблица заполнена
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_study"),
         InlineKeyboardButton(text="📄 Справки", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / ЛК", callback_data="cat_it"),
         InlineKeyboardButton(text="🏠 Общежитие", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq")]
    ])

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыберите тему обращения:",
        reply_markup=get_menu_kb()
    )

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery):
    async with new_session() as session:
        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        faqs = result.scalars().all()

    if faqs:
        text = "\n".join([f"🔹 {f.trigger_word}: {f.answer_text}" for f in faqs])
    else:
        text = "База знаний пока пуста."

    await callback.message.answer(f"📚 <b>FAQ:</b>\n\n{text}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def select_cat(callback: types.CallbackQuery, state: FSMContext):
    cat_map = {
        "cat_study": "Учеба", 
        "cat_docs": "Справки", 
        "cat_it": "IT", 
        "cat_dorm": "Общежитие"
    }
    category = cat_map.get(callback.data, "Общее")
    
    await state.update_data(category=category)
    await state.set_state(TicketForm.waiting_text)
    await callback.message.edit_text(f"Тема: <b>{category}</b>.\n✍️ Напишите ваш вопрос:", parse_mode="HTML")

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message, state: FSMContext, bot: Bot):
    async with new_session() as session:
        # 1. Проверка FAQ
        stmt = select(FAQ)
        result = await session.execute(stmt)
        faqs = result.scalars().all()

        for faq in faqs:
             if faq.trigger_word.lower() in message.text.lower():
                await message.answer(f"🤖 <b>Подсказка:</b>\n{faq.answer_text}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
                return

        # 2. Проверка состояния
        current_state = await state.get_state()

        # Если студент пишет "Привет" без выбора категории
        if current_state != TicketForm.waiting_text:
            # Проверяем активный тикет
            result = await session.execute(select(User).where(User.external_id == message.from_user.id))
            user = result.scalar_one_or_none()
            
            has_active_ticket = False
            if user:
                res_t = await session.execute(select(Ticket).where(
                    Ticket.user_id == user.id, 
                    Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS])
                ))
                if res_t.first():
                    has_active_ticket = True
            
            if has_active_ticket:
                # Добавляем в существующий
                await create_ticket(session, message.from_user.id, SourceType.TELEGRAM, message.text, bot, "Existing")
                await message.answer("✅ Сообщение добавлено к диалогу.")
                return
            else:
                # Тикета нет -> Меню
                await message.answer(
                    "Чтобы задать вопрос, выберите категорию:",
                    reply_markup=get_menu_kb()
                )
                return

        # 3. Создание нового тикета
        data = await state.get_data()
        category = data.get("category", "Общее")

        t = await create_ticket(session, message.from_user.id, SourceType.TELEGRAM, message.text, bot, category)
    
    await message.answer(f"✅ <b>Заявка #{t.daily_id} принята!</b>", parse_mode="HTML")
    await state.clear()
