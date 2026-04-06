"""add_erp_vendors

Revision ID: e6cc055da982
Revises: 73c028bd9bfa
Create Date: 2026-04-03 19:05:16.811930

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e6cc055da982'
down_revision: Union[str, None] = '73c028bd9bfa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('erp_vendors',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('product_name', sa.String(length=200), nullable=False),
        sa.Column('target_sector', sa.String(length=50), nullable=False, comment='insurance, automotive, both'),
        sa.Column('target_region', sa.String(length=50), nullable=False, comment='TN, EU, MENA, global'),
        sa.Column('website', sa.String(length=200), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('data_origin', sa.String(length=20), server_default=sa.text("'seeded'"), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        comment='ERP vendor competitive intelligence for TEAMWILL market positioning.'
    )
    op.create_index('idx_erp_vendor_region', 'erp_vendors', ['target_region'], unique=False)
    op.create_index('idx_erp_vendor_sector', 'erp_vendors', ['target_sector'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_erp_vendor_sector', table_name='erp_vendors')
    op.drop_index('idx_erp_vendor_region', table_name='erp_vendors')
    op.drop_table('erp_vendors')
