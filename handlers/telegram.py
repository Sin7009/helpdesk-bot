from aiogram import Router, F, Bot, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# --- ВАЖНО: Добавлен импорт get_active_ticket и add_message_to_ticket ---
from services.ticket_service import create_ticket, get_active_ticket, add_message_to_ticket
from services.faq_service import FAQService
from database.models import Ticket, TicketStatus, User, FAQ, SourceType, Category

from core.config import settings

router = Router()

class TicketForm(StatesGroup):
    waiting_text = State()

# --- КЛАВИАТУРЫ ---
# (Оставляем пока хардкод для надежности, раз вы его вернули)
def get_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_study"),
         InlineKeyboardButton(text="📄 Справки", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / ЛК", callback_data="cat_it"),
         InlineKeyboardButton(text="🏠 Общежитие", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq")]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
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
async def show_faq(callback: types.CallbackQuery, session: AsyncSession):
    # Оптимизация: используем кэш вместо запроса к БД
    faqs = FAQService.get_all_faqs()

    if faqs:
        text = "\n".join([f"🔹 {f.trigger_word}: {f.answer_text}" for f in faqs])
    else:
        text = "База знаний пока пуста."

    await callback.message.answer(f"📚 <b>FAQ:</b>\n\n{text}", parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"Привет, {callback.from_user.first_name}! 👋\nВыберите тему обращения:",
        reply_markup=get_menu_kb()
    )

@router.callback_query(F.data.startswith("cat_"))
async def select_cat(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    # 1. Проверка активного тикета
    active_ticket = await get_active_ticket(session, callback.from_user.id, SourceType.TELEGRAM)
    if active_ticket:
        await callback.answer("⚠️ У вас уже есть открытый диалог. Дождитесь ответа или закройте его.", show_alert=True)
        return

    # 2. Определение категории
    cat_map = {
        "cat_study": "Учеба",
        "cat_docs": "Справки",
        "cat_it": "IT",
        "cat_dorm": "Общежитие"
    }
    # Исправлено: получаем имя категории из словаря или берем хвост строки
    category_name = cat_map.get(callback.data, "Общее")
    
    # Исправлено: используем category_name, а не несуществующую category
    await state.update_data(category=category_name)
    await state.set_state(TicketForm.waiting_text)

    await callback.message.edit_text(
        f"Тема: <b>{category_name}</b>.\n✍️ Напишите ваш вопрос:",
        parse_mode="HTML",
        reply_markup=get_back_kb()
    )

@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: types.Message, state: FSMContext, bot: Bot, session: AsyncSession):
    # 1. Игнорируем сообщения в чате сотрудников
    if message.chat.id == settings.TG_STAFF_CHAT_ID:
        return

    # 2. Проверка FAQ (Оптимизация: используем кэш)
    faq = FAQService.find_match(message.text)
    if faq:
        await message.answer(f"🤖 <b>Подсказка:</b>\n{faq.answer_text}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
        return

    # 3. Проверка на активный тикет (добавление сообщения)
    active_ticket = await get_active_ticket(session, message.from_user.id, SourceType.TELEGRAM)

    if active_ticket:
        # Если есть тикет — просто добавляем сообщение
        await add_message_to_ticket(session, active_ticket, message.text, bot)
        await message.answer("✅ Сообщение добавлено к диалогу.")
        # Сбрасываем состояние, если вдруг оно зависло
        await state.clear()
        return

    # 4. Если тикета нет — проверяем создание нового
    current_state = await state.get_state()

    if current_state == TicketForm.waiting_text:
        # Создание нового тикета
        data = await state.get_data()
        category = data.get("category", "Общее")

        t = await create_ticket(session, message.from_user.id, SourceType.TELEGRAM, message.text, bot, category, message.from_user.full_name)
        await message.answer(f"✅ <b>Заявка #{t.daily_id} принята!</b>", parse_mode="HTML")
        await state.clear()
        return

    # 5. Если студент пишет "Привет" без выбора меню
    await message.answer(
        "Чтобы задать вопрос, выберите категорию:",
        reply_markup=get_menu_kb()
    )
