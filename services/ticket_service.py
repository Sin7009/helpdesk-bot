from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from database.models import Ticket, TicketStatus, Message, SenderRole, User, SourceType

async def get_open_ticket(session: AsyncSession, user_id: int) -> Ticket | None:
    """
    Retrieves an active ticket for a specific user.

    This function checks if the user has any tickets with status 'new' or 'in_progress'.
    It assumes a user can only have one open ticket at a time as per the requirements.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The internal ID of the user.

    Returns:
        Ticket | None: The open ticket object if found, otherwise None.
    """
    stmt = select(Ticket).where(
        Ticket.user_id == user_id,
        Ticket.status.in_([TicketStatus.NEW, TicketStatus.IN_PROGRESS])
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def create_ticket(
    session: AsyncSession,
    user_id: int,
    source: SourceType,
    text: str
) -> Ticket:
    """
    Creates a new ticket and associates the initial message with it.

    This function creates a new Ticket record with 'new' status and uses the provided
    text as the 'question_text'. It then immediately calls `add_message_to_ticket`
    to save the first message in the conversation history.

    Args:
        session (AsyncSession): The database session.
        user_id (int): The internal ID of the user.
        source (SourceType): The platform source.
        text (str): The content of the initial message/question.

    Returns:
        Ticket: The newly created Ticket object.
    """
    ticket = Ticket(
        user_id=user_id,
        source=source,
        question_text=text,
        status=TicketStatus.NEW
    )
    session.add(ticket)
    await session.commit()
    await session.refresh(ticket)

    # Create the first message
    await add_message_to_ticket(session, ticket.id, text, SenderRole.USER)

    return ticket

async def add_message_to_ticket(
    session: AsyncSession,
    ticket_id: int,
    text: str,
    sender_role: SenderRole
) -> Message:
    """
    Adds a new message to an existing ticket's history.

    Args:
        session (AsyncSession): The database session.
        ticket_id (int): The ID of the ticket to attach the message to.
        text (str): The content of the message.
        sender_role (SenderRole): Whether the message is from a 'user' or 'admin'.

    Returns:
        Message: The newly created Message object.
    """
    message = Message(
        ticket_id=ticket_id,
        sender_role=sender_role,
        text=text
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message

async def get_ticket_by_id(session: AsyncSession, ticket_id: int) -> Ticket | None:
    """
    Retrieves a ticket by its ID, eagerly loading the associated User.

    This is primarily used by the admin reply logic to fetch ticket details
    and the user's external ID for routing the response.

    Args:
        session (AsyncSession): The database session.
        ticket_id (int): The ID of the ticket to retrieve.

    Returns:
        Ticket | None: The ticket object with user relation loaded, or None.
    """
    stmt = select(Ticket).options(selectinload(Ticket.user)).where(Ticket.id == ticket_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

async def close_ticket(session: AsyncSession, ticket_id: int) -> None:
    """
    Marks a ticket as 'closed'.

    Args:
        session (AsyncSession): The database session.
        ticket_id (int): The ID of the ticket to close.
    """
    stmt = update(Ticket).where(Ticket.id == ticket_id).values(status=TicketStatus.CLOSED)
    await session.execute(stmt)
    await session.commit()
