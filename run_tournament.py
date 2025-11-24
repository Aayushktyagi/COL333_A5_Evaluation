#!/usr/bin/env python3
"""
Tournament System for COL333 A5 Evaluation
Runs round-robin matches between all submissions in a group
Each match is played on small, medium, and large boards
"""

import os
import sys
import subprocess
import time
import csv
from datetime import datetime
import shutil
import signal
from pathlib import Path
import re
from itertools import combinations

# Configuration
PORT = 9500
BOARD_SIZES = ['small', 'medium', 'large']
# Time limits for thinking time (server internal timeout)
SERVER_TIME_LIMITS = {
    'small': 120,   # 2 minutes
    'medium': 240,  # 4 minutes
    'large': 360    # 6 minutes
}
# External timeout = server timeout + buffer for connection and cleanup
TIME_LIMITS = {
    'small': 150,   # 2.5 minutes (120s + 30s buffer)
    'medium': 270,  # 4.5 minutes (240s + 30s buffer)
    'large': 390    # 6.5 minutes (360s + 30s buffer)
}

class TournamentRunner:
    def __init__(self, group_dir, output_dir):
        self.group_dir = Path(group_dir)
        self.group_name = self.group_dir.name
        # Create group-specific output directory
        self.output_dir = Path(output_dir) / self.group_name
        self.submissions = sorted([d for d in self.group_dir.iterdir() if d.is_dir() and d.name.startswith('submission_')])
        
        # Create output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.matches_dir = self.output_dir / 'matches'
        self.matches_dir.mkdir(exist_ok=True)
        
        # CSV file for results
        self.csv_file = self.output_dir / f'{self.group_name}_results.csv'
        
        print(f"🏆 Tournament for {self.group_name}")
        print(f"📁 Group directory: {self.group_dir}")
        print(f"📊 Output directory: {self.output_dir}")
        print(f"👥 Found {len(self.submissions)} submissions")
        for sub in self.submissions:
            print(f"   - {sub.name}")
        print()
    
    def detect_submission_type(self, submission_dir):
        """Detect if submission is Python, C++, or mixed"""
        has_cmake = (submission_dir / 'CMakeLists.txt').exists()
        has_cpp = any(submission_dir.glob('*.cpp'))
        has_py = any(submission_dir.glob('*.py'))
        
        if has_cmake or has_cpp:
            return 'mixed' if has_py else 'cpp'
        return 'python'
    
    def compile_cpp_submission(self, submission_dir, temp_dir):
        """Compile C++ submission if needed"""
        if not (submission_dir / 'CMakeLists.txt').exists():
            return False, "No CMakeLists.txt found"
        
        # Python executable from Aayush_env
        python_exe = "/home/aayush/anaconda3/envs/Aayush_env/bin/python"
        
        build_dir = temp_dir / 'build'
        # Remove old build directory if exists
        if build_dir.exists():
            shutil.rmtree(build_dir)
        build_dir.mkdir(exist_ok=True)
        
        try:
            # Get pybind11 cmake directory
            pybind11_result = subprocess.run(
                [python_exe, '-m', 'pybind11', '--cmakedir'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if pybind11_result.returncode != 0:
                return False, "Could not find pybind11 cmake directory"
            
            pybind11_dir = pybind11_result.stdout.strip()
            
            # Configure CMake with pybind11
            result = subprocess.run(
                [
                    'cmake', '..',
                    f'-Dpybind11_DIR={pybind11_dir}',
                    '-DCMAKE_BUILD_TYPE=Release',
                    '-DCMAKE_C_COMPILER=gcc',
                    '-DCMAKE_CXX_COMPILER=g++'
                ],
                cwd=build_dir,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[-500:] if result.stderr else "CMake configure failed"
                return False, f"CMake configure failed: {error_msg}"
            
            # Build with CMake
            result = subprocess.run(
                ['cmake', '--build', '.', '--config', 'Release'],
                cwd=build_dir,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode != 0:
                error_msg = result.stderr[-500:] if result.stderr else "CMake build failed"
                return False, f"CMake build failed: {error_msg}"
            
            # Check if .so file was created
            so_files = list(build_dir.glob('*.so'))
            if not so_files:
                return False, "No .so file generated"
            
            return True, f"Compilation successful: {so_files[0].name}"
            
        except subprocess.TimeoutExpired:
            return False, "Compilation timeout"
        except Exception as e:
            return False, f"Compilation error: {str(e)[:200]}"
    
    def setup_match_directory(self, match_dir, player1_dir, player2_dir):
        """Copy necessary files for a match"""
        match_dir.mkdir(parents=True, exist_ok=True)
        
        # Reference files to copy
        eval_dir = Path(__file__).parent
        manual_test_dir = eval_dir / 'manual_test'
        
        # Files that should be in manual_test directory
        manual_test_files = ['gameEngine.py', 'agent.py', 'bot_client.py', 'web_server.py']
        
        # Files that are in evaluation root directory
        eval_root_files = ['test_bot_student.py', 'test_bot_vs_student.py']
        
        # Copy files from manual_test directory
        for file in manual_test_files:
            src = manual_test_dir / file
            if src.exists():
                shutil.copy2(src, match_dir)
        
        # Copy files from evaluation root directory
        for file in eval_root_files:
            src = eval_dir / file
            if src.exists():
                shutil.copy2(src, match_dir)
        
        # Copy templates directory from manual_test
        templates_src = manual_test_dir / 'templates'
        if templates_src.exists():
            templates_dst = match_dir / 'templates'
            if templates_dst.exists():
                shutil.rmtree(templates_dst)
            shutil.copytree(templates_src, templates_dst)
        
        # Setup player directories
        player1_temp = match_dir / 'player1'
        player2_temp = match_dir / 'player2'
        
        # Copy all files from player1
        if player1_temp.exists():
            shutil.rmtree(player1_temp)
        shutil.copytree(player1_dir, player1_temp)
        
        # Copy all files from player2
        if player2_temp.exists():
            shutil.rmtree(player2_temp)
        shutil.copytree(player2_dir, player2_temp)
        
        # Copy gameEngine.py and agent.py to each player directory so they can import it
        for player_dir in [player1_temp, player2_temp]:
            for file in ['gameEngine.py', 'agent.py']:
                src = manual_test_dir / file
                if src.exists():
                    shutil.copy2(src, player_dir)
        
        # Compile C++ submissions if needed
        for player_dir, player_name in [(player1_temp, 'Player1'), (player2_temp, 'Player2')]:
            submission_type = self.detect_submission_type(player_dir)
            if submission_type in ['cpp', 'mixed']:
                print(f"         🔨 Compiling {player_name} C++ submission...")
                success, message = self.compile_cpp_submission(player_dir, player_dir)
                if success:
                    print(f"         ✅ {player_name} compilation successful")
                else:
                    print(f"         ⚠️  {player_name} compilation warning: {message}")
        
        return player1_temp, player2_temp
    
    def parse_game_result(self, log_file, server_log_file=None):
        """Parse game result from log file (prefer server log, fallback to player log)"""
        # First check server log if available
        logs_to_check = []
        if server_log_file and server_log_file.exists():
            logs_to_check.append(('server', server_log_file))
        if log_file.exists():
            logs_to_check.append(('player', log_file))
        
        if not logs_to_check:
            return None, None, None, "No log files found"
        
        winner = None
        circle_score = None
        square_score = None
        error = None
        termination_reason = None
        
        for log_type, log_path in logs_to_check:
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Check for timeout
            if 'Timeout' in content or 'timeout' in content or 'TIMEOUT' in content:
                termination_reason = "Timeout"
                # Try to extract scores even on timeout
                score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if score_match:
                    circle_score = float(score_match.group(1))
                    square_score = float(score_match.group(2))
                    winner = 'circle' if circle_score > square_score else 'square' if square_score > circle_score else 'draw'
                    break
            
            # Check for repetition (3-move repetition detected)
            if 'REPETITION DETECTED' in content or 'repetition' in content.lower():
                termination_reason = "Repetition (3-move rule)"
                # Extract winner from server log
                winner_match = re.search(r'Winner:\s*(\w+)', content, re.IGNORECASE)
                if winner_match:
                    winner = winner_match.group(1).lower()
                
                # Extract scores from server log
                score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if score_match:
                    circle_score = float(score_match.group(1))
                    square_score = float(score_match.group(2))
                    break
            
            # Check for invalid move
            if 'INVALID MOVE' in content or 'invalid move' in content.lower():
                termination_reason = "Invalid move"
                # Check who made invalid move
                if 'INVALID MOVE by circle' in content:
                    winner = 'square'
                    circle_score = 0.0
                    square_score = 100.0
                elif 'INVALID MOVE by square' in content:
                    winner = 'circle'
                    circle_score = 100.0
                    square_score = 0.0
                
                # Try to get scores from server log
                score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if score_match:
                    circle_score = float(score_match.group(1))
                    square_score = float(score_match.group(2))
                break
            
            # Check for turn limit (1000 turns)
            if 'Turn limit' in content or 'turn limit' in content.lower() or '1000 total turns' in content:
                termination_reason = "Turn limit (1000 turns)"
                score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if score_match:
                    circle_score = float(score_match.group(1))
                    square_score = float(score_match.group(2))
                    winner = 'circle' if circle_score > square_score else 'square' if square_score > circle_score else 'draw'
                    break
            
            # Check for normal completion (win condition or game finished)
            if 'Game finished' in content or 'Game Over' in content or 'Winner:' in content:
                # Try to extract winner
                if not winner:
                    winner_match = re.search(r'Winner:\s*(\w+)', content, re.IGNORECASE)
                    if winner_match:
                        winner = winner_match.group(1).lower()
                
                # Extract scores from server log or player log
                score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                if score_match:
                    circle_score = float(score_match.group(1))
                    square_score = float(score_match.group(2))
                    if not winner:
                        winner = 'circle' if circle_score > square_score else 'square' if square_score > circle_score else 'draw'
                    termination_reason = "Normal (win condition met)" if winner and winner != 'draw' else "Normal (completed)"
                    break
        
        # If still no result, check for errors
        if not winner and not termination_reason:
            # Look for common error patterns in both logs
            for log_type, log_path in logs_to_check:
                with open(log_path, 'r') as f:
                    content = f.read()
                
                error_patterns = [
                    (r'ImportError', 'Import Error'),
                    (r'ModuleNotFoundError', 'Module Not Found'),
                    (r'AttributeError', 'Attribute Error'),
                    (r'TypeError', 'Type Error'),
                    (r'ValueError', 'Value Error'),
                    (r'IndexError', 'Index Error'),
                    (r'KeyError', 'Key Error'),
                    (r'NameError', 'Name Error'),
                    (r'SyntaxError', 'Syntax Error'),
                    (r'IndentationError', 'Indentation Error'),
                    (r'Traceback', 'Python Exception'),
                    (r'ConnectionRefusedError', 'Connection Refused'),
                    (r'TimeoutError', 'Timeout Error'),
                    (r'Connection refused', 'Connection Refused'),
                ]
                
                for pattern, error_name in error_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        error = error_name
                        # Try to get more specific error message
                        lines = content.split('\n')
                        for line in lines:
                            if re.search(pattern, line, re.IGNORECASE):
                                error = line.strip()[:200]  # First 200 chars of error line
                                break
                        termination_reason = f"Error: {error}"
                        break
                
                if error:
                    break
            
            if not error:
                # Last resort - check if log is empty or incomplete
                for log_type, log_path in logs_to_check:
                    with open(log_path, 'r') as f:
                        content = f.read()
                    
                    if len(content.strip()) < 50:
                        error = "Log too short - process may have crashed"
                        termination_reason = "Error: Process crashed"
                    else:
                        # Check if game actually finished
                        if '✅ Bot finished' in content or 'Game finished' in content:
                            # Game finished but no clear result - could be repetition
                            termination_reason = "Completed (check server log for details)"
                            # Try one more time to find winner from any log
                            score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
                            if score_match:
                                circle_score = float(score_match.group(1))
                                square_score = float(score_match.group(2))
                                winner = 'circle' if circle_score > square_score else 'square' if square_score > circle_score else 'draw'
                        else:
                            # Get last non-empty line as context
                            lines = [l.strip() for l in content.split('\n') if l.strip()]
                            if lines:
                                error = f"Game did not complete. Last log: {lines[-1][:150]}"
                                termination_reason = "Incomplete"
                            else:
                                error = "Unknown error - game did not complete"
                                termination_reason = "Error: Unknown"
        
        # Format error/termination message
        if error:
            final_error = error
        elif termination_reason:
            final_error = termination_reason
        else:
            final_error = None
        
        return winner, circle_score, square_score, final_error
    
    def run_game(self, match_dir, player1_temp, player2_temp, board_size, log_prefix):
        """Run a single game
        
        Note: C++ submissions are expected to be pre-compiled by students.
        The test scripts will import from student_agent_cpp.py which loads the compiled .so file.
        """
        print(f"      🎮 Running {board_size} board game...")
        
        # Commands using conda environment with unbuffered output (-u flag)
        conda_python = 'bash -c "source ~/anaconda3/etc/profile.d/conda.sh && conda activate Aayush_env && python -u'
        
        # Start web server
        server_log = match_dir / f'{log_prefix}_server.log'
        with open(server_log, 'w') as f:
            server_proc = subprocess.Popen(
                f'{conda_python} web_server.py {PORT} {board_size}"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True
            )
        
        time.sleep(2)  # Wait for server to start
        
        # Start player1 (circle) - runs player1's submission
        # Use relative paths so Python can find the student_agent module
        player1_log = match_dir / f'{log_prefix}_player1.log'
        with open(player1_log, 'w') as f:
            player1_proc = subprocess.Popen(
                f'{conda_python} test_bot_student.py player1 {PORT} {board_size} circle"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True
            )
        
        time.sleep(1)
        
        # Start player2 (square) - runs player2's submission
        # Use relative paths so Python can find the student_agent module
        player2_log = match_dir / f'{log_prefix}_player2.log'
        with open(player2_log, 'w') as f:
            player2_proc = subprocess.Popen(
                f'{conda_python} test_bot_student.py player2 {PORT} {board_size} square"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True
            )
        
        # Wait for both players to connect (check server log for connection messages)
        print(f"         ⏳ Waiting for players to connect...")
        connection_timeout = 30  # 30 seconds to connect
        connection_start = time.time()
        both_connected = False
        
        while time.time() - connection_start < connection_timeout:
            if server_log.exists():
                with open(server_log, 'r') as f:
                    log_content = f.read()
                    if 'both players connected' in log_content.lower() or 'game' in log_content.lower() and 'started' in log_content.lower():
                        both_connected = True
                        print(f"         ✅ Both players connected")
                        break
            time.sleep(0.5)
        
        if not both_connected:
            print(f"         ⚠️  Players did not connect within {connection_timeout}s, starting timeout anyway")
        
        # NOW start the external watchdog timeout (server has its own internal timeout)
        # External timeout = server thinking time + buffer for server to write final scores
        timeout_seconds = TIME_LIMITS[board_size]
        server_timeout = SERVER_TIME_LIMITS[board_size]
        start_time = time.time()
        print(f"         ⏱️  External watchdog started: {timeout_seconds}s (server timeout: {server_timeout}s + 30s buffer)")
        
        while time.time() - start_time < timeout_seconds:
            if server_proc.poll() is not None:
                print(f"         ✅ Server process completed naturally")
                break
            time.sleep(2)
        else:
            # Timeout reached - give server 5 seconds to finish writing logs
            print(f"         ⏰ External timeout reached, allowing server to finish writing...")
            time.sleep(5)
        
        # Kill all processes gracefully, giving them time to finish I/O
        for proc_name, proc in [("server", server_proc), ("player1", player1_proc), ("player2", player2_proc)]:
            try:
                if proc.poll() is None:  # Still running
                    # Try to terminate gracefully first (allows cleanup)
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)  # Give 5 seconds for graceful shutdown
                        print(f"         ✓ {proc_name} terminated gracefully")
                    except subprocess.TimeoutExpired:
                        # Force kill if terminate doesn't work
                        proc.kill()
                        proc.wait(timeout=2)
                        print(f"         ⚠️  {proc_name} force killed")
                else:
                    print(f"         ✓ {proc_name} already finished")
            except Exception as e:
                print(f"         ❌ Error killing {proc_name}: {e}")
                pass
        
        # Aggressively kill any remaining processes for this board
        try:
            # Kill web server
            subprocess.run(
                ['pkill', '-9', '-f', f'web_server.py.*{PORT}.*{board_size}'],
                capture_output=True,
                timeout=2
            )
            # Kill test bots
            subprocess.run(
                ['pkill', '-9', '-f', f'test_bot_student.py.*{PORT}.*{board_size}'],
                capture_output=True,
                timeout=2
            )
            # Kill any python processes with the port
            subprocess.run(
                ['pkill', '-9', '-f', f'python.*{PORT}'],
                capture_output=True,
                timeout=2
            )
        except:
            pass
        
        # Wait for processes to fully terminate and port to be released
        time.sleep(4)
        
        # Parse result from server log (preferred) or player1 log (fallback)
        winner, circle_score, square_score, error = self.parse_game_result(player1_log, server_log)
        
        if winner:
            result_msg = f"{board_size}: Winner = {winner}, Scores = {circle_score}-{square_score}"
            if error:
                result_msg += f" ({error})"
            print(f"         ✅ {result_msg}")
        else:
            print(f"         ⚠️  {board_size}: {error}")
        
        return winner, circle_score, square_score, error
    
    def create_match_summary(self, match_dir, results):
        """Create a comprehensive match summary file"""
        summary_file = match_dir / 'match_summary.txt'
        
        with open(summary_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write(f"MATCH SUMMARY - Match {results['match_num']}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Player 1 (Circle): {results['player1']} (ID: {results['player1_id']})\n")
            f.write(f"Player 2 (Square): {results['player2']} (ID: {results['player2_id']})\n")
            f.write(f"Timestamp: {results.get('timestamp', 'N/A')}\n\n")
            
            # Summary table
            f.write("-" * 80 + "\n")
            f.write(f"{'Board Size':<15} {'Winner':<15} {'Circle Score':<15} {'Square Score':<15} {'Status':<20}\n")
            f.write("-" * 80 + "\n")
            
            total_p1_wins = 0
            total_p2_wins = 0
            total_draws = 0
            total_errors = 0
            
            for board_size in BOARD_SIZES:
                winner = results.get(f'{board_size}_winner', 'error')
                p1_score = results.get(f'{board_size}_player1_score', '')
                p2_score = results.get(f'{board_size}_player2_score', '')
                error_msg = results.get(f'{board_size}_error', '')
                
                # Count results
                if winner == 'circle':
                    total_p1_wins += 1
                elif winner == 'square':
                    total_p2_wins += 1
                elif winner == 'draw':
                    total_draws += 1
                else:
                    total_errors += 1
                
                # Format scores
                score_str_circle = f"{p1_score:.1f}" if p1_score != '' else 'N/A'
                score_str_square = f"{p2_score:.1f}" if p2_score != '' else 'N/A'
                
                # Status message (truncate if too long)
                status = error_msg if error_msg else 'Completed'
                if len(status) > 35:
                    status = status[:32] + "..."
                
                f.write(f"{board_size.capitalize():<15} {winner.capitalize():<15} {score_str_circle:<15} {score_str_square:<15} {status:<20}\n")
            
            f.write("-" * 80 + "\n\n")
            
            # Overall match result
            f.write("MATCH RESULT:\n")
            f.write(f"  Player 1 (Circle) wins: {total_p1_wins}\n")
            f.write(f"  Player 2 (Square) wins: {total_p2_wins}\n")
            f.write(f"  Draws: {total_draws}\n")
            f.write(f"  Errors: {total_errors}\n\n")
            
            if total_p1_wins > total_p2_wins:
                f.write(f"🏆 OVERALL WINNER: Player 1 - {results['player1']}\n")
            elif total_p2_wins > total_p1_wins:
                f.write(f"🏆 OVERALL WINNER: Player 2 - {results['player2']}\n")
            else:
                f.write(f"🤝 MATCH TIED\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("DETAILED RESULTS BY BOARD SIZE\n")
            f.write("=" * 80 + "\n\n")
            
            # Detailed results for each board
            for board_size in BOARD_SIZES:
                winner = results.get(f'{board_size}_winner', 'error')
                p1_score = results.get(f'{board_size}_player1_score', '')
                p2_score = results.get(f'{board_size}_player2_score', '')
                error_msg = results.get(f'{board_size}_error', '')
                
                f.write(f"{board_size.upper()} BOARD:\n")
                f.write(f"  Winner: {winner.capitalize()}\n")
                f.write(f"  Circle Score: {p1_score if p1_score != '' else 'N/A'}\n")
                f.write(f"  Square Score: {p2_score if p2_score != '' else 'N/A'}\n")
                
                if error_msg:
                    f.write(f"  Termination: {error_msg}\n")
                
                f.write(f"  Logs:\n")
                f.write(f"    - Server: {board_size}_server.log\n")
                f.write(f"    - Player 1: {board_size}_player1.log\n")
                f.write(f"    - Player 2: {board_size}_player2.log\n")
                f.write("\n")
            
            f.write("=" * 80 + "\n")
        
        print(f"      📄 Match summary saved to: {summary_file.name}")
    
    def run_match(self, player1_dir, player2_dir, match_num):
        """Run a complete match (all board sizes) between two players"""
        player1_id = player1_dir.name.replace('submission_', '')
        player2_id = player2_dir.name.replace('submission_', '')
        match_name = f"match_{match_num}_{player1_id}_vs_{player2_id}"
        
        print(f"\n🎯 Match {match_num}: {player1_dir.name} (Circle) vs {player2_dir.name} (Square)")
        
        # Create match directory
        match_dir = self.matches_dir / match_name
        player1_temp, player2_temp = self.setup_match_directory(match_dir, player1_dir, player2_dir)
        
        results = {
            'match_num': match_num,
            'player1': player1_dir.name,
            'player2': player2_dir.name,
            'player1_id': player1_id,
            'player2_id': player2_id,
        }
        
        # Run games for each board size
        for board_size in BOARD_SIZES:
            log_prefix = board_size
            winner, circle_score, square_score, error = self.run_game(
                match_dir, player1_temp, player2_temp, board_size, log_prefix
            )
            
            results[f'{board_size}_winner'] = winner or 'error'
            results[f'{board_size}_player1_score'] = circle_score if circle_score is not None else ''
            results[f'{board_size}_player2_score'] = square_score if square_score is not None else ''
            results[f'{board_size}_error'] = error or ''
            
            # Wait longer between games to ensure port is released
            print(f"      ⏳ Waiting for port cleanup...")
            time.sleep(5)
        
        # Add timestamp before creating summary
        results['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Create match summary
        self.create_match_summary(match_dir, results)
        
        return results
    
    def run_tournament(self):
        """Run complete round-robin tournament"""
        print(f"\n{'='*80}")
        print(f"🏆 Starting Tournament: {self.group_name}")
        print(f"{'='*80}\n")
        
        # Generate all matches (each pair plays once)
        matches = list(combinations(self.submissions, 2))
        total_matches = len(matches)
        
        print(f"📋 Total matches to play: {total_matches}")
        print(f"🎮 Board sizes: {', '.join(BOARD_SIZES)}")
        print(f"⏱️  Time limits: Small={TIME_LIMITS['small']}s, Medium={TIME_LIMITS['medium']}s, Large={TIME_LIMITS['large']}s\n")
        
        # Initialize CSV
        csv_fields = [
            'match_num', 'player1', 'player2', 'player1_id', 'player2_id',
        ]
        for board_size in BOARD_SIZES:
            csv_fields.extend([
                f'{board_size}_winner',
                f'{board_size}_player1_score',
                f'{board_size}_player2_score',
                f'{board_size}_error'
            ])
        csv_fields.append('timestamp')
        
        with open(self.csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
        
        # Run all matches
        for match_num, (player1, player2) in enumerate(matches, 1):
            try:
                results = self.run_match(player1, player2, match_num)
                # Timestamp already added in run_match
                
                # Save to CSV
                with open(self.csv_file, 'a', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=csv_fields)
                    writer.writerow(results)
                
                print(f"✅ Match {match_num}/{total_matches} completed")
                
            except Exception as e:
                print(f"❌ Match {match_num} failed: {str(e)}")
                import traceback
                traceback.print_exc()
        
        print(f"\n{'='*80}")
        print(f"🏁 Tournament Complete!")
        print(f"📊 Results saved to: {self.csv_file}")
        print(f"📁 Match logs saved to: {self.matches_dir}")
        print(f"{'='*80}\n")
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print tournament summary"""
        if not self.csv_file.exists():
            return
        
        print("\n📊 TOURNAMENT SUMMARY\n")
        
        # Read results
        with open(self.csv_file, 'r') as f:
            reader = csv.DictReader(f)
            results = list(reader)
        
        # Calculate scores for each player
        player_scores = {}
        for sub in self.submissions:
            player_scores[sub.name] = {'wins': 0, 'losses': 0, 'draws': 0, 'errors': 0, 'total_score': 0}
        
        for result in results:
            player1 = result['player1']
            player2 = result['player2']
            
            for board_size in BOARD_SIZES:
                winner = result[f'{board_size}_winner']
                p1_score = result[f'{board_size}_player1_score']
                p2_score = result[f'{board_size}_player2_score']
                
                if winner == 'circle':
                    player_scores[player1]['wins'] += 1
                    player_scores[player2]['losses'] += 1
                elif winner == 'square':
                    player_scores[player1]['losses'] += 1
                    player_scores[player2]['wins'] += 1
                elif winner == 'draw':
                    player_scores[player1]['draws'] += 1
                    player_scores[player2]['draws'] += 1
                else:
                    player_scores[player1]['errors'] += 1
                    player_scores[player2]['errors'] += 1
                
                if p1_score:
                    player_scores[player1]['total_score'] += float(p1_score)
                if p2_score:
                    player_scores[player2]['total_score'] += float(p2_score)
        
        # Print standings
        print(f"{'Player':<30} {'Wins':<8} {'Losses':<8} {'Draws':<8} {'Errors':<8} {'Total Score':<12}")
        print("-" * 80)
        
        # Sort by wins, then total score
        sorted_players = sorted(
            player_scores.items(),
            key=lambda x: (x[1]['wins'], x[1]['total_score']),
            reverse=True
        )
        
        for player, stats in sorted_players:
            print(f"{player:<30} {stats['wins']:<8} {stats['losses']:<8} {stats['draws']:<8} {stats['errors']:<8} {stats['total_score']:<12.2f}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python run_tournament.py <group_directory> [output_directory]")
        print("Example: python run_tournament.py /path/to/Groups/Group1")
        sys.exit(1)
    
    group_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else './tournament_results'
    
    if not os.path.exists(group_dir):
        print(f"❌ Error: Group directory not found: {group_dir}")
        sys.exit(1)
    
    runner = TournamentRunner(group_dir, output_dir)
    runner.run_tournament()


if __name__ == '__main__':
    main()
