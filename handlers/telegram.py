from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from services.ticket_service import create_ticket, get_active_ticket, add_message_to_ticket
from services.faq_service import FAQService
from database.models import Category, SourceType

from core.config import settings

router = Router()

class TicketForm(StatesGroup):
    waiting_text = State()

# --- КЛАВИАТУРЫ ---
async def get_menu_kb(session: AsyncSession):
    # Fetch categories from DB
    stmt = select(Category)
    result = await session.execute(stmt)
    categories = result.scalars().all()

    keyboard = []
    row = []
    for cat in categories:
        # Use simple callback data format: "cat_<id>"
        # But for backward compatibility with existing hardcoded "cat_study" logic in start handler...
        # The user asked to make it dynamic.
        # Let's map callback_data="cat_{name}"
        cb_data = f"cat_{cat.name}"
        # Make sure not to exceed 64 bytes for callback_data
        if len(cb_data.encode('utf-8')) > 64:
             cb_data = f"cat_id_{cat.id}"

        row.append(InlineKeyboardButton(text=f"{cat.name}", callback_data=cb_data))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- ХЕНДЛЕРЫ ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()
    kb = await get_menu_kb(session)
    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\nВыберите тему обращения:",
        reply_markup=kb
    )

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery):
    faqs = FAQService.get_cache()

    if faqs:
        text = "\n".join([f"🔹 {f.trigger_word}: {f.answer_text}" for f in faqs])
    else:
        text = "База знаний пока пуста."

    await callback.message.answer(f"📚 <b>FAQ:</b>\n\n{text}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def select_cat(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    # Determine category name from callback data
    cat_data = callback.data
    category_name = "Общее"
    
    if cat_data.startswith("cat_id_"):
        try:
             cat_id = int(cat_data.split("_")[-1])
             cat = await session.get(Category, cat_id)
             if cat: category_name = cat.name
        except: pass
    else:
        # Assuming cat_{name}
        category_name = cat_data.replace("cat_", "")

    await state.update_data(category=category_name)
    await state.set_state(TicketForm.waiting_text)
    await callback.message.edit_text(f"Тема: <b>{category_name}</b>.\n✍️ Напишите ваш вопрос:", parse_mode="HTML")

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message, state: FSMContext, bot: Bot, session: AsyncSession):
    # Skip if it is a reply in the staff chat (though usually user bot is separate)
    # The original check was: if message.from_user.id == settings.TG_ADMIN_ID and message.reply_to_message: return
    # We should keep a similar check if the bot runs in a mode where admin is also a user?
    # Actually, better to check if message.chat.id == TG_STAFF_CHAT_ID (group chat)
    if message.chat.id == settings.TG_STAFF_CHAT_ID:
        return

    # 1. Check for Active Ticket First (Critical Fix)
    active_ticket = await get_active_ticket(session, message.from_user.id, SourceType.TELEGRAM)

    if active_ticket:
        # If user is in Waiting Text state, it means they are creating a new ticket,
        # but create_ticket should handle logic.
        # However, create_ticket creates a NEW one.
        # If active_ticket exists, we should attach to it.

        # Exception: User explicitly selected a category and is now typing the first message of a NEW ticket?
        # But wait, if they have an active ticket, they shouldn't be able to start a new one easily without closing the old one?
        # Or maybe the "Waiting Text" state implies they are finishing the creation flow.

        current_state = await state.get_state()
        if current_state == TicketForm.waiting_text:
             # This is the tricky part.
             # If they have an active ticket, but they are in the menu flow to create a new one...
             # Standard helpdesk logic: usually 1 active ticket per user.
             # If they have one, we should probably warn them or attach to the existing one.
             # Given the "Critical Error" description: "When student has active ticket ... calls create_ticket ... creates new daily_id".
             # The fix requested: "Call add_message_to_ticket instead".

             # So, if active_ticket exists, we ignore the "new ticket flow" and just append to the active one.
             await state.clear()
             await add_message_to_ticket(session, active_ticket, message.text, bot)
             await message.answer("✅ Сообщение добавлено к текущему диалогу.")
             return
        else:
             # Simply chatting
             await add_message_to_ticket(session, active_ticket, message.text, bot)
             await message.answer("✅ Сообщение добавлено к диалогу.")
             return

    # 2. If No Active Ticket

    # Check State
    current_state = await state.get_state()

    if current_state == TicketForm.waiting_text:
        # Creating new ticket
        data = await state.get_data()
        category = data.get("category", "Общее")

        t = await create_ticket(session, message.from_user.id, SourceType.TELEGRAM, message.text, bot, category, message.from_user.full_name)
        await message.answer(f"✅ <b>Заявка #{t.daily_id} принята!</b>", parse_mode="HTML")
        await state.clear()
        return

    # 3. Check FAQ (Cache)
    faq_match = FAQService.find_match(message.text)
    if faq_match:
        await message.answer(f"🤖 <b>Подсказка:</b>\n{faq_match.answer_text}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
        return

    # 4. Fallback -> Menu
    kb = await get_menu_kb(session)
    await message.answer(
        "Чтобы задать вопрос, выберите категорию:",
        reply_markup=kb
    )
