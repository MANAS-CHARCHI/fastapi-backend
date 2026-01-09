from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Boolean,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
if TYPE_CHECKING:
    from apps.users.models import Users
from apps.db.base import Base

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)

    owner_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    owner: Mapped["Users"] = relationship(
        "Users",
        back_populates="projects",
    )

    versions: Mapped[List["ProjectVersion"]] = relationship(
        "ProjectVersion",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectVersion(Base):
    __tablename__ = "project_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id"),
        nullable=False,
    )

    version: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    project: Mapped["Project"] = relationship(
        "Project",
        back_populates="versions",
    )
