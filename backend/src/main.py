import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from websockets.exceptions import ConnectionClosedOK

from . import game_logic
from .models import GameId

app = FastAPI()


Jsonish = dict[str, Any]


def runserver():
    """Convenient function for launching with `poetry run`."""
    uvicorn.run(
        'src.main:app',
        host=os.environ['HOST'],
        port=int(os.environ['PORT']),
        reload=True,
    )


@dataclass
class GameRegistry:
    """Essentially a "two-way" `dict` for assigning `Game`s to `WebSocket`s."""

    socket_to_game_id: dict[WebSocket, GameId] = field(default_factory=dict)
    game_id_to_sockets: dict[GameId, tuple[WebSocket, WebSocket]] = field(default_factory=dict)

    def new_game(self, game_id: GameId, player1: WebSocket, player2: WebSocket):
        """Register new player pair."""
        self.pop_socket(player1)
        self.pop_socket(player2)
        self.socket_to_game_id[player1] = game_id
        self.socket_to_game_id[player2] = game_id
        self.game_id_to_sockets[game_id] = (player1, player2)

    def get_game_id(self, websocket: WebSocket) -> GameId | None:
        """Get `GameId` for `websocket`."""
        return self.socket_to_game_id.get(websocket)

    def get_socket_info(self, websocket: WebSocket) -> tuple[bool, GameId] | None:
        """Get whether was first player and `GameId` for `websocket`."""
        if game_id := self.get_game_id(websocket):
            socket1, _ = self.game_id_to_sockets[game_id]
            return socket1 == websocket, game_id
        return None

    def get_sockets(self, game_id: GameId | None) -> tuple[WebSocket, WebSocket] | None:
        """Get `WebSocket`s associated with `game_id`."""
        if not game_id:
            return None
        return self.game_id_to_sockets.get(game_id)

    def pop_socket(self, socket: WebSocket):
        """Remove `socket` from registry, as well as it's associated game."""
        game_id = self.socket_to_game_id.pop(socket, None)
        if game_id:
            for socket in self.get_sockets(game_id) or ():
                self.socket_to_game_id.pop(socket, None)
            self.game_id_to_sockets.pop(game_id, None)


class GameManager:
    """Handles assigning connections to `Game`s and broadcasting messages."""

    def __init__(self):
        self.awaiting_opponent: WebSocket | None = None
        self.registry = GameRegistry()

    def get_socket_info(self, websocket: WebSocket) -> tuple[bool, GameId] | None:
        """Get the whether the player is first and the `GameId` for `websocket`."""
        return self.registry.get_socket_info(websocket)

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        await self.enter_new_player(websocket)

    async def enter_new_player(self, websocket: WebSocket):
        """Look for a game for a new entrant."""
        if self.awaiting_opponent:
            opponent = self.awaiting_opponent
            self.awaiting_opponent = None
            if opponent.client_state == WebSocketState.CONNECTED:
                # Player who was waiting gets to go first.
                # But could really do this any number of ways.
                await self.start_new_game(opponent, websocket)
                return
        self.awaiting_opponent = websocket
        await self.send_json(websocket, {'state': 'ready'})

    async def start_new_game(self, player1: WebSocket, player2: WebSocket):
        """Start a new game between two players."""
        game_id = game_logic.create_game()
        # Depending on requirements, it might be interesting to send back occupied tiles too.
        # This would, for example, facilitate reconnect to an existing, unfinished game.
        # But keeping minimal here and considering that use case out-of-scope.
        valid_tiles = {'validTiles': [asdict(p) for p in game_logic.get_initial_valid_tiles()]}
        await asyncio.gather(
            self.send_json(player1, {'player': 1} | valid_tiles),
            self.send_json(player2, {'player': 2} | valid_tiles),
        )
        self.registry.new_game(game_id, player1, player2)

    async def rematch(self, websocket: WebSocket):
        """Challenge same opponent to a rematch, if possible."""
        game_id = self.registry.get_game_id(websocket)
        sockets = self.registry.get_sockets(game_id)
        if not sockets:
            self.registry.pop_socket(websocket)
            await self.enter_new_player(websocket)
            return

        player_one, player_two = sockets
        await self.start_new_game(player_one, player_two)

    @staticmethod
    async def send_json(websocket: WebSocket, message: Jsonish):
        """Convenience wrapper around `send_text`."""
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.send_text(json.dumps(message))

    async def broadcast(self, websocket: WebSocket, message: Jsonish):
        """Send a message to all players in the same game as `websocket`."""
        game_id = self.registry.get_game_id(websocket)
        await asyncio.gather(
            *{self.send_json(websocket, message) for websocket in (self.registry.get_sockets(game_id) or ())}
        )

    async def disconnect(self, websocket: WebSocket):
        """Handle cowardly resignation of `websocket`."""
        await self.broadcast(websocket, {'state': 'abandoned'})
        self.registry.pop_socket(websocket)
        if websocket == self.awaiting_opponent:
            self.awaiting_opponent = None


game_manager = GameManager()


@app.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    """Websocket endpoint."""
    await game_manager.connect(websocket)

    while True:
        try:
            message = await websocket.receive_text()
            await handle_message(websocket, message)
        except (WebSocketDisconnect, ConnectionClosedOK):
            await game_manager.disconnect(websocket)
            return


async def handle_message(websocket: WebSocket, message: str):
    """Super-sophisticated deserialization logic goes here."""
    if message == 'new':
        await game_manager.rematch(websocket)
        return

    try:
        # Our chosen high-throughput encoding scheme.
        sender_identity, _, coords = message.partition(':')
        sender_identity = int(sender_identity)
        [x, y] = coords.split(',')
        x, y = int(x), int(y)
        info = game_manager.get_socket_info(websocket)
        assert info
        is_first, game_id = info
        # Sanity check... need the right user sending the right stuff.
        assert (sender_identity == 1) is is_first
    except (ValueError, AssertionError):
        await game_manager.broadcast(websocket, {'error': 'Unexpected error!'})
        return

    move_summary = {'x': x, 'y': y, 'player': sender_identity}
    match game_logic.make_move(game_id, x, y, is_first):
        case 'winner':
            # Admittedly here and elsewhere the frontend really _knows_ what the last move was...
            # But just trying to keep responsibility in the backend to not be duplicative.
            await game_manager.broadcast(websocket, move_summary | {'winner': True})
        case 'draw':
            await game_manager.broadcast(websocket, move_summary | {'draw': True})
        case game_logic.InvalidMove(reason):
            await game_manager.send_json(websocket, {'error': reason})
        case points:
            await game_manager.broadcast(
                websocket,
                move_summary
                | {
                    'validTiles': [asdict(p) for p in points],
                },
            )
