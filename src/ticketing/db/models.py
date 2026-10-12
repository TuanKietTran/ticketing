from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Organizer(Base):
    __tablename__ = "organizers"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    api_key_hash: Mapped[str] = mapped_column(Text)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    organizer_id: Mapped[UUID] = mapped_column(ForeignKey("organizers.id"))
    name: Mapped[str] = mapped_column(Text)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    sale_opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sale_closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Section(Base):
    __tablename__ = "sections"
    __table_args__ = (CheckConstraint("held + sold <= capacity", name="inventory_not_oversold"),)
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    mode: Mapped[str] = mapped_column(String(32))
    capacity: Mapped[int] = mapped_column(Integer)
    held: Mapped[int] = mapped_column(Integer, default=0)
    sold: Mapped[int] = mapped_column(Integer, default=0)


class Hold(Base):
    __tablename__ = "holds"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    buyer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active")
    idempotency_key: Mapped[str] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("buyer_id", "idempotency_key"),)


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    actor_id: Mapped[str] = mapped_column(Text, primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    status_code: Mapped[int | None] = mapped_column(Integer)
    response_json: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Order(Base):
    __tablename__ = "orders"
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    event_id: Mapped[UUID] = mapped_column(ForeignKey("events.id"))
    buyer_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True))
    hold_id: Mapped[UUID] = mapped_column(ForeignKey("holds.id"), unique=True)
    state: Mapped[str] = mapped_column(String(32))
    total_minor: Mapped[int] = mapped_column(BigInteger)
