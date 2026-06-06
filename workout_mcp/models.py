"""SQLAlchemy ORM models for workout data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Routine(Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    workouts: Mapped[list[Workout]] = relationship(
        back_populates="routine", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Routine(id={self.id!r}, name={self.name!r})"


class Workout(Base):
    __tablename__ = "workout"

    id: Mapped[int] = mapped_column(primary_key=True)
    start: Mapped[datetime]
    end: Mapped[datetime]
    title: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)
    routine_id: Mapped[int] = mapped_column(ForeignKey("routine.id"))

    __table_args__ = (UniqueConstraint("routine_id", "start", "end"),)

    routine: Mapped[Routine] = relationship(back_populates="workouts")
    workout_exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="workout", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Workout(id={self.id!r}, start={self.start!r}, end={self.end!r})"


class Exercise(Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)

    workout_exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="exercise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Exercise(id={self.id!r}, name={self.name!r})"


class WorkoutExercise(Base):
    __tablename__ = "workout_exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_id: Mapped[int] = mapped_column(ForeignKey("workout.id"))
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercise.id"))
    exercise_index: Mapped[int]

    __table_args__ = (UniqueConstraint("workout_id", "exercise_id", "exercise_index"),)

    workout: Mapped[Workout] = relationship(back_populates="workout_exercises")
    exercise: Mapped[Exercise] = relationship(back_populates="workout_exercises")
    sets: Mapped[list[Set]] = relationship(
        back_populates="workout_exercise", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"WorkoutExercise(id={self.id!r}, exercise_index={self.exercise_index!r})"


class Set(Base):
    __tablename__ = "set"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_exercise_id: Mapped[int] = mapped_column(ForeignKey("workout_exercise.id"))
    set_index: Mapped[int]
    reps: Mapped[int | None] = mapped_column(default=None)
    weight: Mapped[float | None] = mapped_column(default=None)
    rpe: Mapped[float | None] = mapped_column(default=None)
    distance_km: Mapped[float | None] = mapped_column(default=None)
    duration_seconds: Mapped[float | None] = mapped_column(default=None)

    __table_args__ = (UniqueConstraint("workout_exercise_id", "set_index"),)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")

    def __repr__(self) -> str:
        return (
            f"Set(id={self.id!r}, set_index={self.set_index!r}, "
            f"reps={self.reps!r}, weight={self.weight!r}, "
            f"distance_km={self.distance_km!r}, duration_seconds={self.duration_seconds!r})"
        )


class SyncState(Base):
    __tablename__ = "sync_state"

    id: Mapped[int] = mapped_column(primary_key=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(default=None)
    updated_at: Mapped[datetime | None] = mapped_column(default=None)

    def __repr__(self) -> str:
        return f"SyncState(id={self.id!r}, last_sync_at={self.last_sync_at!r})"
