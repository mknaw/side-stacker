import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .db import Base

# Convenient to alias type to use as readable label.
GameId = int


class Game(Base):
    __tablename__ = 'games'

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    created = sa.Column(sa.DateTime, server_default=func.now())

    moves = relationship('Move', back_populates='game')


class Move(Base):
    __tablename__ = 'moves'

    id = sa.Column(sa.Integer, primary_key=True, index=True)
    x = sa.Column(sa.SmallInteger)
    y = sa.Column(sa.SmallInteger)
    game_id = sa.Column(sa.Integer, sa.ForeignKey('games.id'), index=True)

    game = relationship('Game', back_populates='moves')
    __table_args__ = (
        sa.UniqueConstraint('game_id', 'x', 'y', name='_game_pos_uc'),
    )
