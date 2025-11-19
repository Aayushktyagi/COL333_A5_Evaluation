#!/usr/bin/env python3
"""Random bot for testing."""
import sys
import requests
import time

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
    
    # Connect bot
    print(f"Connecting as {PLAYER}...")
    resp = requests.post(
        f"http://localhost:{port}/bot/connect/{PLAYER}",
        json={"name": "Random", "board_size": board_size}
    )
    print(f"Connect response: {resp.json()}")
    
    agent = get_agent(PLAYER, "random")
    print(f"Random agent created")
    
    # Wait for game to become active (both players need to connect)
    print("Waiting for game to become active...")
    for _ in range(60):  # Wait up to 30 seconds
        try:
            state = requests.get(f"http://localhost:{port}/bot/game_state/{PLAYER}").json()
            if state["game_status"] == "active":
                print("✅ Game is active!")
                break
            time.sleep(0.5)
        except:
            time.sleep(0.5)
    else:
        print("⚠️  Game did not become active")
        sys.exit(1)
    
    # Game loop
    for turn in range(100):
        try:
            # Get game state
            state = requests.get(f"http://localhost:{port}/bot/game_state/{PLAYER}").json()
            
            if state["game_status"] != "active":
                print(f"Game not active: {state['game_status']}")
                break
            
            if not state["your_turn"]:
                time.sleep(0.5)
                continue
            
            print(f"\nTurn {turn+1}: Random bot turn")
            
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
                f"http://localhost:{port}/bot/move/{PLAYER}",
                json={"move": move, "thinking_time": thinking_time}
            )
            result = resp.json()
            
            if not result.get("success"):
                print(f"Move failed: {result}")
                break
            
            if result.get("winner"):
                print(f"\n🏆 Winner: {result['winner']}")
                break
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    print("\n✅ Random bot finished")

if __name__ == "__main__":
    main()
