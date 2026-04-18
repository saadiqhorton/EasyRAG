"""Initial schema migration

Creates all tables for the RAG Knowledge Base:
- collections
- source_documents
- document_versions
- chunks
- derived_assets
- ingestion_jobs
- failure_events
- query_sessions
- answer_records

Revision ID: 001_initial
Revises:
Create Date: 2026-04-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables."""
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False, index=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "source_documents",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("collection_id", sa.Uuid, sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("source_uri", sa.String(1024), nullable=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "document_versions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("document_id", sa.Uuid, sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("parse_confidence", sa.Float, nullable=True),
        sa.Column("index_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        sa.Index("ix_document_versions_active", "document_id", "is_active"),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collection_id", sa.Uuid, nullable=False, index=True),
        sa.Column("document_id", sa.Uuid, nullable=False, index=True),
        sa.Column("order_index", sa.Integer, nullable=False),
        sa.Column("title", sa.String(512), nullable=True),
        sa.Column("section_path", sa.String(1024), nullable=True),
        sa.Column("page_number_start", sa.Integer, nullable=True),
        sa.Column("page_number_end", sa.Integer, nullable=True),
        sa.Column("modality", sa.String(20), nullable=False, server_default="text"),
        sa.Column("confidence", sa.Float, nullable=False, server_default=sa.text("1.0")),
        sa.Column("token_count", sa.Integer, nullable=False),
        sa.Column("text_content", sa.Text, nullable=False),
        sa.Index("ix_chunks_collection_order", "collection_id", "order_index"),
        sa.Index("ix_chunks_version", "version_id"),
    )

    op.create_table(
        "derived_assets",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("asset_type", sa.String(50), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("collection_id", sa.Uuid, sa.ForeignKey("collections.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version_id", sa.Uuid, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued", index=True),
        sa.Column("current_stage", sa.String(20), nullable=True),
        sa.Column("retry_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("chunks_total", sa.Integer, nullable=True),
        sa.Column("chunks_processed", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "failure_events",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("job_id", sa.Uuid, sa.ForeignKey("ingestion_jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collection_id", sa.Uuid, nullable=False, index=True),
        sa.Column("stage_name", sa.String(30), nullable=False),
        sa.Column("error_type", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("is_retryable", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("suggested_action", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "query_sessions",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("collection_id", sa.Uuid, nullable=False, index=True),
        sa.Column("raw_query", sa.Text, nullable=False),
        sa.Column("normalized_query", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "answer_records",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("session_id", sa.Uuid, sa.ForeignKey("query_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("collection_id", sa.Uuid, nullable=False, index=True),
        sa.Column("answer_text", sa.Text, nullable=False),
        sa.Column("answer_mode", sa.String(40), nullable=False),
        sa.Column("citations_json", sa.Text, nullable=False),
        sa.Column("evidence_ids_json", sa.Text, nullable=False),
        sa.Column("raw_candidate_scores_json", sa.Text, nullable=True),
        sa.Column("evidence_json", sa.Text, nullable=True),
        sa.Column("reranker_used", sa.Boolean, nullable=False),
        sa.Column("llm_model", sa.String(100), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("answer_records")
    op.drop_table("query_sessions")
    op.drop_table("failure_events")
    op.drop_table("ingestion_jobs")
    op.drop_table("derived_assets")
    op.drop_table("chunks")
    op.drop_table("document_versions")
    op.drop_table("source_documents")
    op.drop_table("collections")