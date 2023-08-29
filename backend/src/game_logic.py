from dataclasses import dataclass
from typing import Literal

from sqlalchemy.exc import IntegrityError

from . import models
from .db import get_session


BOARD_SIZE = 7
TILE_COUNT = BOARD_SIZE**2
WINNER_LENGTH = 4


@dataclass
class V2:
    x: int
    y: int

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __add__(self, other: 'V2') -> 'V2':
        return V2(self.x + other.x, self.y + other.y)


@dataclass
class InvalidMove:
    reason: str


def create_game() -> int:
    """Persist a new `Game` and return its ID."""
    with get_session() as session:
        game = models.Game()
        with session.begin():
            session.add(game)
        session.refresh(game)
        return game.id


def get_valid_tiles(occupied_tiles: set[V2]) -> set[V2]:
    """Returns the set of open tiles for the next move."""
    candidates = (
        # Edges are OK,
        {V2(0, y) for y in range(BOARD_SIZE)}
        | {V2(BOARD_SIZE - 1, y) for y in range(BOARD_SIZE)}
        # as are the tiles next to occupied tiles,
        | {p + V2(1, 0) for p in occupied_tiles}
        | {p + V2(-1, 0) for p in occupied_tiles}
    )
    # unless they're occupied,
    candidates -= occupied_tiles
    # or off the board entirely.
    return {c for c in candidates if 0 <= c.x < BOARD_SIZE}


def get_initial_valid_tiles() -> set[V2]:
    """Returns the set of open tiles as of the start of the game."""
    return get_valid_tiles(set())


def adjust_valid_tiles_after_move(valid_tiles: set[V2], occupied_tiles: set[V2], new_tile: V2):
    """Adjust `valid_tiles` to the newest move.

    Given that neither this, nor the previous, nor any of the app is coded with cutting edge
    performance in mind, we probably could have just called `get_valid_tiles` again to write less code.
    But, it was written.
    """
    valid_tiles -= {new_tile}
    right = new_tile + V2(1, 0)
    if right not in occupied_tiles:
        valid_tiles.add(right)
        return
    left = new_tile + V2(-1, 0)
    if left not in occupied_tiles:
        valid_tiles.add(left)


def is_winner(occupied_tiles: set[V2], new_tile: V2) -> bool:
    """Check if move to `new_tile` is a winner.

    Simplified by the assumption that we would have ended the game already had any of
    the previous moves been winners. So only check vectors from the current move's tile.
    """

    def travel_along(p: V2, d: V2, count: int = 0):
        if p in occupied_tiles:
            return travel_along(p + d, d, count + 1)
        return count

    for d1, d2 in [
        (V2(1, 0), V2(-1, 0)),  # Horizontal
        (V2(0, 1), V2(0, -1)),  # Vertical
        (V2(1, 1), V2(-1, -1)),  # Lawful diagonal
        (V2(1, -1), V2(-1, 1)),  # Chaotic diagonal
    ]:
        if 1 + travel_along(new_tile + d1, d1) + travel_along(new_tile + d2, d2) >= WINNER_LENGTH:
            return True
    return False


def make_move(
    game_id: models.GameId,
    x: int,
    y: int,
    is_first: bool,
) -> set[V2] | InvalidMove | Literal['winner', 'draw']:
    """Determine the whether the proposed move is valid and persist it if so."""
    with get_session() as session:
        moves = session.query(models.Move).filter(models.Move.game_id == game_id).order_by(models.Move.id).all()
        move = models.Move(game_id=game_id, x=x, y=y)
        session.add(move)
        new_tile = V2(move.x, move.y)
        occupied_tiles = {V2(m.x, m.y) for m in moves}
        if (len(occupied_tiles) % 2 == 0) is not is_first:
            return InvalidMove('Turn out of order!')
        valid_tiles = get_valid_tiles(occupied_tiles)
        if new_tile not in valid_tiles:
            return InvalidMove('Tile is not viable')
        try:
            session.commit()
        except IntegrityError:
            # In practice, should have been excluded from `valid_points`.
            return InvalidMove('Tile already occupied')

        # Subtract one since we've added one in `session.commit()`, but not worth fetching again.
        if len(occupied_tiles) == TILE_COUNT - 1:
            return 'draw'

        # Notice can figure out which moves were mine by taking every other move in order.
        my_moves = moves[:-1][::-2]
        if is_winner({V2(m.x, m.y) for m in my_moves}, new_tile):
            return 'winner'

        adjust_valid_tiles_after_move(valid_tiles, occupied_tiles, new_tile)
        return get_valid_tiles(occupied_tiles | {new_tile})
