from sqlalchemy import  DateTime, ForeignKey, Integer, String, Boolean, event, Uuid
from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column, DeclarativeBase
import uuid
from sqlalchemy.sql import func
from sqlalchemy import insert

class Base(DeclarativeBase):
    pass

class Users(Base):
    __tablename__ = "users"

    id:Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, index=True, default=uuid.uuid7)
    email:Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password:Mapped[str] = mapped_column(String, nullable=False)
    is_active:Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    activations : Mapped["Activations"] = relationship("Activations", back_populates="user", cascade="all, delete-orphan")

class Activations(Base):
    __tablename__ = "activations"

    id:Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id:Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    activation_code:Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    is_used:Mapped[bool] = mapped_column(Boolean, default=False)
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user:Mapped["Users"] = relationship("Users", back_populates="activations")

@event.listens_for(Users, 'after_insert')
def create_activation_token(mapper, connection, target):
    # 'insert' must be imported from sqlalchemy
    stmt = insert(Activations.__table__).values(
        user_id=target.id, 
        activation_code=str(uuid.uuid4())
    )
    connection.execute(stmt)

class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id:Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    jti:Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    created_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at:Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    user_id:Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False, default=uuid.uuid4)

    user:Mapped["Users"] = relationship("Users")