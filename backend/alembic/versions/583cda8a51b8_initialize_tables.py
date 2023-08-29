"""initialize tables

Revision ID: 583cda8a51b8
Revises: 
Create Date: 2023-08-31 15:59:53.455288

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '583cda8a51b8'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('games',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created', sa.DateTime(), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_games_id'), 'games', ['id'], unique=False)
    op.create_table('moves',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('x', sa.SmallInteger(), nullable=True),
    sa.Column('y', sa.SmallInteger(), nullable=True),
    sa.Column('game_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['game_id'], ['games.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('game_id', 'x', 'y', name='_game_pos_uc')
    )
    op.create_index(op.f('ix_moves_game_id'), 'moves', ['game_id'], unique=False)
    op.create_index(op.f('ix_moves_id'), 'moves', ['id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_moves_id'), table_name='moves')
    op.drop_index(op.f('ix_moves_game_id'), table_name='moves')
    op.drop_table('moves')
    op.drop_index(op.f('ix_games_id'), table_name='games')
    op.drop_table('games')
    # ### end Alembic commands ###