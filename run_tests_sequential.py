#!/usr/bin/env python3
"""
Run all eligible submissions sequentially (one at a time).
"""

import os
import csv
import time
import subprocess
import signal
from pathlib import Path

# Configuration
SUBMISSIONS_CSV = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/results/submissions_list.csv"
EVALUATION_DIR = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation"
REFERENCE_DIR = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_2025_A5/client_server"
SUBMISSIONS_BASE = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/assignment_7153640_export"
REFERENCE_STUDENT_AGENT = "/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/assignment_7153640_export/submission_369109993"

# Configuration
PORT = 9500  # Single port for sequential execution
BOARD_SIZES = ['small', 'medium', 'large']
# Time limits based on board size (in seconds)
TIME_LIMITS = {
    'small': 120,   # 2 minutes
    'medium': 240,  # 4 minutes
    'large': 360    # 6 minutes
}

# Python executable
PYTHON_EXE = "/home/aayush/anaconda3/envs/Aayush_env/bin/python"

def test_submission(folder_name, student_id, group_info):
    """Test a single submission against reference student agent."""
    print(f"\n{'='*80}")
    print(f"Testing: {folder_name}")
    print(f"Group: {group_info}")
    print(f"Student ID(s): {student_id}")
    print(f"{'='*80}")
    
    try:
        # Create test directory for this submission
        test_dir = os.path.join(EVALUATION_DIR, 'temp_tests', folder_name)
        os.makedirs(test_dir, exist_ok=True)
        
        # Copy reference files
        for file in ['gameEngine.py', 'agent.py', 'bot_client.py']:
            src = os.path.join(REFERENCE_DIR, file)
            dst = os.path.join(test_dir, file)
            subprocess.run(['cp', src, dst], check=True, capture_output=True)
        
        # Copy updated web_server.py with repetition detection from manual_test
        web_server_src = os.path.join(EVALUATION_DIR, 'manual_test', 'web_server.py')
        web_server_dst = os.path.join(test_dir, 'web_server.py')
        subprocess.run(['cp', web_server_src, web_server_dst], check=True, capture_output=True)
        
        # Copy templates directory
        templates_src = os.path.join(REFERENCE_DIR, 'templates')
        templates_dst = os.path.join(test_dir, 'templates')
        if os.path.exists(templates_dst):
            subprocess.run(['rm', '-rf', templates_dst], check=True, capture_output=True)
        subprocess.run(['cp', '-r', templates_src, templates_dst], check=True, capture_output=True)
        
        # Copy all files from submission directory
        submission_dir = os.path.join(SUBMISSIONS_BASE, folder_name)
        for item in os.listdir(submission_dir):
            src_path = os.path.join(submission_dir, item)
            dst_path = os.path.join(test_dir, item)
            if os.path.isfile(src_path):
                subprocess.run(['cp', src_path, dst_path], check=True, capture_output=True)
            elif os.path.isdir(src_path):
                if os.path.exists(dst_path):
                    subprocess.run(['rm', '-rf', dst_path], check=True, capture_output=True)
                subprocess.run(['cp', '-r', src_path, dst_path], check=True, capture_output=True)
        
        # Choose board size (deterministic based on folder name)
        board_size = BOARD_SIZES[hash(folder_name) % len(BOARD_SIZES)]
        timeout_seconds = TIME_LIMITS[board_size]
        print(f"Board size: {board_size}")
        print(f"Time limit: {timeout_seconds}s ({timeout_seconds//60} minutes)")
        
        # Start web server
        server_log = os.path.join(test_dir, 'server.log')
        with open(server_log, 'w') as log_file:
            server_proc = subprocess.Popen(
                [PYTHON_EXE, 'web_server.py', str(PORT), board_size],
                cwd=test_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        # Wait for server to start
        print("Starting server...")
        time.sleep(15)
        
        # Check if server is running
        if server_proc.poll() is not None:
            with open(server_log, 'r') as f:
                error_msg = f.read()[-500:]
            print(f"❌ ERROR: Server failed to start")
            print(f"Error: {error_msg[:200]}")
            return {
                'folder_name': folder_name,
                'student_id': student_id,
                'status': 'ERROR',
                'error': f'Server failed to start: {error_msg[:200]}',
                'winner': '',
                'student_score': '',
                'random_score': '',
                'turns': ''
            }
        
        print("Server started successfully")
        
        # Start student bot (circle)
        student_log = os.path.join(test_dir, 'student_bot.log')
        with open(student_log, 'w') as log_file:
            student_proc = subprocess.Popen(
                [PYTHON_EXE, os.path.join(EVALUATION_DIR, 'test_bot_student.py'), 
                 test_dir, str(PORT), board_size],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        print("Student bot (circle) started")
        time.sleep(3)
        
        # Start reference student bot (square)
        random_log = os.path.join(test_dir, 'random_bot.log')
        with open(random_log, 'w') as log_file:
            random_proc = subprocess.Popen(
                [PYTHON_EXE, os.path.join(EVALUATION_DIR, 'test_bot_vs_student.py'), 
                 test_dir, str(PORT), board_size, REFERENCE_STUDENT_AGENT],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        print("Reference student bot (square) started")
        print(f"Game in progress... (timeout: {timeout_seconds}s)")
        
        # Wait for game to complete or timeout
        start_time = time.time()
        game_completed = False
        
        while time.time() - start_time < timeout_seconds:
            # Check if both bots have finished (game complete)
            if student_proc.poll() is not None and random_proc.poll() is not None:
                game_completed = True
                elapsed = time.time() - start_time
                print(f"✅ Game completed in {elapsed:.1f} seconds")
                break
            time.sleep(2)
        
        if not game_completed:
            print(f"⏱️  TIMEOUT: Game did not complete within {timeout_seconds}s")
        
        # Kill all processes
        for proc in [server_proc, student_proc, random_proc]:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                proc.wait(timeout=5)
            except:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except:
                    pass
        
        # Parse results from server log
        result = parse_game_result(server_log, student_log, random_log, folder_name, student_id)
        
        print(f"Result: {result['status']}")
        if result['winner']:
            print(f"Winner: {result['winner']}")
        if result['error']:
            print(f"Error: {result['error'][:100]}")
        
        return result
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)[:100]}")
        import traceback
        traceback.print_exc()
        return {
            'folder_name': folder_name,
            'student_id': student_id,
            'status': 'ERROR',
            'error': str(e)[:200],
            'winner': '',
            'student_score': '',
            'random_score': '',
            'turns': ''
        }

def parse_game_result(server_log, student_log, random_log, folder_name, student_id):
    """Parse game result from logs."""
    try:
        # Check for errors in student bot
        with open(student_log, 'r') as f:
            student_content = f.read()
        
        if 'error' in student_content.lower() or 'exception' in student_content.lower() or 'traceback' in student_content.lower():
            error_lines = [line for line in student_content.split('\n') 
                          if 'error' in line.lower() or 'exception' in line.lower()]
            error_msg = error_lines[0] if error_lines else 'Student bot error'
            return {
                'folder_name': folder_name,
                'student_id': student_id,
                'status': 'ERROR',
                'error': error_msg[:200],
                'winner': '',
                'student_score': '',
                'random_score': '',
                'turns': ''
            }
        
        # Check server log for game completion
        with open(server_log, 'r') as f:
            log_content = f.read()
        
        import re
        winner = ''
        player1_score = ''
        player2_score = ''
        turns = ''
        reason = ''
        
        lines = log_content.split('\n')
        for line in lines:
            # Check for repetition (opponent wins)
            if 'Repetition/stalemate detected' in line:
                # Next line should have Winner info
                reason = 'Repetition detected - opponent wins'
            
            # Look for explicit winner declaration
            if 'Winner:' in line:
                if 'circle' in line.lower():
                    winner = 'student'
                elif 'square' in line.lower():
                    winner = 'random'
            
            # Look for game finished with winner
            if 'Game finished' in line and 'Winner:' in line:
                if 'circle' in line.lower():
                    winner = 'student'
                elif 'square' in line.lower():
                    winner = 'random'
            
            # Check for timeout (opponent wins)
            if 'timeout' in line.lower() and 'winner' in line.lower():
                if 'circle' in line.lower():
                    winner = 'student'
                    reason = 'Opponent timeout'
                elif 'square' in line.lower():
                    winner = 'random'
                    reason = 'Opponent timeout'
            
            # Look for scores - format: "Final Scores - Circle: X.XX, Square: Y.YY"
            if 'Final Scores' in line:
                # Extract circle and square scores
                circle_match = re.search(r'Circle:\s*([\d.]+)', line)
                square_match = re.search(r'Square:\s*([\d.]+)', line)
                if circle_match:
                    player1_score = circle_match.group(1)
                if square_match:
                    player2_score = square_match.group(1)
            
            # Look for turns
            if 'turn' in line.lower() and 'turn_count' not in line.lower():
                turn_nums = re.findall(r'\d+', line)
                if turn_nums:
                    turns = turn_nums[-1]
        
        # Check for invalid move in student bot log (opponent wins)
        with open(random_log, 'r') as f:
            random_content = f.read()
        
        if 'invalid_move' in student_content.lower() or 'invalid move' in student_content.lower():
            winner = 'random'
            reason = 'Student made invalid move'
        elif 'invalid_move' in random_content.lower() or 'invalid move' in random_content.lower():
            winner = 'student'
            reason = 'Opponent made invalid move'
        
        # If we found a winner, return completed
        if winner:
            return {
                'folder_name': folder_name,
                'student_id': student_id,
                'status': 'COMPLETED',
                'error': reason,
                'winner': winner,
                'student_score': player1_score,
                'random_score': player2_score,
                'turns': turns
            }
        
        # Check if game didn't become active
        if 'did not become active' in student_content:
            return {
                'folder_name': folder_name,
                'student_id': student_id,
                'status': 'ERROR',
                'error': 'Game did not become active',
                'winner': '',
                'student_score': '',
                'random_score': '',
                'turns': ''
            }
        
        # Default to timeout
        return {
            'folder_name': folder_name,
            'student_id': student_id,
            'status': 'TIMEOUT',
            'error': 'Game did not complete within timeout',
            'winner': '',
            'student_score': '',
            'random_score': '',
            'turns': ''
        }
            
    except Exception as e:
        return {
            'folder_name': folder_name,
            'student_id': student_id,
            'status': 'ERROR',
            'error': str(e)[:200],
            'winner': '',
            'student_score': '',
            'random_score': '',
            'turns': ''
        }

def main():
    print("="*80)
    print("SEQUENTIAL SUBMISSION EVALUATION")
    print("="*80)
    print(f"Python: {PYTHON_EXE}")
    print(f"Port: {PORT}")
    print(f"Time limits: small={TIME_LIMITS['small']}s, medium={TIME_LIMITS['medium']}s, large={TIME_LIMITS['large']}s")
    print("="*80)
    
    # Read eligible submissions (python type, no forbidden imports, not a duplicate)
    eligible_submissions = []
    with open(SUBMISSIONS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row['type'] == 'python' and 
                row['forbidden_imports'] == 'NONE' and 
                not row['duplicate_of']):
                # Create group info from student IDs
                student_ids = row['student_id'].split(',')
                group_info = f"Group of {len(student_ids)}" if len(student_ids) > 1 else "Individual"
                eligible_submissions.append((row['folder_name'], row['student_id'], group_info))
    
    print(f"\nFound {len(eligible_submissions)} eligible Python submissions")
    print("\nStarting sequential evaluation...\n")
    
    results = []
    group_results = {}  # Track results by group
    start_time = time.time()
    
    for idx, (folder_name, student_id, group_info) in enumerate(eligible_submissions, 1):
        print(f"\n[{idx}/{len(eligible_submissions)}]")
        result = test_submission(folder_name, student_id, group_info)
        results.append(result)
        
        # Track group results
        if group_info not in group_results:
            group_results[group_info] = {'wins': 0, 'losses': 0, 'draws': 0, 'errors': 0, 'total': 0}
        
        group_results[group_info]['total'] += 1
        if result['status'] == 'COMPLETED':
            if result['winner'] == 'student':
                group_results[group_info]['wins'] += 1
            elif result['winner'] == 'random':
                group_results[group_info]['losses'] += 1
            else:
                group_results[group_info]['draws'] += 1
        else:
            group_results[group_info]['errors'] += 1
        
        # Update CSV after each submission
        with open(SUBMISSIONS_CSV, 'r') as f:
            rows = list(csv.DictReader(f))
        
        for row in rows:
            if row['folder_name'] == folder_name:
                row['status'] = result['status']
                row['errors'] = result['error']
                # Store additional info in score_vs_random column
                if result['status'] == 'COMPLETED':
                    score_info = f"Winner: {result['winner']}"
                    if result['student_score'] and result['random_score']:
                        score_info += f" | Scores: {result['student_score']}-{result['random_score']}"
                    row['score_vs_random'] = score_info
                else:
                    row['score_vs_random'] = result['error'][:100]
                break
        
        with open(SUBMISSIONS_CSV, 'w', newline='') as f:
            fieldnames = rows[0].keys()
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        
        print(f"CSV updated")
    
    # Print summary
    total_time = time.time() - start_time
    print("\n" + "="*80)
    print("EVALUATION COMPLETE")
    print("="*80)
    print(f"Total time: {total_time/60:.1f} minutes")
    print(f"\nResults:")
    
    completed = sum(1 for r in results if r['status'] == 'COMPLETED')
    errors = sum(1 for r in results if r['status'] == 'ERROR')
    timeouts = sum(1 for r in results if r['status'] == 'TIMEOUT')
    
    print(f"  Completed: {completed}")
    print(f"  Errors: {errors}")
    print(f"  Timeouts: {timeouts}")
    print(f"  Total: {len(results)}")
    
    # Winner breakdown
    if completed > 0:
        student_wins = sum(1 for r in results if r['winner'] == 'student')
        random_wins = sum(1 for r in results if r['winner'] == 'random')
        draws = sum(1 for r in results if r['winner'] in ['tie', 'draw_repetition'])
        
        print(f"\nWinner breakdown (completed games):")
        print(f"  Student wins: {student_wins}")
        print(f"  Reference student wins: {random_wins}")
        print(f"  Draws: {draws}")
    
    # Group statistics
    print(f"\n{'='*80}")
    print("GROUP STATISTICS")
    print(f"{'='*80}")
    for group_type, stats in sorted(group_results.items()):
        print(f"\n{group_type}:")
        print(f"  Total submissions: {stats['total']}")
        if stats['wins'] + stats['losses'] + stats['draws'] > 0:
            print(f"  Wins: {stats['wins']}")
            print(f"  Losses: {stats['losses']}")
            print(f"  Draws: {stats['draws']}")
            win_rate = (stats['wins'] / (stats['wins'] + stats['losses'] + stats['draws']) * 100) if (stats['wins'] + stats['losses'] + stats['draws']) > 0 else 0
            print(f"  Win rate: {win_rate:.1f}%")
        if stats['errors'] > 0:
            print(f"  Errors: {stats['errors']}")
    
    print("\nResults saved to:", SUBMISSIONS_CSV)
    print("="*80)

if __name__ == "__main__":
    main()
