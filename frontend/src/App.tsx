import { useEffect, useState } from 'react'
import './App.css'

import useWebSocket, { ReadyState } from 'react-use-websocket'

const boardSideLength = 7 // here you go, tailwind: grid-cols-7

enum GameStateLabel {
  Connecting,
  Ready = 'ready',
  Active = 'active',
  Abandoned = 'abandoned',
}

type GameState = GameStateLabel | { firstPlayerWon: undefined | boolean }

type Point = {
  x: number
  y: number
}

type OccupiedTile = {
  point: Point
  wasFirstPlayer: boolean
}

type ExpectedJsonMessage =
  | {
      state: 'ready' | 'abandoned'
    }
  | {
      player: 1 | 2
      validTiles: Point[]
    }
  | (Point & { player: 1 | 2 } & (
        | {
            validTiles: Point[]
          }
        | {
            winner: true
          }
        | {
            draw: true
          }
      ))
  | {
      error: string
    }

export default function App() {
  return (
    <div className={'flex flex-col items-center'}>
      <h1 className={'pb-5'}>Side-Stacker</h1>
      <Game />
    </div>
  )
}

const labelFor = (isFirstPlayer: boolean) =>
  isFirstPlayer ? 'Player One' : 'Player Two'

const colorFor = (isFirstPlayer: boolean) =>
  // tailwind: text-red-500 text-blue-500 bg-red-500 bg-blue-500
  isFirstPlayer ? 'red-500' : 'blue-500'

function Game() {
  const [gameState, setGameState] = useState<GameState>(
    GameStateLabel.Connecting
  )
  const [validTiles, setValidTiles] = useState<Point[]>([])
  const [occupiedTiles, setOccupiedTiles] = useState<OccupiedTile[]>([])
  const [imFirstPlayer, setImFirstPlayer] = useState<boolean | undefined>(
    undefined
  )
  const [isCurrentFirstPlayer, setIsCurrentFirstPlayer] =
    useState<boolean>(true)
  const [awaitingServerResponse, setAwaitingServerResponse] = useState<boolean>(false)

  const { sendMessage, lastJsonMessage, readyState } =
    useWebSocket<ExpectedJsonMessage>(import.meta.env.VITE_BACKEND_WS_URL, {
      shouldReconnect: () => true,
      reconnectInterval: 1000,
      // Probably in a real app you might communicate something
      // after a certain number of failed connection attempts.
    })

  // Communication with websocket.
  useEffect(() => {
    if (lastJsonMessage === null) {
      return
    }
    setAwaitingServerResponse(false)

    if (readyState !== ReadyState.OPEN) {
      setGameState(GameStateLabel.Connecting)
      return
    }

    if ('state' in lastJsonMessage) {
      // Non-active game state
      const { state } = lastJsonMessage
      setGameState(state as GameStateLabel)
      resetState()
    } else if ('x' in lastJsonMessage) {
      // Move confirmation
      const { x, y, player } = lastJsonMessage
      const wasFirstPlayer = player === 1
      setOccupiedTiles((tiles) => [
        ...tiles,
        { point: { x, y }, wasFirstPlayer },
      ])
      if ('validTiles' in lastJsonMessage) {
        setValidTiles(lastJsonMessage.validTiles)
        setIsCurrentFirstPlayer((wasFirstPlayer) => !wasFirstPlayer)
      } else {
        const firstPlayerWon =
          'winner' in lastJsonMessage ? wasFirstPlayer : undefined
        setGameState({ firstPlayerWon })
      }
    } else if ('player' in lastJsonMessage) {
      // New game
      const { player, validTiles } = lastJsonMessage
      resetState()
      setImFirstPlayer(player === 1)
      setValidTiles(validTiles)
      setGameState(GameStateLabel.Active)
    } else {
      // Error
      alert(lastJsonMessage.error)
    }
  }, [lastJsonMessage, readyState, setOccupiedTiles])

  const sendMove = (point: Point) => {
    // Send identity of first player (sanity check) and coordinates of move.
    const firstPlayerEncoded = imFirstPlayer ? '1' : '0'
    setAwaitingServerResponse(true)
    sendMessage(`${firstPlayerEncoded}:${point.x},${point.y}`)
  }

  const requestNewGame = () => {
    sendMessage('new')
    resetState()
  }

  const resetState = () => {
    setValidTiles([])
    setOccupiedTiles([])
    setImFirstPlayer(undefined)
    setIsCurrentFirstPlayer(true)
  }

  const isMyTurn = isCurrentFirstPlayer === imFirstPlayer

  switch (gameState) {
    case GameStateLabel.Connecting:
      return <div>Connecting...</div>
    case GameStateLabel.Ready:
      return <div>Awaiting opponent...</div>
    case GameStateLabel.Abandoned:
      return (
        <>
          <div>Opponent fled!</div>
          <button onClick={requestNewGame}>Start a new game?</button>
        </>
      )
    case GameStateLabel.Active:
      return (
        <>
          <Board
            validTiles={validTiles}
            occupiedTiles={occupiedTiles}
            isMyTurn={isMyTurn}
            makeMove={awaitingServerResponse ? undefined : sendMove}
          />
          {!isMyTurn && (
            <div className={'mt-5'}>Waiting for opponent's move...</div>
          )}
        </>
      )
    default: {
      const { firstPlayerWon } = gameState
      return (
        <>
          <Board
            validTiles={validTiles}
            occupiedTiles={occupiedTiles}
            isMyTurn={false}
          />
          <div>
            <p>Game over!</p>
            {firstPlayerWon === undefined ? (
              <p>Stalemate!</p>
            ) : (
              <>
                <p
                  className={`text-${colorFor(firstPlayerWon)}`}
                >{`${labelFor(firstPlayerWon)} wins!`}</p>
                <p
                  className={`text-${colorFor(!firstPlayerWon)}`}
                >{`${labelFor(!firstPlayerWon)} loses.`}</p>
              </>
            )}
            <button onClick={requestNewGame}>Play again?</button>
          </div>
        </>
      )
    }
  }
}

enum TileState {
  Valid,
  Invalid,
  PlayerOne,
  PlayerTwo,
}

const pointsEqual = (a: Point, b: Point) => a.x == b.x && a.y == b.y

function Board({
  validTiles,
  occupiedTiles,
  isMyTurn,
  makeMove,
}: {
  validTiles: Point[]
  occupiedTiles: OccupiedTile[]
  isMyTurn: boolean
  makeMove?: (point: Point) => void
}) {
  return (
    <div
      className={`grid grid-cols-${boardSideLength} gap-4 bg-gray-900 p-10 w-5/12`}
    >
      {Array(boardSideLength)
        .fill(0)
        .map((_, y) =>
          Array(boardSideLength)
            .fill(0)
            .map((_, x) => {
              const point = { x, y }
              const wasFirstPlayer = occupiedTiles.find((tile) =>
                pointsEqual(tile.point, point)
              )?.wasFirstPlayer
              let tileState
              if (wasFirstPlayer === undefined) {
                tileState =
                  isMyTurn &&
                  validTiles.some((openTile) => pointsEqual(openTile, point))
                    ? TileState.Valid
                    : TileState.Invalid
              } else {
                tileState = wasFirstPlayer
                  ? TileState.PlayerOne
                  : TileState.PlayerTwo
              }

              return (
                <Tile
                  key={x + boardSideLength * x}
                  tileState={tileState}
                  onClick={
                    makeMove && tileState == TileState.Valid
                      ? () => makeMove(point)
                      : undefined
                  }
                />
              )
            })
        )}
    </div>
  )
}

const Tile = ({
  tileState,
  onClick,
}: {
  tileState: TileState
  onClick?: () => void
}) => {
  const bgColor = {
    [TileState.Valid]: 'bg-gray-600',
    [TileState.Invalid]: 'bg-gray-800',
    [TileState.PlayerOne]: `bg-${colorFor(true)}`,
    [TileState.PlayerTwo]: `bg-${colorFor(false)}`,
  }[tileState]

  return (
    <div className={'aspect-square relative'}>
      <div
        className={
          `
          rounded-full w-full h-full ${bgColor}
          absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
        ` +
          (onClick ? 'hover:bg-gray-400 cursor-pointer' : 'cursor-not-allowed')
        }
        onClick={onClick}
      ></div>
    </div>
  )
}
