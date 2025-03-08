"""add_units_table_and_update_metric_types

Revision ID: de676024dd3b
Revises: 338bc73f4e1d
Create Date: 2025-03-08 17:56:38.796058

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid


# revision identifiers, used by Alembic.
revision: str = 'de676024dd3b'
down_revision: Union[str, None] = '338bc73f4e1d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if units table exists
    if 'units' not in inspector.get_table_names():
        # Create units table
        op.create_table(
            'units',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('symbol', sa.String(50), nullable=False),
            sa.Column('description', sa.Text()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
            sa.UniqueConstraint('name', name='uq_units_name'),
            sa.UniqueConstraint('symbol', name='uq_units_symbol')
        )

        # Create temporary table to store unique units from metric_types
        result = conn.execute(sa.text('SELECT DISTINCT unit FROM metric_types WHERE unit IS NOT NULL'))
        unique_units = result.fetchall()

        # Insert unique units into the units table
        for (unit_symbol,) in unique_units:
            unit_name = unit_symbol.upper().replace('/', ' PER ')
            conn.execute(
                sa.text(
                    'INSERT INTO units (id, name, symbol, description, created_at) '
                    'VALUES (:id, :name, :symbol, :description, CURRENT_TIMESTAMP)'
                ).bindparams(
                    id=str(uuid.uuid4()),
                    name=unit_name,
                    symbol=unit_symbol,
                    description='Automatically migrated from metric_types table'
                )
            )

    # Check if unit_id column exists in metric_types
    metric_types_columns = [col['name'] for col in inspector.get_columns('metric_types')]
    if 'unit_id' not in metric_types_columns:
        # Add nullable unit_id column first
        with op.batch_alter_table('metric_types') as batch_op:
            batch_op.add_column(sa.Column('unit_id', sa.String(36), nullable=True))

        # Update metric_types with corresponding unit_ids
        conn.execute(
            sa.text(
                'UPDATE metric_types SET unit_id = ('
                'SELECT id FROM units WHERE units.symbol = metric_types.unit'
                ')'
            )
        )

        # Create a temporary table with the desired schema
        op.execute(
            sa.text(
                'CREATE TABLE metric_types_new ('
                'id INTEGER NOT NULL, '
                'name VARCHAR(255) NOT NULL, '
                'description TEXT, '
                'unit_id VARCHAR(36) NOT NULL, '
                'created_at DATETIME, '
                'is_active BOOLEAN, '
                'PRIMARY KEY (id), '
                'UNIQUE (name), '
                'FOREIGN KEY(unit_id) REFERENCES units (id)'
                ')'
            )
        )

        # Copy data to the new table
        op.execute(
            sa.text(
                'INSERT INTO metric_types_new '
                'SELECT id, name, description, unit_id, created_at, is_active '
                'FROM metric_types'
            )
        )

        # Drop the old table and rename the new one
        op.drop_table('metric_types')
        op.rename_table('metric_types_new', 'metric_types')

        # Re-create the indexes
        op.create_index('ix_metric_types_id', 'metric_types', ['id'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    
    # Check if unit_id column exists in metric_types
    metric_types_columns = [col['name'] for col in inspector.get_columns('metric_types')]
    if 'unit_id' in metric_types_columns:
        # Create a temporary table with the old schema
        op.execute(
            sa.text(
                'CREATE TABLE metric_types_old ('
                'id INTEGER NOT NULL, '
                'name VARCHAR(255) NOT NULL, '
                'description TEXT, '
                'unit VARCHAR(50), '
                'created_at DATETIME, '
                'is_active BOOLEAN, '
                'PRIMARY KEY (id), '
                'UNIQUE (name)'
                ')'
            )
        )

        # Copy data back, getting the unit symbol from the units table
        op.execute(
            sa.text(
                'INSERT INTO metric_types_old '
                'SELECT m.id, m.name, m.description, u.symbol, m.created_at, m.is_active '
                'FROM metric_types m '
                'LEFT JOIN units u ON m.unit_id = u.id'
            )
        )

        # Drop the new table and rename the old one back
        op.drop_table('metric_types')
        op.rename_table('metric_types_old', 'metric_types')

        # Re-create the indexes
        op.create_index('ix_metric_types_id', 'metric_types', ['id'])

    # Drop the units table if it exists
    if 'units' in inspector.get_table_names():
        op.drop_table('units')
