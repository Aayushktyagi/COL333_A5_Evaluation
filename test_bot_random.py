#!/usr/bin/env python3
"""Random bot for testing."""
import sys
import requests
import time
import os

# Disable proxy for localhost connections
os.environ['NO_PROXY'] = 'localhost,127.0.0.1'

def main():
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <submission_dir> <port> <board_size>")
        sys.exit(1)
    
    submission_dir = sys.argv[1]
    port = int(sys.argv[2])
    board_size = sys.argv[3]
    
    # Add submission directory to path
    sys.path.insert(0, submission_dir)
    
    from agent import get_agent
    from gameEngine import Piece
    
    def convert_board_to_pieces(board):
        """Convert dict-based board to Piece-based board."""
        if not board or not board[0]:
            return board
        
        # Check if already Piece objects
        if board[0][0] is not None and hasattr(board[0][0], 'owner'):
            return board
        
        # Convert dicts to Piece objects
        new_board = []
        for row in board:
            new_row = []
            for cell in row:
                if cell is None:
                    new_row.append(None)
                else:
                    new_row.append(Piece.from_dict(cell))
            new_board.append(new_row)
        return new_board
    
    PLAYER = "square"
    HOST = "10.237.23.218"  # Use actual IP instead of localhost
    
    # Connect bot (retry if server not ready)
    print(f"Connecting as {PLAYER}...")
    for attempt in range(20):
        try:
            resp = requests.post(
                f"http://{HOST}:{port}/bot/connect/{PLAYER}",
                json={"name": "Random", "board_size": board_size},
                timeout=10
            )
            if resp.status_code == 200:
                print(f"Connect response: {resp.json()}")
                break
            else:
                print(f"Connection attempt {attempt+1} failed with status {resp.status_code}")
                time.sleep(3)
        except Exception as e:
            print(f"Connection attempt {attempt+1} failed: {e}")
            time.sleep(3)
    else:
        print("Failed to connect after 20 attempts")
        sys.exit(1)
    
    agent = get_agent(PLAYER, "random")
    print(f"Random agent created")
    print(f"Entering game loop...")
    
    try:
        # Game loop - run until game finishes
        turn = 0
        while True:
            try:
                # Get game state
                state = requests.get(f"http://{HOST}:{port}/bot/game_state/{PLAYER}", timeout=10).json()
                
                if not state:
                    print("No game state received, waiting...")
                    time.sleep(2)
                    continue
                
                # Check for error response
                if "error" in state:
                    print(f"Server error: {state['error']}")
                    break
                
                # Check if game_status exists
                if "game_status" not in state:
                    print("Invalid game state response")
                    break
                
                # Handle different game statuses
                if state["game_status"] == "waiting":
                    time.sleep(2)
                    continue
                
                if state["game_status"] == "finished":
                    print("Game finished!")
                    break
                
                if not state["your_turn"]:
                    time.sleep(1)
                    continue
                
                turn += 1
                print(f"\nTurn {turn}: Random bot turn")
                
                # Choose move
                start_time = time.time()
                
                # Convert board dicts to Piece objects if needed
                board = convert_board_to_pieces(state["board"])
                
                move = agent.choose(
                    board, 
                    state["rows"], 
                    state["cols"],
                    state["score_cols"],
                    state["time_left"],
                    state["opponent_time"]
                )
                thinking_time = time.time() - start_time
                
                if move is None:
                    print("No move available")
                    break
                
                # Submit move
                resp = requests.post(
                    f"http://{HOST}:{port}/bot/move/{PLAYER}",
                    json={"move": move, "thinking_time": thinking_time}
                )
                result = resp.json()
                
                if not result.get("success"):
                    print(f"Move failed: {result}")
                    break
                
                if result.get("winner"):
                    print(f"\n🏆 Winner: {result['winner']}")
                    break
                
                # Small delay before next iteration
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error in game loop: {e}")
                import traceback
                traceback.print_exc()
                break
    
    except KeyboardInterrupt:
        print("Bot interrupted by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ Random bot finished")

if __name__ == "__main__":
    main()
