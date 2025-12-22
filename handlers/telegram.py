from aiogram import Router, F, Bot, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
import html

# --- ВАЖНО: Добавлен импорт get_active_ticket и add_message_to_ticket ---
from services.ticket_service import create_ticket, get_active_ticket, add_message_to_ticket
from services.faq_service import FAQService
from database.models import Ticket, TicketStatus, User, FAQ, SourceType, Category
from database.repositories.user_repository import UserRepository

from core.config import settings

router = Router()

class TicketForm(StatesGroup):
    waiting_text = State()

class ProfileForm(StatesGroup):
    waiting_student_id = State()
    waiting_department = State()
    waiting_course = State()
    # New fields
    waiting_group = State()
    waiting_role = State()

class Registration(StatesGroup):
    waiting_for_course = State()
    waiting_for_group = State()
    waiting_for_role = State()

class CommentForm(StatesGroup):
    waiting_comment = State()

# --- КЛАВИАТУРЫ ---
def get_menu_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎓 Учеба", callback_data="cat_study"),
         InlineKeyboardButton(text="📄 Справки", callback_data="cat_docs")],
        [InlineKeyboardButton(text="💻 IT / ЛК", callback_data="cat_it"),
         InlineKeyboardButton(text="🏠 Общежитие", callback_data="cat_dorm")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="show_faq")],
        [InlineKeyboardButton(text="📂 Мои заявки", callback_data="my_tickets")]
    ])

def get_back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def kb_courses():
    buttons = []
    # 2 rows of 3 buttons
    row1 = [InlineKeyboardButton(text=str(i), callback_data=str(i)) for i in range(1, 4)]
    row2 = [InlineKeyboardButton(text=str(i), callback_data=str(i)) for i in range(4, 7)]
    return InlineKeyboardMarkup(inline_keyboard=[row1, row2])

async def show_main_menu(message: types.Message):
    await message.answer(
        f"Привет, {html.escape(message.from_user.first_name)}! 👋\nВыберите тему обращения:",
        reply_markup=get_menu_kb()
    )

# --- ХЕНДЛЕРЫ ---

@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext, session: AsyncSession):
    await state.clear()

    # 1. Получаем юзера из базы
    repo = UserRepository(session)
    user = await repo.get_or_create(message.from_user)

    # 2. Проверяем заполненность профиля (группы)
    if not user.group_number:
        await message.answer(
            f"Привет, {html.escape(user.full_name or message.from_user.first_name)}! 👋\n"
            "Я вижу, мы еще не знакомы официально.\n\n"
            "<b>На каком ты курсе?</b>",
            reply_markup=kb_courses(),
            parse_mode="HTML"
        )
        await state.set_state(Registration.waiting_for_course)
    else:
        # Если профиль есть — сразу к делу
        await show_main_menu(message)

# --- REGISTRATION WIZARD ---

@router.callback_query(Registration.waiting_for_course)
async def process_course_callback(callback: types.CallbackQuery, state: FSMContext):
    # Handle course selection via button
    if not callback.data.isdigit():
        await callback.answer("Выберите курс кнопкой", show_alert=True)
        return

    course = int(callback.data)
    await state.update_data(course=course)
    await callback.message.edit_text(
        f"Выбрано: {course} курс.\n"
        "Отлично! А какая у тебя <b>группа</b>? (например, <i>ИВТ-201</i>)",
        parse_mode="HTML"
    )
    await state.set_state(Registration.waiting_for_group)
    await callback.answer()

@router.message(Registration.waiting_for_course)
async def process_course_text(message: types.Message, state: FSMContext):
    # Fallback if user types instead of clicking
    if not message.text.isdigit() or not (1 <= int(message.text) <= 6):
        await message.answer("Пожалуйста, выберите число от 1 до 6.", reply_markup=kb_courses())
        return

    await state.update_data(course=int(message.text))
    await message.answer("Отлично! А какая у тебя <b>группа</b>? (например, <i>ИВТ-201</i>)", parse_mode="HTML")
    await state.set_state(Registration.waiting_for_group)

@router.message(Registration.waiting_for_group)
async def process_group(message: types.Message, state: FSMContext):
    group = message.text.strip().upper()
    if len(group) > 20:
         await message.answer("Слишком длинное название группы. Попробуйте короче.")
         return

    await state.update_data(group=group)

    # Спрашиваем про старосту
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я староста ⭐", callback_data="role_head")],
        [InlineKeyboardButton(text="Просто студент 🎓", callback_data="role_student")]
    ])
    await message.answer(f"Группа: {html.escape(group)}\nПоследний вопрос: ты староста группы?", reply_markup=kb)
    await state.set_state(Registration.waiting_for_role)

@router.callback_query(Registration.waiting_for_role)
async def process_role(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    if callback.data not in ["role_head", "role_student"]:
        await callback.answer()
        return

    is_head = (callback.data == "role_head")
    data = await state.get_data()

    # СОХРАНЯЕМ В БАЗУ
    repo = UserRepository(session)
    await repo.update_profile(
        callback.from_user.id,
        course=data['course'],
        group=data['group'],
        is_head_student=is_head
    )

    await state.clear()
    await callback.message.edit_text("✅ Профиль заполнен! Теперь админы будут знать, кто им пишет.")
    await show_main_menu(callback.message)


# --- GENERAL HANDLERS ---

@router.callback_query(F.data == "show_faq")
async def show_faq(callback: types.CallbackQuery, session: AsyncSession):
    # Оптимизация: используем кэш вместо запроса к БД
    faqs = FAQService.get_all_faqs()

    if faqs:
        text = "\n".join([f"🔹 {f.trigger_word}: {f.answer_text}" for f in faqs])
    else:
        text = "База знаний пока пуста."

    # UX Improvement: Use edit_text to keep chat clean and provide a "Back" button
    await callback.message.edit_text(
        f"📚 <b>FAQ:</b>\n\n{text}",
        parse_mode="HTML",
        reply_markup=get_back_kb()
    )
    # Always answer callback to stop loading animation
    await callback.answer()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        f"Привет, {callback.from_user.first_name}! 👋\nВыберите тему обращения:",
        reply_markup=get_menu_kb()
    )

@router.callback_query(F.data.startswith("cat_"))
async def select_cat(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession, bot: Bot):
    # 1. Проверка активного тикета
    active_ticket = await get_active_ticket(session, callback.from_user.id, SourceType.TELEGRAM)
    if active_ticket:
        await callback.answer(
            f"⚠️ У вас уже есть активная заявка #{active_ticket.daily_id}.\n\n"
            "Просто напишите сообщение в чат, чтобы дополнить её.",
            show_alert=True
        )
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
    
    # Проверяем, сохранил ли пользователь текст заранее (из handle_text)
    data = await state.get_data()
    saved_text = data.get("saved_text")
    saved_media = data.get("saved_media") # dict with media_id, content_type

    if saved_text or saved_media:
        # Если контент уже есть — сразу создаем тикет
        text_to_use = saved_text if saved_text else ""
        media_id = saved_media.get("media_id") if saved_media else None
        content_type = saved_media.get("content_type") if saved_media else "text"

        t = await create_ticket(
            session, callback.from_user.id, SourceType.TELEGRAM,
            text_to_use, bot, category_name, callback.from_user.full_name,
            media_id=media_id, content_type=content_type
        )

        await callback.message.edit_text(
            f"✅ <b>Заявка #{t.daily_id} принята!</b>\n"
            f"Тема: {category_name}\n\n"
            f"🕒 Оператор ответит в рабочее время.\n"
            f"🔔 Вы получите уведомление об ответе.",
            parse_mode="HTML"
        )
        await state.clear()
        return

    # Исправлено: используем category_name, а не несуществующую category
    await state.update_data(category=category_name)
    await state.set_state(TicketForm.waiting_text)

    await callback.message.edit_text(
        f"Тема: <b>{category_name}</b>.\n✍️ Напишите ваш вопрос (можно прикрепить фото):",
        parse_mode="HTML",
        reply_markup=get_back_kb()
    )

# --- Media and Text Handlers ---

@router.message(F.text & ~F.text.startswith("/"))
@router.message(F.photo)
@router.message(F.document)
async def handle_message_content(message: types.Message, state: FSMContext, bot: Bot, session: AsyncSession):
    """Universal handler for text and media messages."""

    # 1. Ignore messages in staff chat
    if message.chat.id == settings.TG_STAFF_CHAT_ID:
        return

    # Extract content
    text = message.text or message.caption or ""
    media_id = None
    content_type = "text"

    if message.photo:
        content_type = "photo"
        media_id = message.photo[-1].file_id # Best quality
    elif message.document:
        content_type = "document"
        media_id = message.document.file_id

    # 2. Check FAQ (only for pure text messages)
    if content_type == "text" and text:
        faq = FAQService.find_match(text)
        if faq:
            await message.answer(f"🤖 <b>Подсказка:</b>\n{faq.answer_text}\n\nЕсли это не помогло, выберите категорию заново: /start", parse_mode="HTML")
            return

    # 3. Check for active ticket
    active_ticket = await get_active_ticket(session, message.from_user.id, SourceType.TELEGRAM)

    if active_ticket:
        # Add message to existing ticket
        await add_message_to_ticket(session, active_ticket, text, bot, media_id=media_id, content_type=content_type)
        await message.answer("✅ Сообщение добавлено к диалогу.")
        await state.clear()
        return

    # 4. If no ticket - check state for new ticket creation
    current_state = await state.get_state()

    # Check for Registration states (should not happen if flow is enforced, but good to catch)
    if current_state in [Registration.waiting_for_course, Registration.waiting_for_group, Registration.waiting_for_role]:
        # Let the specific handlers pick it up
        return

    if current_state == TicketForm.waiting_text:
        # Create new ticket
        data = await state.get_data()
        category = data.get("category", "Общее")

        t = await create_ticket(
            session, message.from_user.id, SourceType.TELEGRAM,
            text, bot, category, message.from_user.full_name,
            media_id=media_id, content_type=content_type
        )
        await message.answer(
            f"✅ <b>Заявка #{t.daily_id} принята!</b>\n\n"
            f"🕒 Оператор ответит в рабочее время.\n"
            f"🔔 Вы получите уведомление об ответе.",
            parse_mode="HTML"
        )
        await state.clear()
        return

    # 5. Если студент пишет сообщение без выбора меню — сохраняем его и просим выбрать тему
    # Check if registered first? No, handle_text might be triggered before start if user just types.
    # But if they type, we should check registration?
    # For now, let's keep it simple: if they type text without active ticket, we prompt menu.
    # The menu buttons will trigger /start logic or category selection which checks registration?
    # Actually, category selection DOES NOT check registration currently.
    # But /start does.

    await state.update_data(saved_text=message.text)

    await message.answer(
        "Я запомнил ваш вопрос! 📝\n"
        "Теперь выберите тему, чтобы я знал, кому его передать: 👇",
        reply_markup=get_menu_kb()
    )

# --- МОИ ЗАЯВКИ (My Tickets) ---

@router.callback_query(F.data == "my_tickets")
async def show_my_tickets(callback: types.CallbackQuery, session: AsyncSession):
    # Find user ID first to get internal ID
    result = await session.execute(select(User).where(User.external_id == callback.from_user.id))
    user = result.scalar_one_or_none()

    if not user:
         await callback.message.edit_text("У вас пока нет заявок.", reply_markup=get_back_kb())
         return

    # Fetch last 5 tickets
    stmt = select(Ticket).where(Ticket.user_id == user.id).order_by(desc(Ticket.created_at)).limit(5)
    result = await session.execute(stmt)
    tickets = result.scalars().all()

    if not tickets:
        await callback.message.edit_text("📂 <b>Список заявок пуст.</b>", parse_mode="HTML", reply_markup=get_back_kb())
        return

    kb_rows = []
    for t in tickets:
        status_emoji = {
            TicketStatus.NEW: "🟡",
            TicketStatus.IN_PROGRESS: "🟡",
            TicketStatus.CLOSED: "🟢"
        }.get(t.status, "⚪")

        btn_text = f"{status_emoji} №{t.daily_id}: {t.status.value}"
        kb_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"ticket_detail_{t.id}")])

    kb_rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])

    await callback.message.edit_text(
        "📂 <b>Мои заявки:</b>\nВыберите заявку для просмотра:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_rows)
    )

@router.callback_query(F.data.startswith("ticket_detail_"))
async def show_ticket_detail(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    t_id = int(callback.data.split("_")[-1])

    # Load ticket with category
    stmt = select(Ticket).options(selectinload(Ticket.category)).where(Ticket.id == t_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        await callback.answer("Заявка не найдена.")
        return

    # Check ownership
    user_res = await session.execute(select(User).where(User.external_id == callback.from_user.id))
    user = user_res.scalar_one_or_none()
    if not user or ticket.user_id != user.id:
        await callback.answer("Это не ваша заявка.")
        return

    cat_name = ticket.category.name if ticket.category else "Без категории"
    date_str = ticket.created_at.strftime("%d.%m.%Y %H:%M")

    status_text = {
        TicketStatus.NEW: "Новая",
        TicketStatus.IN_PROGRESS: "В работе",
        TicketStatus.CLOSED: "Закрыта"
    }.get(ticket.status, ticket.status)

    text = (
        f"🎫 <b>Заявка #{ticket.daily_id}</b>\n"
        f"📅 Дата: {date_str}\n"
        f"📂 Категория: {cat_name}\n"
        f"📊 Статус: <b>{status_text}</b>\n\n"
        f"📝 <b>Вопрос:</b>\n{ticket.question_text}\n"
    )

    if ticket.summary:
        text += f"\n📋 <b>Итог:</b>\n{ticket.summary}\n"

    # Buttons
    btns = []
    # Allow adding comment/re-opening
    btns.append([InlineKeyboardButton(text="💬 Добавить комментарий", callback_data=f"add_comment_{t_id}")])
    btns.append([InlineKeyboardButton(text="🔙 К списку", callback_data="my_tickets")])

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@router.callback_query(F.data.startswith("add_comment_"))
async def add_comment_ask(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    t_id = int(callback.data.split("_")[-1])

    # Verify ticket exists and belongs to user (security check)
    stmt = select(Ticket).where(Ticket.id == t_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    # We also need user_id check here, but assuming context from prev step or re-checking
    user_res = await session.execute(select(User).where(User.external_id == callback.from_user.id))
    user = user_res.scalar_one_or_none()

    if not ticket or not user or ticket.user_id != user.id:
        await callback.answer("Ошибка доступа.", show_alert=True)
        return

    await state.update_data(comment_ticket_id=t_id)
    await state.set_state(CommentForm.waiting_comment)

    await callback.message.edit_text(
        f"✍️ Напишите ваш комментарий к заявке #{ticket.daily_id}.\n"
        "Если заявка закрыта, она будет открыта заново.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"ticket_detail_{t_id}")]
        ])
    )

@router.message(CommentForm.waiting_comment)
async def process_comment(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    data = await state.get_data()
    t_id = data.get("comment_ticket_id")

    if not t_id:
        await message.answer("Ошибка состояния. Попробуйте снова /start")
        await state.clear()
        return

    # Load ticket with relationships
    stmt = select(Ticket).options(selectinload(Ticket.user), selectinload(Ticket.category)).where(Ticket.id == t_id)
    result = await session.execute(stmt)
    ticket = result.scalar_one_or_none()

    if ticket:
        # Extract content
        text = message.text or message.caption or ""
        media_id = None
        content_type = "text"

        if message.photo:
            content_type = "photo"
            media_id = message.photo[-1].file_id
        elif message.document:
            content_type = "document"
            media_id = message.document.file_id

        await add_message_to_ticket(
            session, ticket, text, bot,
            media_id=media_id, content_type=content_type
        )

        await message.answer(f"✅ Комментарий добавлен к заявке #{ticket.daily_id}.")
    else:
        await message.answer("❌ Заявка не найдена.")

    await state.clear()
    # Optionally show the ticket details again?
    # await show_ticket_detail_logic... (too complex to call directly without callback structure, so just stop here)


# --- ПРОФИЛЬ СТУДЕНТА ---

@router.message(Command("myprofile"))
async def cmd_myprofile(message: types.Message, session: AsyncSession):
    """Show current student profile information."""
    result = await session.execute(
        select(User).where(
            User.external_id == message.from_user.id,
            User.source == SourceType.TELEGRAM
        ).limit(1)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer(
            "Ваш профиль еще не создан. Создайте первую заявку, чтобы начать!\n"
            "Используйте /start"
        )
        return
    
    # Format profile information
    profile_lines = [
        "👤 <b>Ваш профиль:</b>\n",
        f"Имя: {html.escape(user.full_name or 'Не указано')}"
    ]
    
    if user.student_id:
        profile_lines.append(f"Студ. билет: {html.escape(user.student_id)}")
    else:
        profile_lines.append("Студ. билет: <i>не указан</i>")
    
    if user.course:
        profile_lines.append(f"Курс: {user.course}")
    else:
        profile_lines.append("Курс: <i>не указан</i>")

    if user.group_number:
        profile_lines.append(f"Группа: {html.escape(user.group_number)}")
    else:
         profile_lines.append("Группа: <i>не указана</i>")

    role_str = "⭐ Староста" if user.is_head_student else "🎓 Студент"
    profile_lines.append(f"Статус: {role_str}")
    
    if user.department:
        profile_lines.append(f"Факультет/Институт: {html.escape(user.department)}")
    else:
        profile_lines.append("Факультет/Институт: <i>не указан</i>")
    
    profile_lines.append("\n<i>Для обновления профиля используйте /updateprofile</i>")
    
    await message.answer(
        "\n".join(profile_lines),
        parse_mode="HTML"
    )

@router.message(Command("updateprofile"))
async def cmd_updateprofile(message: types.Message, state: FSMContext, session: AsyncSession):
    """Start profile update process."""
    # Ensure user exists
    result = await session.execute(
        select(User).where(
            User.external_id == message.from_user.id,
            User.source == SourceType.TELEGRAM
        ).limit(1)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        await message.answer(
            "Ваш профиль еще не создан. Создайте первую заявку, чтобы начать!\n"
            "Используйте /start"
        )
        return
    
    await state.set_state(ProfileForm.waiting_student_id)
    await message.answer(
        "📝 <b>Обновление профиля</b>\n\n"
        "Введите номер студенческого билета (или '-' чтобы пропустить):",
        parse_mode="HTML"
    )

@router.message(ProfileForm.waiting_student_id)
async def process_student_id(message: types.Message, state: FSMContext):
    """Process student ID input."""
    student_id = message.text.strip()
    if student_id == '-':
        student_id = None
    
    await state.update_data(student_id=student_id)
    await state.set_state(ProfileForm.waiting_course)
    await message.answer(
        "Введите ваш курс (1-6) или '-' чтобы пропустить:"
    )

@router.message(ProfileForm.waiting_course)
async def process_course_update(message: types.Message, state: FSMContext):
    """Process course input."""
    course_text = message.text.strip()
    course = None
    
    if course_text != '-':
        try:
            course = int(course_text)
            if course < 1 or course > 6:
                await message.answer("❌ Курс должен быть от 1 до 6. Попробуйте еще раз:")
                return
        except ValueError:
            await message.answer("❌ Введите число от 1 до 6, или '-' чтобы пропустить:")
            return
    
    await state.update_data(course=course)
    await state.set_state(ProfileForm.waiting_group)
    await message.answer(
        "Введите вашу группу (или '-' чтобы пропустить):"
    )

@router.message(ProfileForm.waiting_group)
async def process_group_update(message: types.Message, state: FSMContext):
    group = message.text.strip()
    if group == '-':
        group = None
    else:
        group = group.upper()
        if len(group) > 20:
             await message.answer("Слишком длинное название группы. Попробуйте короче.")
             return

    await state.update_data(group=group)

    # Ask for role
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Я староста ⭐", callback_data="role_head")],
        [InlineKeyboardButton(text="Просто студент 🎓", callback_data="role_student")],
        [InlineKeyboardButton(text="Не менять 🚫", callback_data="role_skip")]
    ])
    await message.answer("Вы староста группы?", reply_markup=kb)
    await state.set_state(ProfileForm.waiting_role)

@router.callback_query(ProfileForm.waiting_role)
async def process_role_update(callback: types.CallbackQuery, state: FSMContext, session: AsyncSession):
    is_head = None
    if callback.data == "role_head":
        is_head = True
    elif callback.data == "role_student":
        is_head = False
    # if role_skip, is_head remains None

    await state.update_data(is_head=is_head)
    await state.set_state(ProfileForm.waiting_department)

    # We continue to department to match the old flow?
    # Or just jump to department?
    # The original flow had Department AFTER Course.
    # My new flow inserted Group and Role after Course.

    await callback.message.edit_text(
        "Введите название вашего факультета/института (или '-' чтобы пропустить):"
    )

@router.message(ProfileForm.waiting_department)
async def process_department(message: types.Message, state: FSMContext, session: AsyncSession):
    """Process department input and save profile."""
    department = message.text.strip()
    if department == '-':
        department = None
    
    # Get all collected data
    data = await state.get_data()
    student_id = data.get('student_id')
    course = data.get('course')
    group = data.get('group')
    is_head = data.get('is_head')
    
    # Use UserRepository to get user, then update all fields in one transaction
    repo = UserRepository(session)
    user = await repo.get_by_external_id(message.from_user.id, SourceType.TELEGRAM)
    
    if user:
        if course is not None:
            user.course = course
        if group is not None:
            user.group_number = group
        if is_head is not None:
            user.is_head_student = is_head

        user.department = department
        user.student_id = student_id

        await session.commit()
        
        await message.answer(
            "✅ <b>Профиль успешно обновлен!</b>\n\n"
            "Теперь сотрудники поддержки будут видеть вашу информацию при обработке заявок.\n"
            "Используйте /myprofile чтобы посмотреть ваш профиль.",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Ошибка при обновлении профиля. Попробуйте позже.")
    
    await state.clear()
