"""expand workout_exercise unique constraint to include exercise_index

Revision ID: b8f6323baaf4
Revises: f300f63fc4a0
Create Date: 2026-06-06 11:22:08.059095

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8f6323baaf4"
down_revision: str | Sequence[str] | None = "f300f63fc4a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop the old (workout_id, exercise_id) unique constraint and add
    a new one that also includes exercise_index, allowing the same
    exercise to appear at multiple positions in a workout.
    """
    op.drop_constraint(
        "workout_exercise_workout_id_exercise_id_key",
        "workout_exercise",
        type_="unique",
    )
    op.create_unique_constraint(
        None,
        "workout_exercise",
        ["workout_id", "exercise_id", "exercise_index"],
    )


def downgrade() -> None:
    """Restore the original (workout_id, exercise_id) unique constraint.

    NOTE: this downgrade will fail if any workout already contains the
    same exercise at two different exercise_index values, because the
    old constraint forbids that.  That is by design — the old schema
    could not represent the data, so the only safe down-migration is to
    delete those duplicate rows first.
    """
    op.drop_constraint(
        "workout_exercise_workout_id_exercise_id_exercise_index_key",
        "workout_exercise",
        type_="unique",
    )
    op.create_unique_constraint(
        None,
        "workout_exercise",
        ["workout_id", "exercise_id"],
    )
