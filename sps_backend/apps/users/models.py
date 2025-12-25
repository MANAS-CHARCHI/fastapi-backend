from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Boolean, event
from datetime import datetime
from sqlalchemy.orm import relationship, Mapped, mapped_column, DeclarativeBase
import uuid
from sqlalchemy.sql import func
from sqlalchemy import insert

class Base(DeclarativeBase):
    pass

class Users(Base):
    __tablename__ = "users"

    id:Mapped[int] = Column(Integer, primary_key=True, index=True)
    email:Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    password:Mapped[str] = Column(String, nullable=False)
    is_active:Mapped[bool] = Column(Boolean, default=True)
    created_at:Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at:Mapped[datetime] = Column(DateTime(timezone=True), onupdate=func.now())
    activations : Mapped["Activations"] = relationship("Activations", back_populates="user", cascade="all, delete-orphan")

class Activations(Base):
    __tablename__ = "activations"

    id:Mapped[int] = Column(Integer, primary_key=True, index=True)
    user_id:Mapped[int] = Column(Integer, ForeignKey("users.id"), nullable=False)
    activation_code:Mapped[str] = Column(String, unique=True, index=True, nullable=False)
    is_used:Mapped[bool] = Column(Boolean, default=False)
    created_at:Mapped[datetime] = Column(DateTime(timezone=True), server_default=func.now())
    updated_at:Mapped[datetime] = Column(DateTime(timezone=True), onupdate=func.now())

    user:Mapped["Users"] = relationship("Users", back_populates="activations")

@event.listens_for(Users, 'after_insert')
def create_activation_token(mapper, connection, target):
    # 'insert' must be imported from sqlalchemy
    stmt = insert(Activations.__table__).values(
        user_id=target.id, 
        activation_code=str(uuid.uuid4())
    )
    connection.execute(stmt)