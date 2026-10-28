"""Tenancy tables. Levels are ordered integers: 0 none, 1 read, 2 run, 3 edit, 4 manage."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from mindgrid.db.base import Base, Keyed, Timestamped


def _values(members: type[enum.StrEnum]) -> list[str]:
    return [m.value for m in members]


# Table comment marking seeded reference data (kept by the per-test cleanup).
REFERENCE_DATA = "reference data: seeded by migrations"


class ProjectRole(enum.StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    ANALYST = "analyst"
    VIEWER = "viewer"
    GUEST = "guest"  # sees the project; categories only through explicit grants


class Level(enum.IntEnum):
    NONE = 0
    READ = 1
    RUN = 2
    EDIT = 3
    MANAGE = 4


_ROLE_ENUM = Enum(ProjectRole, name="project_role", values_callable=_values)


class RoleLevel(Base):
    """What each project role may do (seeded by the migration, editable as data)."""

    __tablename__ = "role_levels"
    __table_args__ = (
        CheckConstraint("default_category_level between 0 and 4", name="level_range"),
        {"comment": REFERENCE_DATA},
    )

    role: Mapped[ProjectRole] = mapped_column(_ROLE_ENUM, primary_key=True)
    manage_project: Mapped[bool] = mapped_column(Boolean)
    manage_members: Mapped[bool] = mapped_column(Boolean)
    default_category_level: Mapped[int] = mapped_column(SmallInteger)


class Project(Keyed, Timestamped, Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner_id", "slug", name="uq_projects_owner_slug"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[ProjectRole] = mapped_column(_ROLE_ENUM)


class Category(Keyed, Timestamped, Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_categories_project_slug"),)

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    # Restricted: role defaults do not apply; only owner/admin and explicit grants reach it.
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)


class CategoryGrant(Base):
    __tablename__ = "category_grants"
    __table_args__ = (CheckConstraint("level between 1 and 4", name="level_range"),)

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger)


class ProjectGroupRole(Base):
    """A group's role in a project: every member has it unless their own role is set."""

    __tablename__ = "project_group_roles"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[ProjectRole] = mapped_column(_ROLE_ENUM)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CategoryGroupGrant(Base):
    """A group's level in a category (a member's own grant wins)."""

    __tablename__ = "category_group_grants"
    __table_args__ = (CheckConstraint("level between 1 and 4", name="level"),)

    category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True
    )
    level: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
