import datetime
from enum import Enum as PyEnum
from typing import Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, DateTime, func
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

class SenderRole(str, PyEnum):
    USER = "user"
    ADMIN = "admin"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[SourceType] = mapped_column(String(10))
    external_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="user")

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source: Mapped[SourceType] = mapped_column(String(10)) # Redundant but requested
    question_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(String(20), default=TicketStatus.NEW)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tickets")
    messages: Mapped[list["Message"]] = relationship(back_populates="ticket", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"))
    sender_role: Mapped[SenderRole] = mapped_column(String(10))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="messages")
