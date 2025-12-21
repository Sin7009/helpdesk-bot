import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    pass

class SourceType(str, PyEnum):
    TELEGRAM = "tg"
    VK = "vk"

class TicketStatus(str, PyEnum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    CLOSED = "closed"

class TicketPriority(str, PyEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class SenderRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"

class UserRole(str, PyEnum):
    USER = "user"
    MODERATOR = "moderator"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[SourceType] = mapped_column(String(10))
    external_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(String(20), default=UserRole.USER)
    
    # University-specific fields
    student_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    course: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        foreign_keys="[Ticket.user_id]",
        back_populates="user"
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket", 
        foreign_keys="[Ticket.assigned_to]",
        back_populates="assigned_staff"
    )

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category")

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    # daily_id: Integer, reset every day. Needs logic to handle this, likely not auto-increment in DB but calculated in code.
    daily_id: Mapped[int] = mapped_column(Integer, default=0)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    source: Mapped[SourceType] = mapped_column(String(10))
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[TicketStatus] = mapped_column(String(20), default=TicketStatus.NEW, index=True)
    priority: Mapped[TicketPriority] = mapped_column(String(10), default=TicketPriority.NORMAL, index=True)
    
    # SLA tracking
    first_response_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    closed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    # Student satisfaction
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    satisfaction_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="tickets")
    assigned_staff: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_tickets")
    category: Mapped["Category"] = relationship(back_populates="tickets")
    messages: Mapped[list["Message"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    sender_role: Mapped[SenderRole] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")

class FAQ(Base):
    __tablename__ = "faq"

    id: Mapped[int] = mapped_column(primary_key=True)
    trigger_word: Mapped[str] = mapped_column(String(255), unique=True)
    answer_text: Mapped[str] = mapped_column(Text)

class DailyTicketCounter(Base):
    """Counter table for atomic daily_id generation.
    
    This table ensures that daily_id values are generated atomically
    to prevent race conditions when multiple tickets are created simultaneously.
    Each row represents a counter for a specific date.
    """
    __tablename__ = "daily_ticket_counter"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[datetime.date] = mapped_column(unique=True, index=True)
    counter: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
