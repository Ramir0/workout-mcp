"""SQLAlchemy ORM models for workout data."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Routine(Base):
    __tablename__ = "routine"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

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
    routine_id: Mapped[int] = mapped_column(ForeignKey("routine.id"))

    routine: Mapped[Routine] = relationship(back_populates="workouts")
    workout_exercises: Mapped[list[WorkoutExercise]] = relationship(
        back_populates="workout", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"Workout(id={self.id!r}, start={self.start!r}, end={self.end!r})"


class Exercise(Base):
    __tablename__ = "exercise"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

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
    reps: Mapped[int]
    weight: Mapped[float]
    rpe: Mapped[float | None] = mapped_column(default=None)

    workout_exercise: Mapped[WorkoutExercise] = relationship(back_populates="sets")

    def __repr__(self) -> str:
        return (
            f"Set(id={self.id!r}, set_index={self.set_index!r}, "
            f"reps={self.reps!r}, weight={self.weight!r})"
        )
