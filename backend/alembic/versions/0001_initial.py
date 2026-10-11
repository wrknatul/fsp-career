"""Initial schema: all tables of SPEC section 5.

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('candidate', 'employer')", name=op.f("ck_users_role")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("birth_date", sa.Date(), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("work_formats", sa.JSON(), nullable=False),
        sa.Column("relocation", sa.Boolean(), nullable=False),
        sa.Column("salary_expectation", sa.Integer(), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("telegram", sa.String(length=64), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("visible", sa.Boolean(), nullable=False),
        sa.Column("fsp_id", sa.String(length=64), nullable=True),
        sa.Column("fsp_linked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fsp_region", sa.String(length=200), nullable=True),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("resume_filename", sa.String(length=255), nullable=True),
        sa.Column("resume_parsed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("category", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("embedding", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_candidates_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_candidates")),
        sa.UniqueConstraint("user_id", name=op.f("uq_candidates_user_id")),
        sa.UniqueConstraint("fsp_id", name=op.f("uq_candidates_fsp_id")),
    )
    op.create_index(op.f("ix_candidates_visible"), "candidates", ["visible"], unique=False)

    op.create_table(
        "employers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("website", sa.String(length=300), nullable=True),
        sa.Column("contact_name", sa.String(length=200), nullable=True),
        sa.Column("contact_email", sa.String(length=254), nullable=True),
        sa.Column("contact_telegram", sa.String(length=64), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_employers_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_employers")),
        sa.UniqueConstraint("user_id", name=op.f("uq_employers_user_id")),
    )

    op.create_table(
        "profile_facts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("verification", sa.String(length=16), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_profile_facts_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_facts")),
        sa.UniqueConstraint(
            "candidate_id",
            "kind",
            "key",
            "source",
            name=op.f("uq_profile_facts_candidate_kind_key_source"),
        ),
    )

    op.create_table(
        "test_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("skill", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("answers", sa.JSON(none_as_null=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_test_sessions_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_test_sessions")),
    )
    op.create_index(
        "ix_test_sessions_candidate_id_skill",
        "test_sessions",
        ["candidate_id", "skill"],
        unique=False,
    )

    op.create_table(
        "link_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_link_attempts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_link_attempts")),
    )
    op.create_index(
        "ix_link_attempts_user_id_created_at",
        "link_attempts",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "vacancies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employer_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("stack", sa.String(length=16), nullable=False),
        sa.Column("grade", sa.String(length=16), nullable=False),
        sa.Column("team_role", sa.String(length=16), nullable=True),
        sa.Column("skills_required", sa.JSON(), nullable=False),
        sa.Column("skills_optional", sa.JSON(), nullable=False),
        sa.Column("work_formats", sa.JSON(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("salary_from", sa.Integer(), nullable=True),
        sa.Column("salary_to", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employers.id"],
            name=op.f("fk_vacancies_employer_id_employers"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vacancies")),
    )
    op.create_index(op.f("ix_vacancies_employer_id"), "vacancies", ["employer_id"], unique=False)

    op.create_table(
        "offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("employer_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("vacancy_id", sa.Integer(), nullable=False),
        sa.Column("salary", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("candidate_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('sent', 'accepted', 'declined')", name=op.f("ck_offers_status")
        ),
        sa.CheckConstraint("salary > 0", name=op.f("ck_offers_salary_positive")),
        sa.ForeignKeyConstraint(
            ["employer_id"],
            ["employers.id"],
            name=op.f("fk_offers_employer_id_employers"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            name=op.f("fk_offers_candidate_id_candidates"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vacancy_id"],
            ["vacancies.id"],
            name=op.f("fk_offers_vacancy_id_vacancies"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_offers")),
        sa.UniqueConstraint("vacancy_id", "candidate_id", name=op.f("uq_offers_vacancy_candidate")),
    )
    op.create_index(op.f("ix_offers_employer_id"), "offers", ["employer_id"], unique=False)
    op.create_index(op.f("ix_offers_candidate_id"), "offers", ["candidate_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_offers_candidate_id"), table_name="offers")
    op.drop_index(op.f("ix_offers_employer_id"), table_name="offers")
    op.drop_table("offers")
    op.drop_index(op.f("ix_vacancies_employer_id"), table_name="vacancies")
    op.drop_table("vacancies")
    op.drop_index("ix_link_attempts_user_id_created_at", table_name="link_attempts")
    op.drop_table("link_attempts")
    op.drop_index("ix_test_sessions_candidate_id_skill", table_name="test_sessions")
    op.drop_table("test_sessions")
    op.drop_table("profile_facts")
    op.drop_table("employers")
    op.drop_index(op.f("ix_candidates_visible"), table_name="candidates")
    op.drop_table("candidates")
    op.drop_table("users")
