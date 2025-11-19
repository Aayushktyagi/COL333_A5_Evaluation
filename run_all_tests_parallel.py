#!/usr/bin/env python3
"""
Run all eligible submissions in parallel against random agent.
Reports successes and failures at the end.
"""

import os
import csv
import time
import subprocess
import signal
from multiprocessing import Pool
from pathlib import Path

# Configuration
SUBMISSIONS_CSV = "/Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/evaluation/results/submissions_list.csv"
EVALUATION_DIR = "/Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/evaluation"
REFERENCE_DIR = "/Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/A5_final/COL333_2025_A5/client_server"
SUBMISSIONS_BASE = "/Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/assignment_7153640_export"

# Parallel configuration
NUM_PARALLEL_SERVERS = 8  # Number of parallel servers to run
BASE_PORT = 9500  # Starting port number
TIMEOUT_PER_GAME = 300  # 5 minutes per game

# Board sizes to test
BOARD_SIZES = ['small', 'medium', 'large']

def test_submission(args):
    """Test a single submission against random agent."""
    submission, port = args
    
    folder_name = submission['folder_name']
    student_id = submission['student_id']
    sub_type = submission['type']
    
    print(f"[Port {port}] Testing {folder_name}")
    
    try:
        # Create test directory for this submission
        test_dir = os.path.join(EVALUATION_DIR, 'temp_tests', f"{folder_name}_p{port}")
        os.makedirs(test_dir, exist_ok=True)
        
        # Copy reference files
        for file in ['gameEngine.py', 'agent.py', 'web_server.py', 'bot_client.py']:
            src = os.path.join(REFERENCE_DIR, file)
            dst = os.path.join(test_dir, file)
            subprocess.run(['cp', src, dst], check=True, capture_output=True)
        
        # Copy templates directory
        templates_src = os.path.join(REFERENCE_DIR, 'templates')
        templates_dst = os.path.join(test_dir, 'templates')
        if os.path.exists(templates_dst):
            subprocess.run(['rm', '-rf', templates_dst], check=True, capture_output=True)
        subprocess.run(['cp', '-r', templates_src, templates_dst], check=True, capture_output=True)
        
        # Copy student agent
        submission_dir = os.path.join(SUBMISSIONS_BASE, folder_name)
        
        if sub_type == 'python':
            student_agent_src = os.path.join(submission_dir, 'student_agent.py')
            if not os.path.exists(student_agent_src):
                return {
                    'folder_name': folder_name,
                    'student_id': student_id,
                    'status': 'ERROR',
                    'error': 'student_agent.py not found',
                    'winner': '',
                    'student_score': '',
                    'random_score': '',
                    'turns': ''
                }
            subprocess.run(['cp', student_agent_src, test_dir], check=True, capture_output=True)
        else:
            # Skip C++ submissions for now
            return {
                'folder_name': folder_name,
                'student_id': student_id,
                'status': 'SKIPPED',
                'error': 'C++ submission (not implemented)',
                'winner': '',
                'student_score': '',
                'random_score': '',
                'turns': ''
            }
        
        # Choose board size
        board_size = BOARD_SIZES[hash(folder_name) % len(BOARD_SIZES)]
        
        # Start web server
        server_log = os.path.join(test_dir, 'server.log')
        with open(server_log, 'w') as log_file:
            server_proc = subprocess.Popen(
                ['python3', 'web_server.py', str(port), board_size],
                cwd=test_dir,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        # Wait for server to start
        time.sleep(5)
        
        # Check if server is running
        if server_proc.poll() is not None:
            with open(server_log, 'r') as f:
                error_msg = f.read()[-500:]
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
        
        # Start student bot
        student_log = os.path.join(test_dir, 'student_bot.log')
        with open(student_log, 'w') as log_file:
            student_proc = subprocess.Popen(
                ['python3', os.path.join(EVALUATION_DIR, 'test_bot_student.py'), 
                 test_dir, str(port), board_size],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        time.sleep(2)
        
        # Start random bot
        random_log = os.path.join(test_dir, 'random_bot.log')
        with open(random_log, 'w') as log_file:
            random_proc = subprocess.Popen(
                ['python3', os.path.join(EVALUATION_DIR, 'test_bot_random.py'), 
                 test_dir, str(port), board_size],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                preexec_fn=os.setsid
            )
        
        # Wait for game to complete or timeout
        start_time = time.time()
        game_completed = False
        
        while time.time() - start_time < TIMEOUT_PER_GAME:
            if server_proc.poll() is not None:
                game_completed = True
                break
            time.sleep(2)
        
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
        
        print(f"[Port {port}] {folder_name}: {result['status']}")
        
        return result
        
    except Exception as e:
        print(f"[Port {port}] ERROR {folder_name}: {str(e)[:100]}")
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
        
        # Look for game over/winner patterns
        if 'Game Over' in log_content or 'Winner' in log_content or 'wins' in log_content:
            winner = ''
            player1_score = ''
            player2_score = ''
            turns = ''
            
            lines = log_content.split('\n')
            for line in lines:
                # Look for winner
                if 'player1' in line.lower() and ('win' in line.lower() or 'winner' in line.lower()):
                    winner = 'student'
                elif 'player2' in line.lower() and ('win' in line.lower() or 'winner' in line.lower()):
                    winner = 'random'
                elif 'circle' in line.lower() and ('win' in line.lower() or 'winner' in line.lower()):
                    winner = 'student'
                elif 'square' in line.lower() and ('win' in line.lower() or 'winner' in line.lower()):
                    winner = 'random'
                elif 'tie' in line.lower() or 'draw' in line.lower():
                    winner = 'tie'
                
                # Look for scores
                if 'score' in line.lower():
                    import re
                    scores = re.findall(r'\d+', line)
                    if len(scores) >= 2:
                        player1_score = scores[0]
                        player2_score = scores[1]
                
                # Look for turns
                if 'turn' in line.lower():
                    import re
                    turn_nums = re.findall(r'\d+', line)
                    if turn_nums:
                        turns = turn_nums[-1]
            
            if winner:
                return {
                    'folder_name': folder_name,
                    'student_id': student_id,
                    'status': 'COMPLETED',
                    'error': '',
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
            'error': f'Failed to parse results: {str(e)[:100]}',
            'winner': '',
            'student_score': '',
            'random_score': '',
            'turns': ''
        }

def main():
    """Main function to run parallel tests."""
    print("="*80)
    print("PARALLEL SUBMISSION TESTING - ALL PYTHON SUBMISSIONS")
    print("="*80)
    print(f"Parallel servers: {NUM_PARALLEL_SERVERS}")
    print(f"Port range: {BASE_PORT} - {BASE_PORT + NUM_PARALLEL_SERVERS - 1}")
    print(f"Timeout per game: {TIMEOUT_PER_GAME}s")
    print()
    
    # Load submissions
    submissions = []
    with open(SUBMISSIONS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Skip duplicates
            if row['duplicate_of']:
                continue
            # Only test Python submissions
            if row['type'] != 'python':
                continue
            # Skip submissions with forbidden imports
            if row['forbidden_imports'] != 'NONE':
                continue
            submissions.append(row)
    
    print(f"Found {len(submissions)} eligible Python submissions to test")
    print()
    
    # Create temp_tests directory
    temp_tests_dir = os.path.join(EVALUATION_DIR, 'temp_tests')
    os.makedirs(temp_tests_dir, exist_ok=True)
    
    # Assign submissions to ports in round-robin fashion
    test_args = []
    for i, submission in enumerate(submissions):
        port = BASE_PORT + (i % NUM_PARALLEL_SERVERS)
        test_args.append((submission, port))
    
    # Run tests in parallel
    print(f"Starting parallel testing at {time.strftime('%H:%M:%S')}...")
    print()
    start_time = time.time()
    
    with Pool(processes=NUM_PARALLEL_SERVERS) as pool:
        results = pool.map(test_submission, test_args)
    
    elapsed_time = time.time() - start_time
    
    # Categorize results
    completed = [r for r in results if r['status'] == 'COMPLETED']
    errors = [r for r in results if r['status'] == 'ERROR']
    timeouts = [r for r in results if r['status'] == 'TIMEOUT']
    skipped = [r for r in results if r['status'] == 'SKIPPED']
    
    # Update CSV with results
    print()
    print("="*80)
    print("Updating submissions_list.csv...")
    
    results_dict = {r['folder_name']: r for r in results}
    
    updated_submissions = []
    with open(SUBMISSIONS_CSV, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder_name = row['folder_name']
            if folder_name in results_dict:
                result = results_dict[folder_name]
                row['status'] = result['status']
                row['errors'] = result['error']
                
                # Format score_vs_random
                if result['winner']:
                    score_info = f"{result['winner']}|S:{result['student_score']}|R:{result['random_score']}|T:{result['turns']}"
                    row['score_vs_random'] = score_info
            
            updated_submissions.append(row)
    
    with open(SUBMISSIONS_CSV, 'w', newline='') as f:
        fieldnames = updated_submissions[0].keys()
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_submissions)
    
    print("✅ CSV updated")
    print()
    
    # Print detailed summary
    print("="*80)
    print("FINAL SUMMARY")
    print("="*80)
    print(f"Total submissions tested: {len(results)}")
    print(f"Time elapsed: {elapsed_time/60:.1f} minutes ({elapsed_time:.0f} seconds)")
    print(f"Average time per submission: {elapsed_time/len(results):.1f} seconds")
    print()
    
    print(f"✅ COMPLETED: {len(completed)}")
    print(f"❌ ERRORS: {len(errors)}")
    print(f"⏱️  TIMEOUTS: {len(timeouts)}")
    print(f"⏭️  SKIPPED: {len(skipped)}")
    print()
    
    # Winner statistics
    if completed:
        student_wins = sum(1 for r in completed if r['winner'] == 'student')
        random_wins = sum(1 for r in completed if r['winner'] == 'random')
        ties = sum(1 for r in completed if r['winner'] == 'tie')
        
        print("Game Results (Completed Games):")
        print(f"  Student wins: {student_wins} ({100*student_wins/len(completed):.1f}%)")
        print(f"  Random wins: {random_wins} ({100*random_wins/len(completed):.1f}%)")
        print(f"  Ties: {ties} ({100*ties/len(completed):.1f}%)")
        print()
    
    # List completed submissions
    if completed:
        print("="*80)
        print(f"COMPLETED SUBMISSIONS ({len(completed)}):")
        print("="*80)
        for r in completed:
            winner_emoji = "🏆" if r['winner'] == 'student' else "❌" if r['winner'] == 'random' else "🤝"
            print(f"{winner_emoji} {r['folder_name']}")
            print(f"   ID: {r['student_id'][:50]}")
            print(f"   Result: {r['winner']} | Scores: {r['student_score']} vs {r['random_score']} | Turns: {r['turns']}")
        print()
    
    # List failed submissions
    if errors:
        print("="*80)
        print(f"FAILED SUBMISSIONS ({len(errors)}):")
        print("="*80)
        for r in errors:
            print(f"❌ {r['folder_name']}")
            print(f"   ID: {r['student_id'][:50]}")
            print(f"   Error: {r['error'][:100]}")
        print()
    
    # List timeout submissions
    if timeouts:
        print("="*80)
        print(f"TIMEOUT SUBMISSIONS ({len(timeouts)}):")
        print("="*80)
        for r in timeouts:
            print(f"⏱️  {r['folder_name']}")
            print(f"   ID: {r['student_id'][:50]}")
        print()
    
    print("="*80)
    print(f"Testing completed at {time.strftime('%H:%M:%S')}")
    print("="*80)

if __name__ == "__main__":
    main()
