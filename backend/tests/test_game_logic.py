from src import game_logic
from src.game_logic import V2


def test_get_valid_points():
    # Probably would want to control `BOARD_SIZE` and `WINNER_LENGTH`,
    # that I'd prefer to leave parametric, but this is fine for our needs, I'd think.
    expected_initial_valid_points = {V2(0, i) for i in range(7)} | {V2(6, i) for i in range(7)}
    valid_points = game_logic.get_valid_tiles(set())
    assert valid_points == expected_initial_valid_points
    game_logic.adjust_valid_tiles_after_move(valid_points, set(), V2(0, 0))
    assert valid_points == expected_initial_valid_points - {V2(0, 0)} | {V2(1, 0)}
    # Whole row taken.
    assert not any(p.y == 0 for p in game_logic.get_valid_tiles({V2(i, 0) for i in range(7)}))


def test_is_winner():
    assert game_logic.is_winner({V2(0, 0), V2(1, 0), V2(2, 0)}, V2(3, 0))
    assert game_logic.is_winner({V2(0, 0), V2(2, 2), V2(3, 3)}, V2(1, 1))
    assert game_logic.is_winner({V2(0, 0), V2(0, 1), V2(0, 3)}, V2(0, 2))
    assert game_logic.is_winner({V2(4, 0), V2(3, 1), V2(2, 2)}, V2(1, 3))
    assert not game_logic.is_winner({V2(4, 0), V2(2, 2)}, V2(1, 3))
    assert not game_logic.is_winner({V2(4, 0), V2(2, 2), V2(5, 5)}, V2(1, 3))
    assert not game_logic.is_winner(set(), V2(0, 0))
