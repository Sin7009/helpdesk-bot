from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from database.setup import new_session
from services.ticket_service import create_ticket, get_active_ticket, add_message_to_ticket
from database.models import Ticket, TicketStatus, Category
from sqlalchemy import select, delete
from core.config import settings
from datetime import datetime

router = Router()

# --- CONSTANTS ---
FAQ_DATA = {
    "wifi": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "вайфай": "📶 <b>Wi-Fi:</b> Сеть `MGPU_Student`, Пароль: `mgpu2024`",
    "пароль": "🔑 Сбросить пароль от ЛК можно в кабинете 205 или на сайте lk.mgpu.ru",
    "справк": "📄 Заказать справку можно через Личный Кабинет -> Раздел 'Услуги'.",
    "стипенди": "💰 Стипендия приходит 25-го числа каждого месяца на карту МИР."
}

class TicketForm(StatesGroup):
    waiting_category = State()
    waiting_initial_text = State() # Used to store text if user sent message first

# --- KEYBOARDS ---
async def get_main_menu_kb(session):
    # Dynamic categories
    result = await session.execute(select(Category))
    categories = result.scalars().all()

    keyboard = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(text=cat.name, callback_data=f"cat_{cat.id}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton(text="❓ Частые вопросы (FAQ)", callback_data="show_faq")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- HANDLERS ---

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    async with new_session() as session:
        kb = await get_main_menu_kb(session)

    await message.answer(
        f"Привет, {message.from_user.first_name}! 👋\n"
        "Я бот поддержки. Выберите тему вопроса, и мы поможем:",
        reply_markup=kb
    )

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery):
    text = "📚 <b>База знаний:</b>\n\n"
    for key, val in FAQ_DATA.items():
        text += f"🔹 {key.capitalize()}: {val}\n"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def select_category(callback: types.CallbackQuery, state: FSMContext, bot: Bot):
    cat_id = int(callback.data.split("_")[1])
    
    data = await state.get_data()
    initial_text = data.get("initial_text")
    
    async with new_session() as session:
        # Get category name
        category = await session.get(Category, cat_id)
        if not category:
            await callback.answer("Категория не найдена", show_alert=True)
            return

        if initial_text:
            # Create ticket immediately
            ticket = await create_ticket(
                session,
                callback.from_user.id,
                "tg",
                initial_text,
                bot,
                category.name,
                user_full_name=callback.from_user.full_name
            )
            await callback.message.edit_text(f"✅ <b>Заявка #{ticket.daily_id} принята!</b>\nТема: {category.name}\nМы скоро ответим.", parse_mode="HTML")
            await state.clear()
        else:
            # Wait for text
            await state.update_data(category_name=category.name)
            await state.set_state(TicketForm.waiting_initial_text)
            await callback.message.edit_text(
                f"Тема: <b>{category.name}</b>.\n✍️ Опишите вашу проблему одним сообщением:",
                parse_mode="HTML"
            )

@router.message(TicketForm.waiting_initial_text)
async def process_initial_ticket_text(message: types.Message, state: FSMContext, bot: Bot):
    text = message.text
    
    # Auto-FAQ check could go here, but requirements emphasize Dialogue Mode

    data = await state.get_data()
    category_name = data.get("category_name", "General")

    async with new_session() as session:
        ticket = await create_ticket(
            session, message.from_user.id, "tg", text, bot, category_name, user_full_name=message.from_user.full_name
        )
    
    await message.answer(f"✅ <b>Заявка #{ticket.daily_id} принята!</b>\nМы скоро ответим.", parse_mode="HTML")
    await state.clear()


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: types.Message, state: FSMContext, bot: Bot):
    # 1. Check if user has active ticket
    async with new_session() as session:
        active_ticket = await get_active_ticket(session, message.from_user.id, "tg")

        if active_ticket:
            # 2. Append to active ticket
            await add_message_to_ticket(session, active_ticket, message.text, bot)
            # Confirm to user? Usually silent or "sent".
            # Requirement says: "Append message... Notify admin".
            # Doesn't explicitly say notify user, but good UX is a checkmark or silent.
            # To avoid spamming user, maybe just reaction?
            # Or text confirmation.
            # "Message added to request #{id}"
            await message.reply("✅ Сообщение добавлено к вашей заявке.", disable_notification=True)
        else:
            # 3. No active ticket -> Trigger Category Selection
            # Save text for later
            await state.update_data(initial_text=message.text)

            kb = await get_main_menu_kb(session)
            await message.answer(
                "У вас нет активных заявок. Пожалуйста, выберите категорию, чтобы создать новую:",
                reply_markup=kb
            )

# --- ADMIN COMMANDS ---

@router.message(Command("add_category"))
async def add_category(message: types.Message):
    if message.from_user.id != settings.TG_ADMIN_ID: return

    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/add_category Название`")
        return

    name = args[1].strip()
    async with new_session() as session:
        try:
            session.add(Category(name=name))
            await session.commit()
            await message.answer(f"✅ Категория '{name}' добавлена.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")

@router.message(Command("del_category"))
async def del_category(message: types.Message):
    if message.from_user.id != settings.TG_ADMIN_ID: return

    args = message.text.split(" ", 1)
    if len(args) < 2:
        await message.answer("⚠️ Использование: `/del_category Название`")
        return

    name = args[1].strip()
    async with new_session() as session:
        # Check if used?
        # Simple delete for now
        result = await session.execute(select(Category).where(Category.name == name))
        cat = result.scalar_one_or_none()
        if cat:
            await session.delete(cat)
            await session.commit()
            await message.answer(f"✅ Категория '{name}' удалена.")
        else:
            await message.answer("❌ Категория не найдена.")

@router.message(Command("reply"))
async def admin_reply(message: types.Message, bot: Bot):
    if message.from_user.id != settings.TG_ADMIN_ID: return

    try:
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
            
            # Send to user
            try:
                await bot.send_message(
                    ticket.user_id, 
                    f"👨‍💼 <b>Ответ оператора:</b>\n\n{reply_text}", 
                    parse_mode="HTML"
                )

                # Add message to history (Admin role)
                msg = Message(ticket_id=ticket.id, sender_role="admin", text=reply_text)
                session.add(msg)
                await session.commit()

                # Keep open
                await message.answer(f"✅ Ответ отправлен в тикет #{ticket_id}.")
            except Exception as e:
                await message.answer(f"❌ Ошибка отправки: {e}")

    except ValueError:
        await message.answer("❌ ID тикета должен быть числом.")

@router.message(Command("close"))
async def close_ticket_command(message: types.Message, bot: Bot):
    if message.from_user.id != settings.TG_ADMIN_ID: return

    try:
        args = message.text.split(" ", 1)
        if len(args) < 2:
            await message.answer("⚠️ Формат: `/close ID`")
            return

        ticket_id = int(args[1])
        await close_ticket_logic(ticket_id, bot, message)
    except ValueError:
        await message.answer("❌ ID должен быть числом.")

@router.callback_query(F.data.startswith("close_ticket_"))
async def close_ticket_btn(callback: types.CallbackQuery, bot: Bot):
    if callback.from_user.id != settings.TG_ADMIN_ID: return

    ticket_id = int(callback.data.split("_")[2])
    await close_ticket_logic(ticket_id, bot, callback.message)
    await callback.answer("Тикет закрыт")

async def close_ticket_logic(ticket_id: int, bot: Bot, admin_message: types.Message):
    async with new_session() as session:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            await admin_message.answer("❌ Тикет не найден.")
            return

        if ticket.status == TicketStatus.CLOSED:
            await admin_message.answer("⚠️ Тикет уже закрыт.")
            return

        ticket.status = TicketStatus.CLOSED
        ticket.closed_at = datetime.now()
        await session.commit()

        await admin_message.answer(f"✅ Тикет #{ticket_id} закрыт.")

        # Notify user
        try:
            await bot.send_message(ticket.user_id, f"✅ Ваша заявка #{ticket.daily_id} закрыта. Спасибо за обращение!")
        except:
            pass
