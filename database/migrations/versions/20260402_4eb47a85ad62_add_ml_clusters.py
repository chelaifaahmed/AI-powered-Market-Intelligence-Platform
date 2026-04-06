"""add_ml_clusters

Revision ID: 4eb47a85ad62
Revises: d6e7f8a9b0c1
Create Date: 2026-04-02 15:56:01.007846

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '4eb47a85ad62'
down_revision: Union[str, None] = 'd6e7f8a9b0c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table: ml_cluster_metadata
    op.create_table('ml_cluster_metadata',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('cluster_id', sa.Integer(), nullable=False),
        sa.Column('cluster_label', sa.String(length=100), nullable=False),
        sa.Column('erp_module', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('avg_negative_pct', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('avg_review_count', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('company_count', sa.Integer(), nullable=False),
        sa.Column('color_hex', sa.String(length=7), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        comment='One row per KMeans cluster with label, ERP module, and summary stats.'
    )
    op.create_index('idx_mlcm_cluster', 'ml_cluster_metadata', ['cluster_id'], unique=False)

    # Add cluster columns to car_brands
    op.add_column('car_brands', sa.Column('cluster_id', sa.Integer(), nullable=True, comment='KMeans cluster assignment'))
    op.add_column('car_brands', sa.Column('cluster_label', sa.String(length=100), nullable=True, comment='Human-readable cluster label'))
    op.add_column('car_brands', sa.Column('erp_module', sa.String(length=100), nullable=True, comment='Recommended TEAMWILL ERP module'))

    # Add cluster columns to insurance_companies
    op.add_column('insurance_companies', sa.Column('cluster_id', sa.Integer(), nullable=True, comment='KMeans cluster assignment'))
    op.add_column('insurance_companies', sa.Column('cluster_label', sa.String(length=100), nullable=True, comment='Human-readable cluster label'))
    op.add_column('insurance_companies', sa.Column('erp_module', sa.String(length=100), nullable=True, comment='Recommended TEAMWILL ERP module'))


def downgrade() -> None:
    op.drop_column('insurance_companies', 'erp_module')
    op.drop_column('insurance_companies', 'cluster_label')
    op.drop_column('insurance_companies', 'cluster_id')
    op.drop_column('car_brands', 'erp_module')
    op.drop_column('car_brands', 'cluster_label')
    op.drop_column('car_brands', 'cluster_id')
    op.drop_index('idx_mlcm_cluster', table_name='ml_cluster_metadata')
    op.drop_table('ml_cluster_metadata')
