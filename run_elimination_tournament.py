#!/usr/bin/env python3
"""
Single Elimination Tournament System
Runs a 32-team seeded single-elimination tournament
Bracket: #1 vs #32, #2 vs #31, etc.
"""

import os
import sys
import subprocess
import time
import csv
import json
from datetime import datetime
import shutil
from pathlib import Path
import re
from multiprocessing import Pool, Manager
import threading
from functools import partial

# Configuration
SEEDS_FILE = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/elimination_seeds_T1.csv")
PLAYERS_BASE = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/Tournament_1/Group_Stage")
OUTPUT_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/Tournament_T1_Elimination_Stage_Results")
MANUAL_TEST_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/manual_test")
EVAL_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation")

# Tournament T1 Configuration
BASE_PORT = 9600  # Base port for parallel execution
TOURNAMENT_MODE = "T1"  # T1 = small board only with role swap
BOARD_SIZES = ['small']  # Only small board for T1

# Time limits per player (as per T1 requirements)
SERVER_TIME_LIMITS = {
    'small': 120,   # 2 minutes per player
}

# External watchdog timeout (generous to allow games to complete)
TIME_LIMITS = {
    'small': 300,   # 5 minutes total for external watchdog
}

# Parallel execution settings
MAX_PARALLEL_MATCHES = 16  # Run up to 16 matches in parallel (Round of 32)

# Global function for parallel execution (needs to be at module level for pickle)
def run_single_match_parallel(args):
    """Global function to run a single match (for multiprocessing)"""
    match_info, round_name, match_num, port = args
    
    # Create a temporary tournament instance for this match
    tournament = EliminationTournament()
    winner, results = tournament.run_match(match_info, round_name, match_num, port)
    return winner, results

class EliminationTournament:
    def __init__(self):
        self.seeds = self.load_seeds()
        self.bracket = self.create_bracket()
        self.results = []
        self.port_lock = threading.Lock()
        self.next_port = BASE_PORT
        
        # Create output directories
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.matches_dir = OUTPUT_DIR / 'matches'
        self.matches_dir.mkdir(exist_ok=True)
        
        print(f"🏆 SINGLE ELIMINATION TOURNAMENT")
        print(f"📁 Output directory: {OUTPUT_DIR}")
        print(f"👥 {len(self.seeds)} seeded players")
        print()
    
    def get_next_port(self):
        """Get next available port for parallel execution"""
        with self.port_lock:
            port = self.next_port
            self.next_port += 1
            return port
    
    def load_seeds(self):
        """Load seeded players from CSV"""
        seeds = []
        with open(SEEDS_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                seeds.append({
                    'seed': int(row['seed']),
                    'group': row['group'],
                    'player': row['player'],
                    'wins': int(row['wins']),
                    'total_score': float(row['total_score'])
                })
        return seeds
    
    def create_bracket(self):
        """Create seeded bracket: #1 vs #32, #2 vs #31, etc."""
        bracket = {
            'round_of_32': [],
            'round_of_16': [],
            'quarterfinals': [],
            'semifinals': [],
            'final': None,
            'champion': None
        }
        
        # Round of 32: Seed n vs Seed (33 - n)
        num_seeds = len(self.seeds)
        for i in range(num_seeds // 2):
            high_seed = self.seeds[i]
            low_seed = self.seeds[num_seeds - 1 - i]
            bracket['round_of_32'].append({
                'match_id': i + 1,
                'player1': high_seed,
                'player2': low_seed
            })
        
        return bracket
    
    def get_player_path(self, group, player):
        """Get the path to player's submission directory"""
        group_dir = PLAYERS_BASE / group
        player_path = group_dir / player
        if player_path.exists():
            return player_path
        return None
    
    def compile_cpp_submission(self, submission_dir, temp_dir):
        """Compile C++ submission if needed"""
        if not (submission_dir / 'CMakeLists.txt').exists():
            return False, "No CMakeLists.txt found"
        
        python_exe = "/home/aayush/anaconda3/envs/Aayush_env/bin/python"
        build_dir = temp_dir / 'build'
        
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
                return False, "Could not find pybind11"
            
            pybind11_dir = pybind11_result.stdout.strip()
            
            # Configure and build
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
                return False, "CMake configure failed"
            
            result = subprocess.run(
                ['cmake', '--build', '.', '--config', 'Release'],
                cwd=build_dir,
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode != 0:
                return False, "Build failed"
            
            so_files = list(build_dir.glob('*.so'))
            if not so_files:
                return False, "No .so file generated"
            
            return True, "Compilation successful"
            
        except Exception as e:
            return False, str(e)[:200]
    
    def setup_match_directory(self, match_dir, player1_info, player2_info):
        """Setup match directory with player submissions"""
        match_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy reference files
        for file in ['gameEngine.py', 'agent.py', 'bot_client.py', 'web_server.py']:
            src = MANUAL_TEST_DIR / file
            if src.exists():
                shutil.copy2(src, match_dir)
        
        for file in ['test_bot_student.py']:
            src = EVAL_DIR / file
            if src.exists():
                shutil.copy2(src, match_dir)
        
        # Copy templates
        templates_src = MANUAL_TEST_DIR / 'templates'
        if templates_src.exists():
            templates_dst = match_dir / 'templates'
            if templates_dst.exists():
                shutil.rmtree(templates_dst)
            shutil.copytree(templates_src, templates_dst)
        
        # Setup player directories
        for player_info, player_name in [(player1_info, 'player1'), (player2_info, 'player2')]:
            player_path = self.get_player_path(player_info['group'], player_info['player'])
            if not player_path:
                print(f"   ❌ Player path not found: {player_info['group']}/{player_info['player']}")
                continue
            
            player_dir = match_dir / player_name
            if player_dir.exists():
                shutil.rmtree(player_dir)
            shutil.copytree(player_path, player_dir)
            
            # Copy gameEngine and agent
            for file in ['gameEngine.py', 'agent.py']:
                src = MANUAL_TEST_DIR / file
                if src.exists():
                    shutil.copy2(src, player_dir)
            
            # Compile if C++
            if (player_dir / 'CMakeLists.txt').exists():
                print(f"   🔨 Compiling {player_name}...")
                success, msg = self.compile_cpp_submission(player_dir, player_dir)
                if success:
                    print(f"   ✅ {player_name} compiled")
                else:
                    print(f"   ⚠️  {player_name} compilation warning: {msg}")
        
        return match_dir / 'player1', match_dir / 'player2'
    
    def parse_game_result(self, player1_log, server_log):
        """Parse game result from logs"""
        logs_to_check = []
        if server_log and server_log.exists():
            logs_to_check.append(server_log)
        if player1_log.exists():
            logs_to_check.append(player1_log)
        
        winner = None
        circle_score = None
        square_score = None
        
        for log_path in logs_to_check:
            with open(log_path, 'r') as f:
                content = f.read()
            
            # Look for scores
            score_match = re.search(r'Final Scores - Circle:\s*(\d+\.?\d*),\s*Square:\s*(\d+\.?\d*)', content, re.IGNORECASE)
            if score_match:
                circle_score = float(score_match.group(1))
                square_score = float(score_match.group(2))
                winner = 'circle' if circle_score > square_score else 'square' if square_score > circle_score else 'draw'
                break
            
            # Look for winner
            winner_match = re.search(r'Winner:\s*(\w+)', content, re.IGNORECASE)
            if winner_match:
                winner = winner_match.group(1).lower()
        
        error = None if winner else "No result found"
        return winner, circle_score, square_score, error
    
    def run_game(self, match_dir, board_size, log_prefix, player1_role, player2_role, port):
        """Run a single game with specified roles
        
        Args:
            match_dir: Directory for match files
            board_size: 'small', 'medium', or 'large'
            log_prefix: Prefix for log files (e.g., 'small_game1')
            player1_role: 'circle' or 'square' for player1
            player2_role: 'circle' or 'square' for player2
            port: Port number to use for this game
        """
        print(f"      🎮 Running {board_size} board ({log_prefix}) on port {port}...")
        print(f"         Player1: {player1_role}, Player2: {player2_role}")
        
        conda_python = 'bash -c "source ~/anaconda3/etc/profile.d/conda.sh && conda activate Aayush_env && python -u'
        
        # Start server
        server_log = match_dir / f'{log_prefix}_server.log'
        with open(server_log, 'w') as f:
            server_proc = subprocess.Popen(
                f'{conda_python} web_server.py {port} {board_size}"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True,
                env={**os.environ, 'DISPLAY': ''}
            )
        
        time.sleep(2)
        
        # Start players with their assigned roles
        player1_log = match_dir / f'{log_prefix}_player1.log'
        player2_log = match_dir / f'{log_prefix}_player2.log'
        
        with open(player1_log, 'w') as f:
            player1_proc = subprocess.Popen(
                f'{conda_python} test_bot_student.py player1 {port} {board_size} {player1_role}"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True
            )
        
        time.sleep(1)
        
        with open(player2_log, 'w') as f:
            player2_proc = subprocess.Popen(
                f'{conda_python} test_bot_student.py player2 {port} {board_size} {player2_role}"',
                cwd=match_dir,
                stdout=f,
                stderr=subprocess.STDOUT,
                shell=True
            )
        
        # Wait for completion
        timeout = TIME_LIMITS[board_size]
        start_time = time.time()
        while time.time() - start_time < timeout:
            if server_proc.poll() is not None:
                break
            time.sleep(2)
        
        # Cleanup
        for proc in [server_proc, player1_proc, player2_proc]:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except:
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except:
                    pass
        
        # Kill remaining processes
        subprocess.run(['pkill', '-9', '-f', f'web_server.py.*{port}'], capture_output=True, timeout=2)
        subprocess.run(['pkill', '-9', '-f', f'test_bot.*{port}'], capture_output=True, timeout=2)
        time.sleep(4)
        
        # Parse result
        winner, circle_score, square_score, error = self.parse_game_result(player1_log, server_log)
        
        if winner:
            print(f"         ✅ Winner: {winner}, Scores: C:{circle_score} S:{square_score}")
        else:
            print(f"         ⚠️  {error}")
        
        return winner, circle_score, square_score, error
    
    def run_match(self, match_info, round_name, match_num, port=None):
        """Run a complete match (T1 format with role swaps)"""
        player1 = match_info['player1']
        player2 = match_info['player2']
        
        # Get port if not provided
        if port is None:
            port = self.get_next_port()
        
        print(f"\n{'='*100}")
        print(f"🎯 {round_name} - Match {match_num} (Port {port})")
        print(f"   Seed #{player1['seed']} {player1['player']}")
        print(f"      vs")
        print(f"   Seed #{player2['seed']} {player2['player']}")
        print(f"{'='*100}")
        
        # Create match directory
        match_dir = self.matches_dir / f"{round_name.replace(' ', '_')}_match_{match_num}"
        self.setup_match_directory(match_dir, player1, player2)
        
        results = {
            'round': round_name,
            'match_num': match_num,
            'player1_seed': player1['seed'],
            'player1_name': player1['player'],
            'player1_group': player1['group'],
            'player2_seed': player2['seed'],
            'player2_name': player2['player'],
            'player2_group': player2['group'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # Run games with role swaps (T1 format)
        p1_wins = 0
        p2_wins = 0
        p1_total_score = 0.0
        p2_total_score = 0.0
        
        for board_size in BOARD_SIZES:
            if TOURNAMENT_MODE == "T1":
                # Game 1: player1 as circle, player2 as square
                print(f"\n   📋 {board_size.upper()} BOARD - Game 1")
                log_prefix = f'{board_size}_game1'
                winner_g1, circle_score_g1, square_score_g1, error_g1 = self.run_game(
                    match_dir, board_size, log_prefix, 'circle', 'square', port
                )
                
                results[f'{board_size}_game1_winner'] = winner_g1 or 'error'
                results[f'{board_size}_game1_player1_score'] = circle_score_g1 if circle_score_g1 is not None else ''
                results[f'{board_size}_game1_player2_score'] = square_score_g1 if square_score_g1 is not None else ''
                results[f'{board_size}_game1_error'] = error_g1 or ''
                
                if circle_score_g1 is not None:
                    p1_total_score += circle_score_g1
                if square_score_g1 is not None:
                    p2_total_score += square_score_g1
                
                print(f"      ⏳ Waiting for port cleanup before Game 2...")
                time.sleep(5)
                
                # Game 2: player2 as circle, player1 as square
                print(f"\n   📋 {board_size.upper()} BOARD - Game 2")
                log_prefix = f'{board_size}_game2'
                winner_g2, circle_score_g2, square_score_g2, error_g2 = self.run_game(
                    match_dir, board_size, log_prefix, 'square', 'circle', port
                )
                
                results[f'{board_size}_game2_winner'] = winner_g2 or 'error'
                results[f'{board_size}_game2_player1_score'] = square_score_g2 if square_score_g2 is not None else ''
                results[f'{board_size}_game2_player2_score'] = circle_score_g2 if circle_score_g2 is not None else ''
                results[f'{board_size}_game2_error'] = error_g2 or ''
                
                if square_score_g2 is not None:
                    p1_total_score += square_score_g2
                if circle_score_g2 is not None:
                    p2_total_score += circle_score_g2
                
                # Count wins
                if winner_g1 == 'circle':
                    p1_wins += 1
                elif winner_g1 == 'square':
                    p2_wins += 1
                
                if winner_g2 == 'circle':
                    p2_wins += 1
                elif winner_g2 == 'square':
                    p1_wins += 1
                
                results[f'{board_size}_player1_total_score'] = p1_total_score
                results[f'{board_size}_player2_total_score'] = p2_total_score
            else:
                # Standard mode: single game
                log_prefix = board_size
                winner, circle_score, square_score, error = self.run_game(
                    match_dir, board_size, log_prefix, 'circle', 'square', port
                )
                
                results[f'{board_size}_winner'] = winner or 'error'
                results[f'{board_size}_circle_score'] = circle_score if circle_score is not None else ''
                results[f'{board_size}_square_score'] = square_score if square_score is not None else ''
                results[f'{board_size}_error'] = error or ''
                
                if winner == 'circle':
                    p1_wins += 1
                elif winner == 'square':
                    p2_wins += 1
            
            time.sleep(5)
        
        # Determine match winner with tiebreaker logic
        if p1_wins > p2_wins:
            match_winner = player1
            results['match_winner'] = player1['player']
            results['match_winner_seed'] = player1['seed']
            print(f"\n🏆 Match Winner: Seed #{match_winner['seed']} {match_winner['player']}")
            print(f"   Final: Player1 {p1_wins} wins ({p1_total_score:.2f} pts) vs Player2 {p2_wins} wins ({p2_total_score:.2f} pts)")
        elif p2_wins > p1_wins:
            match_winner = player2
            results['match_winner'] = player2['player']
            results['match_winner_seed'] = player2['seed']
            print(f"\n🏆 Match Winner: Seed #{match_winner['seed']} {match_winner['player']}")
            print(f"   Final: Player1 {p1_wins} wins ({p1_total_score:.2f} pts) vs Player2 {p2_wins} wins ({p2_total_score:.2f} pts)")
        else:
            # TIE - Apply tiebreaker rules
            print(f"\n⚖️  TIE DETECTED: Both players have {p1_wins} wins")
            print(f"   Scores: Player1 {p1_total_score:.2f} pts vs Player2 {p2_total_score:.2f} pts")
            
            # Tiebreaker Battle 1: 1 minute per player
            print(f"\n🔥 TIEBREAKER BATTLE 1 (60 seconds per player)")
            
            # Temporarily change time limits for tiebreaker
            original_time_limit = SERVER_TIME_LIMITS['small']
            original_watchdog = TIME_LIMITS['small']
            SERVER_TIME_LIMITS['small'] = 60  # 1 minute per player
            TIME_LIMITS['small'] = 150  # 2.5 minutes watchdog
            
            # Tiebreaker game 1: player1 as circle, player2 as square
            log_prefix = 'tiebreaker1_game1'
            tb1_winner_g1, tb1_circle_g1, tb1_square_g1, tb1_error_g1 = self.run_game(
                match_dir, 'small', log_prefix, 'circle', 'square', port
            )
            time.sleep(5)
            
            # Tiebreaker game 2: player2 as circle, player1 as square
            log_prefix = 'tiebreaker1_game2'
            tb1_winner_g2, tb1_circle_g2, tb1_square_g2, tb1_error_g2 = self.run_game(
                match_dir, 'small', log_prefix, 'square', 'circle', port
            )
            
            tb1_p1_wins = 0
            tb1_p2_wins = 0
            tb1_p1_score = (tb1_circle_g1 or 0) + (tb1_square_g2 or 0)
            tb1_p2_score = (tb1_square_g1 or 0) + (tb1_circle_g2 or 0)
            
            if tb1_winner_g1 == 'circle':
                tb1_p1_wins += 1
            elif tb1_winner_g1 == 'square':
                tb1_p2_wins += 1
            
            if tb1_winner_g2 == 'circle':
                tb1_p2_wins += 1
            elif tb1_winner_g2 == 'square':
                tb1_p1_wins += 1
            
            results['tiebreaker1_p1_wins'] = tb1_p1_wins
            results['tiebreaker1_p2_wins'] = tb1_p2_wins
            results['tiebreaker1_p1_score'] = tb1_p1_score
            results['tiebreaker1_p2_score'] = tb1_p2_score
            
            print(f"   Tiebreaker 1 Result: P1 {tb1_p1_wins}W ({tb1_p1_score:.2f}) vs P2 {tb1_p2_wins}W ({tb1_p2_score:.2f})")
            
            if tb1_p1_wins > tb1_p2_wins:
                match_winner = player1
                results['tiebreaker'] = 'tiebreaker_battle_1'
            elif tb1_p2_wins > tb1_p1_wins:
                match_winner = player2
                results['tiebreaker'] = 'tiebreaker_battle_1'
            else:
                # Still tied - Tiebreaker Battle 2: 30 seconds per player
                print(f"\n🔥 STILL TIED - TIEBREAKER BATTLE 2 (30 seconds per player)")
                time.sleep(5)
                
                SERVER_TIME_LIMITS['small'] = 30  # 30 seconds per player
                TIME_LIMITS['small'] = 90  # 1.5 minutes watchdog
                
                # Tiebreaker 2 game 1
                log_prefix = 'tiebreaker2_game1'
                tb2_winner_g1, tb2_circle_g1, tb2_square_g1, tb2_error_g1 = self.run_game(
                    match_dir, 'small', log_prefix, 'circle', 'square', port
                )
                time.sleep(5)
                
                # Tiebreaker 2 game 2
                log_prefix = 'tiebreaker2_game2'
                tb2_winner_g2, tb2_circle_g2, tb2_square_g2, tb2_error_g2 = self.run_game(
                    match_dir, 'small', log_prefix, 'square', 'circle', port
                )
                
                tb2_p1_wins = 0
                tb2_p2_wins = 0
                tb2_p1_score = (tb2_circle_g1 or 0) + (tb2_square_g2 or 0)
                tb2_p2_score = (tb2_square_g1 or 0) + (tb2_circle_g2 or 0)
                
                if tb2_winner_g1 == 'circle':
                    tb2_p1_wins += 1
                elif tb2_winner_g1 == 'square':
                    tb2_p2_wins += 1
                
                if tb2_winner_g2 == 'circle':
                    tb2_p2_wins += 1
                elif tb2_winner_g2 == 'square':
                    tb2_p1_wins += 1
                
                results['tiebreaker2_p1_wins'] = tb2_p1_wins
                results['tiebreaker2_p2_wins'] = tb2_p2_wins
                results['tiebreaker2_p1_score'] = tb2_p1_score
                results['tiebreaker2_p2_score'] = tb2_p2_score
                
                print(f"   Tiebreaker 2 Result: P1 {tb2_p1_wins}W ({tb2_p1_score:.2f}) vs P2 {tb2_p2_wins}W ({tb2_p2_score:.2f})")
                
                if tb2_p1_wins > tb2_p2_wins:
                    match_winner = player1
                    results['tiebreaker'] = 'tiebreaker_battle_2'
                elif tb2_p2_wins > tb2_p1_wins:
                    match_winner = player2
                    results['tiebreaker'] = 'tiebreaker_battle_2'
                else:
                    # Still tied - Use group stage performance
                    print(f"\n⚖️  STILL TIED - Using group stage performance (higher seed wins)")
                    match_winner = player1 if player1['seed'] < player2['seed'] else player2
                    results['tiebreaker'] = 'group_stage_seed'
            
            # Restore original time limits
            SERVER_TIME_LIMITS['small'] = original_time_limit
            TIME_LIMITS['small'] = original_watchdog
            
            results['match_winner'] = match_winner['player']
            results['match_winner_seed'] = match_winner['seed']
            
            print(f"\n🏆 Match Winner (via {results['tiebreaker']}): Seed #{match_winner['seed']} {match_winner['player']}")
        
        return match_winner, results
    
    def run_round_parallel(self, matches, round_name):
        """Run all matches in a round in parallel"""
        print(f"\n{'='*100}")
        print(f"🎯 {round_name.upper()} - Running {len(matches)} matches in PARALLEL")
        print(f"{'='*100}")
        
        # Assign ports to each match
        args_list = []
        for i, match in enumerate(matches, 1):
            port = BASE_PORT + i - 1
            args_list.append((match, round_name, i, port))
        
        print(f"🚀 Launching {len(args_list)} matches in parallel on ports {BASE_PORT} to {BASE_PORT + len(args_list) - 1}")
        
        # Run matches in parallel using multiprocessing
        num_workers = min(len(args_list), MAX_PARALLEL_MATCHES)
        with Pool(processes=num_workers) as pool:
            results_list = pool.map(run_single_match_parallel, args_list)
        
        # Separate winners and results
        winners = [result[0] for result in results_list]
        all_results = [result[1] for result in results_list]
        
        print(f"✅ All {len(matches)} matches completed")
        
        return winners, all_results
    
    def run_tournament(self):
        """Run complete elimination tournament"""
        print("\n" + "="*100)
        print("🏆 STARTING SINGLE ELIMINATION TOURNAMENT")
        print("="*100 + "\n")
        
        csv_file = OUTPUT_DIR / 'elimination_results.csv'
        
        # CSV fields for T1 format (small board only, 2 games with role swaps)
        csv_fields = [
            'round', 'match_num', 'player1_seed', 'player1_name', 'player1_group',
            'player2_seed', 'player2_name', 'player2_group', 'match_winner', 'match_winner_seed',
            # Small board game 1
            'small_game1_winner', 'small_game1_player1_score', 'small_game1_player2_score', 'small_game1_error',
            # Small board game 2
            'small_game2_winner', 'small_game2_player1_score', 'small_game2_player2_score', 'small_game2_error',
            # Small board totals
            'small_player1_total_score', 'small_player2_total_score',
            # Tiebreaker info
            'tiebreaker', 'tiebreaker1_p1_wins', 'tiebreaker1_p2_wins', 'tiebreaker1_p1_score', 'tiebreaker1_p2_score',
            'tiebreaker2_p1_wins', 'tiebreaker2_p2_wins', 'tiebreaker2_p1_score', 'tiebreaker2_p2_score',
            'timestamp'
        ]
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields)
            writer.writeheader()
        
        # Round of 32 - Run in parallel
        round_of_16_players, round32_results = self.run_round_parallel(
            self.bracket['round_of_32'], "Round of 32"
        )
        for results in round32_results:
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
                writer.writerow(results)
        
        # Round of 16 - Run in parallel
        round16_matches = [
            {'player1': round_of_16_players[i], 'player2': round_of_16_players[i+1]}
            for i in range(0, len(round_of_16_players), 2)
        ]
        quarterfinal_players, round16_results = self.run_round_parallel(
            round16_matches, "Round of 16"
        )
        for results in round16_results:
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
                writer.writerow(results)
        
        # Quarterfinals - Run in parallel
        quarter_matches = [
            {'player1': quarterfinal_players[i], 'player2': quarterfinal_players[i+1]}
            for i in range(0, len(quarterfinal_players), 2)
        ]
        semifinal_players, quarter_results = self.run_round_parallel(
            quarter_matches, "Quarterfinals"
        )
        for results in quarter_results:
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
                writer.writerow(results)
        
        # Semifinals - Run in parallel
        semi_matches = [
            {'player1': semifinal_players[i], 'player2': semifinal_players[i+1]}
            for i in range(0, len(semifinal_players), 2)
        ]
        final_players, semi_results = self.run_round_parallel(
            semi_matches, "Semifinals"
        )
        for results in semi_results:
            with open(csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
                writer.writerow(results)
        
        # Final - Run single match
        print("\n\n" + "="*100)
        print("🎯 FINAL")
        print("="*100)
        match = {'player1': final_players[0], 'player2': final_players[1]}
        champion, results = self.run_match(match, "Final", 1, BASE_PORT)
        
        with open(csv_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
            writer.writerow(results)
        
        # Print champion
        print("\n" + "="*100)
        print(f"🏆🏆🏆 TOURNAMENT CHAMPION 🏆🏆🏆")
        print(f"Seed #{champion['seed']}: {champion['player']} from {champion['group']}")
        print("="*100 + "\n")
        
        # Save champion info
        with open(OUTPUT_DIR / 'champion.txt', 'w') as f:
            f.write("="*100 + "\n")
            f.write("ELIMINATION TOURNAMENT CHAMPION\n")
            f.write("="*100 + "\n\n")
            f.write(f"Seed: #{champion['seed']}\n")
            f.write(f"Player: {champion['player']}\n")
            f.write(f"Group: {champion['group']}\n")
            f.write(f"Original Wins: {champion['wins']}\n")
            f.write(f"Original Score: {champion['total_score']}\n")
            f.write("\n" + "="*100 + "\n")
        
        print(f"📊 Results saved to: {csv_file}")
        print(f"🏆 Champion info: {OUTPUT_DIR / 'champion.txt'}")


def main():
    tournament = EliminationTournament()
    tournament.run_tournament()


if __name__ == '__main__':
    main()
