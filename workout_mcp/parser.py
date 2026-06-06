"""Hevy CSV export parser."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import TextIO


@dataclass
class ParsedSet:
    set_index: int
    reps: int | None
    weight: float | None
    rpe: float | None
    distance_km: float | None
    duration_seconds: float | None
    source_row: int  # CSV row number (1-indexed, including header)


@dataclass
class ParsedExercise:
    name: str
    exercise_index: int
    sets: list[ParsedSet]


@dataclass
class ParsedWorkout:
    start: datetime
    end: datetime
    exercises: list[ParsedExercise]


@dataclass
class ParsedRoutine:
    name: str
    workouts: list[ParsedWorkout]


class ParseError(Exception):
    """Base class for parser errors."""


class EmptyCSVError(ParseError):
    """Raised when the CSV has no data rows."""


class MissingColumnError(ParseError):
    """Raised when required columns are missing."""


class MalformedDateError(ParseError):
    """Raised when a date cannot be parsed."""


class InvalidValueError(ParseError):
    """Raised when a field value is invalid."""


_REQUIRED_COLUMNS = {
    "title",
    "start_time",
    "end_time",
    "exercise_title",
    "set_index",
}


def _parse_datetime(value: str) -> datetime:
    stripped = value.strip()
    try:
        return datetime.strptime(stripped, "%b %d, %Y, %I:%M %p")
    except ValueError as exc:
        raise MalformedDateError(f"Unable to parse date: {stripped!r}") from exc


def _parse_int(value: str, field: str) -> int:
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be an integer, got: {stripped!r}") from exc


def _parse_float(value: str, field: str) -> float:
    stripped = value.strip()
    try:
        return float(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be a number, got: {stripped!r}") from exc


def _parse_optional_float(value: str, field: str) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return float(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be a number or empty, got: {stripped!r}") from exc


def _parse_optional_int(value: str, field: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise InvalidValueError(f"{field} must be an integer or empty, got: {stripped!r}") from exc


def parse_hevy_csv(source: TextIO) -> list[ParsedRoutine]:
    """Parse a Hevy CSV export into a nested workout structure."""
    content = source.read()
    if content.startswith("\ufeff"):
        content = content.removeprefix("\ufeff")
    reader = csv.DictReader(io.StringIO(content))

    if reader.fieldnames is None:
        raise EmptyCSVError("CSV has no header row")

    missing = _REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise MissingColumnError(f"Missing required columns: {', '.join(sorted(missing))}")

    rows = list(reader)
    if not rows:
        raise EmptyCSVError("CSV contains no data rows")

    # Tag each row with its CSV row number (1-indexed, header = row 1)
    for row_num, row in enumerate(rows, start=2):
        row["_row_num"] = row_num

    # Group rows by (routine_name, start, end)
    workout_groups: dict[tuple[str, datetime, datetime], list[dict[str, str]]] = {}
    for row in rows:
        routine_name = row["title"].strip()
        if not routine_name:
            raise InvalidValueError("title cannot be empty")

        start = _parse_datetime(row["start_time"])
        end = _parse_datetime(row["end_time"])

        key = (routine_name, start, end)
        workout_groups.setdefault(key, []).append(row)

    # Build nested structure
    routines: dict[str, ParsedRoutine] = {}
    for (routine_name, start, end), workout_rows in workout_groups.items():
        # Track exercise occurrences in first-appearance order.  The same
        # exercise name may appear at multiple positions in a routine; each
        # occurrence becomes its own ParsedExercise with a unique
        # exercise_index.
        occurrence_keys: list[tuple[str, int]] = []
        occurrence_index: dict[str, int] = {}
        for row in workout_rows:
            ex_name = row["exercise_title"].strip()
            if not ex_name:
                raise InvalidValueError("exercise_title cannot be empty")
            if ex_name not in occurrence_index:
                occurrence_index[ex_name] = 0
                occurrence_keys.append((ex_name, 0))
            else:
                occurrence_index[ex_name] += 1
                occurrence_keys.append((ex_name, occurrence_index[ex_name]))

        # Group rows by (exercise_name, occurrence_index)
        occurrence_groups: dict[tuple[str, int], list[dict[str, str]]] = {}
        for row, occ_key in zip(workout_rows, occurrence_keys, strict=True):
            occurrence_groups.setdefault(occ_key, []).append(row)

        parsed_exercises: list[ParsedExercise] = []
        for exercise_index, occ_key in enumerate(occurrence_keys):
            ex_name, _occ = occ_key
            ex_rows = occurrence_groups[occ_key]
            sets: list[ParsedSet] = []
            for row in ex_rows:
                set_index = _parse_int(row["set_index"], "set_index")

                weight = _parse_optional_float(row.get("weight_kg", ""), "weight_kg")
                reps = _parse_optional_int(row.get("reps", ""), "reps")
                distance_km = _parse_optional_float(row.get("distance_km", ""), "distance_km")
                duration_seconds_raw = row.get("duration_seconds", "").strip()
                # Hevy CSV exports write "0" for duration_seconds on non-cardio sets;
                # treat this placeholder as absent rather than zero seconds.
                duration_seconds = (
                    _parse_optional_float(duration_seconds_raw, "duration_seconds")
                    if duration_seconds_raw != "0"
                    else None
                )

                if all(v is None for v in (weight, reps, distance_km, duration_seconds)):
                    raise InvalidValueError(
                        "At least one of weight_kg, reps, distance_km, or duration_seconds must be provided"
                    )

                if weight is not None and weight < 0:
                    raise InvalidValueError(f"weight_kg must be non-negative, got {weight}")
                if reps is not None and reps < 0:
                    raise InvalidValueError(f"reps must be non-negative, got {reps}")
                if distance_km is not None and distance_km < 0:
                    raise InvalidValueError(f"distance_km must be non-negative, got {distance_km}")
                if duration_seconds is not None and duration_seconds < 0:
                    raise InvalidValueError(
                        f"duration_seconds must be non-negative, got {duration_seconds}"
                    )

                rpe = _parse_optional_float(row.get("rpe", ""), "rpe")
                if rpe is not None and (rpe < 1 or rpe > 10):
                    raise InvalidValueError(f"rpe must be between 1 and 10, got {rpe}")

                sets.append(
                    ParsedSet(
                        set_index=set_index,
                        reps=reps,
                        weight=weight,
                        rpe=rpe,
                        distance_km=distance_km,
                        duration_seconds=duration_seconds,
                        source_row=int(row["_row_num"]),
                    )
                )

            parsed_exercises.append(
                ParsedExercise(
                    name=ex_name,
                    exercise_index=exercise_index,
                    sets=sets,
                )
            )

        workout = ParsedWorkout(
            start=start,
            end=end,
            exercises=parsed_exercises,
        )

        if routine_name not in routines:
            routines[routine_name] = ParsedRoutine(
                name=routine_name,
                workouts=[workout],
            )
        else:
            routines[routine_name].workouts.append(workout)

    return list(routines.values())
