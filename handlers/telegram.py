import re
from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select

from database.setup import new_session
from services.ticket_service import create_ticket
from database.models import Ticket, TicketStatus, User, FAQ
from core.config import settings

router = Router()

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
    async with new_session() as session:
        stmt = select(FAQ).order_by(FAQ.trigger_word)
        result = await session.execute(stmt)
        faqs = result.scalars().all()

    if faqs:
        text = "\n".join([f"🔹 {f.answer_text}" for f in faqs])
    else:
        text = "FAQ пока пуст."

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
    async with new_session() as session:
        # 1. Проверка FAQ (быстрый ответ)
        # We fetch all FAQs. For a large number of FAQs, Full Text Search would be better,
        # but for now iterating in memory (or SQL LIKE) is fine.
        # Given we need to check if trigger word is IN the message, we can't easily do WHERE message LIKE %trigger%.
        # We have to do WHERE 'message' LIKE %trigger% -> reverse like? No.
        # Better: fetch all triggers and check in python if list is small.
        # Or: SELECT * FROM faq.
        stmt = select(FAQ)
        result = await session.execute(stmt)
        faqs = result.scalars().all()

        for faq in faqs:
             if faq.trigger_word.lower() in message.text.lower():
                await message.answer(f"🤖 <b>Подсказка:</b>\n{faq.answer_text}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
                return

        # 2. Проверка состояния (ждет ли бот вопрос?)
        current_state = await state.get_state()

        # Если мы НЕ ждем вопрос (студент просто написал "Привет")
        if current_state != TicketForm.waiting_text:
            # Проверим, может у него уже есть ОТКРЫТЫЙ тикет?
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
                    reply_markup=get_menu_kb()
                )
                return

        # 3. Создание нового тикета (если состояние waiting_text)
        data = await state.get_data()
        category = data.get("category", "Общее")

        t = await create_ticket(session, message.from_user.id, "tg", message.text, bot, category)
    
    await message.answer(f"✅ <b>Заявка #{t.id} создана!</b>", parse_mode="HTML")
    await state.clear()

    # --- АДМИНКА ---

# Вариант 1: Нативный ответ (Reply) на сообщение бота
@router.message(F.reply_to_message & (F.from_user.id == settings.TG_ADMIN_ID))
async def admin_reply_native(message: types.Message, bot: Bot):
    # Пытаемся найти "#123" в тексте сообщения, на которое отвечаем
    origin_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"#(\d+)", origin_text)
    
    if not match:
        await message.answer("⚠️ Я не вижу ID тикета в сообщении, на которое вы ответили. Используйте /reply ID Текст")
        return

    ticket_id = int(match.group(1))
    answer_text = message.text
    
    await process_admin_answer(message, bot, ticket_id, answer_text)

# Вариант 2: Команда /reply ID Текст
@router.message(Command("reply"))
async def admin_reply_command(message: types.Message, bot: Bot):
    if message.from_user.id != settings.TG_ADMIN_ID: return
    try:
        args = message.text.split(" ", 2)
        ticket_id = int(args[1])
        answer_text = args[2]
        await process_admin_answer(message, bot, ticket_id, answer_text)
    except:
        await message.answer("⚠️ Формат: `/reply ID Текст` или просто ответьте на сообщение.")

# Общая функция отправки (чтобы не дублировать код)
async def process_admin_answer(message: types.Message, bot: Bot, ticket_id: int, text: str):
    async with new_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if ticket:
            try:
                await bot.send_message(
                    ticket.user_id, 
                    f"👨‍💼 <b>Ответ оператора:</b>\n\n{text}", 
                    parse_mode="HTML"
                )
                ticket.status = TicketStatus.CLOSED
                await session.commit()
                await message.answer(f"✅ Ответ ушел. Тикет #{ticket_id} закрыт.")
            except Exception as e:
                await message.answer(f"❌ Не удалось отправить: {e}")
        else:
            await message.answer("❌ Тикет не найден в базе.")
