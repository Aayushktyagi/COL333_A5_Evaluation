#!/usr/bin/env python3
"""
Resume incomplete tournaments for groups with 4 players
Only runs groups that have incomplete matches
"""

import os
import sys
import subprocess
import time
import shutil
from pathlib import Path
from multiprocessing import Pool
import signal

# Configuration
GROUP_STAGE_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/Tournament/Group_stage")
OUTPUT_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_results")
EVALUATION_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation")
TOURNAMENT_SCRIPT = EVALUATION_DIR / "run_tournament.py"

# Base port - each group will use BASE_PORT + group_number
BASE_PORT = 9500
NUM_WORKERS = 25  # Number of groups to re-run

# List of groups to re-run with improved timeout logic
# INCOMPLETE_GROUPS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29,30, 31, 32]
INCOMPLETE_GROUPS = [31, 32]

def check_group_completion(group_num):
    """Check if a group's tournament is complete"""
    csv_file = OUTPUT_DIR / f"Group{group_num}" / f"Group{group_num}_results.csv"
    if not csv_file.exists():
        return False, 0, 0
    
    # Count matches
    with open(csv_file, 'r') as f:
        actual_matches = len(f.readlines()) - 1  # Exclude header
    
    # Get player count
    group_dir = GROUP_STAGE_DIR / f"Group{group_num}"
    player_count = len([d for d in group_dir.iterdir() if d.is_dir() and d.name.startswith('submission_')])
    expected_matches = player_count * (player_count - 1) // 2
    
    is_complete = actual_matches == expected_matches
    return is_complete, actual_matches, expected_matches

def run_single_tournament(args):
    """Run tournament for a single group"""
    group_num, group_dir = args
    group_name = group_dir.name
    port = BASE_PORT + group_num
    
    # FORCE RE-RUN: Skip completion check and always re-run
    print(f"🔄 FORCE re-running tournament for {group_name} on port {port}")
    
    try:
        # Create a temporary Python script that sets the PORT before importing
        temp_script = EVALUATION_DIR / f"run_tournament_group{group_num}.py"
        
        # Read the original tournament script
        with open(TOURNAMENT_SCRIPT, 'r') as f:
            original_content = f.read()
        
        # Replace the PORT value
        modified_content = original_content.replace(
            "PORT = 9500",
            f"PORT = {port}"
        )
        
        # Write temporary script
        with open(temp_script, 'w') as f:
            f.write(modified_content)
        
        # Backup existing results and delete to restart fresh
        group_results_dir = OUTPUT_DIR / f"Group{group_num}"
        if group_results_dir.exists():
            backup_dir = OUTPUT_DIR / f"Group{group_num}_backup_{int(time.time())}"
            shutil.move(str(group_results_dir), str(backup_dir))
            print(f"   📦 Backed up old results to {backup_dir.name}")
        
        # Run tournament with conda environment
        result = subprocess.run(
            f'bash -c "source ~/anaconda3/etc/profile.d/conda.sh && conda activate Aayush_env && python {temp_script} {group_dir} {OUTPUT_DIR}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout per group
        )
        
        # Clean up temporary script
        if temp_script.exists():
            temp_script.unlink()
        
        # Verify completion
        is_complete, actual, expected = check_group_completion(group_num)
        
        if result.returncode == 0 and is_complete:
            print(f"✅ {group_name} completed successfully on port {port} ({actual}/{expected} matches)")
            return {
                'group': group_name,
                'status': 'success',
                'port': port,
                'matches': f'{actual}/{expected}'
            }
        else:
            print(f"⚠️  {group_name} finished but incomplete on port {port} ({actual}/{expected} matches)")
            return {
                'group': group_name,
                'status': 'incomplete',
                'port': port,
                'matches': f'{actual}/{expected}',
                'error': result.stderr[-500:] if result.stderr else 'Unknown issue'
            }
    
    except subprocess.TimeoutExpired:
        print(f"⏰ {group_name} timed out on port {port}")
        # Clean up processes for this port
        try:
            subprocess.run(['pkill', '-9', '-f', f'web_server.py.*{port}'], timeout=5)
            subprocess.run(['pkill', '-9', '-f', f'test_bot.*{port}'], timeout=5)
        except:
            pass
        
        # Clean up temporary script
        temp_script = EVALUATION_DIR / f"run_tournament_group{group_num}.py"
        if temp_script.exists():
            temp_script.unlink()
        
        return {
            'group': group_name,
            'status': 'timeout',
            'port': port,
            'error': 'Tournament exceeded 2 hour time limit'
        }
    
    except Exception as e:
        print(f"💥 {group_name} crashed on port {port}: {str(e)}")
        
        # Clean up temporary script
        temp_script = EVALUATION_DIR / f"run_tournament_group{group_num}.py"
        if temp_script.exists():
            temp_script.unlink()
        
        return {
            'group': group_name,
            'status': 'error',
            'port': port,
            'error': str(e)
        }

def main():
    print("=" * 100)
    print("🔄 RESUMING INCOMPLETE TOURNAMENTS")
    print("=" * 100)
    print()
    
    # Get incomplete group directories
    group_dirs = []
    for group_num in INCOMPLETE_GROUPS:
        group_dir = GROUP_STAGE_DIR / f"Group{group_num}"
        if group_dir.exists():
            group_dirs.append((group_num, group_dir))
    
    print(f"📁 Found {len(group_dirs)} incomplete groups to resume")
    print(f"💻 Using {NUM_WORKERS} CPU cores")
    print(f"🔌 Port range: {BASE_PORT} to {BASE_PORT + 32}")
    print()
    
    print(f"🚀 Starting {len(group_dirs)} tournaments in parallel...")
    print(f"⏰ Maximum time per tournament: 2 hours")
    print()
    
    start_time = time.time()
    
    # Run tournaments in parallel
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(run_single_tournament, group_dirs)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Summary
    print()
    print("=" * 100)
    print("📊 RESUME TOURNAMENT RESULTS")
    print("=" * 100)
    print()
    
    successful = [r for r in results if r['status'] == 'success']
    already_complete = [r for r in results if r['status'] == 'already_complete']
    incomplete = [r for r in results if r['status'] == 'incomplete']
    timeout = [r for r in results if r['status'] == 'timeout']
    errors = [r for r in results if r['status'] == 'error']
    
    print(f"✅ Newly Completed: {len(successful)}")
    print(f"✅ Already Complete: {len(already_complete)}")
    print(f"⚠️  Still Incomplete: {len(incomplete)}")
    print(f"⏰ Timeout: {len(timeout)}")
    print(f"💥 Errors: {len(errors)}")
    print()
    
    if successful:
        print("✅ NEWLY COMPLETED GROUPS:")
        for r in successful:
            print(f"   - {r['group']} (port {r['port']}, {r.get('matches', 'N/A')} matches)")
        print()
    
    if incomplete:
        print("⚠️  STILL INCOMPLETE GROUPS:")
        for r in incomplete:
            print(f"   - {r['group']} (port {r['port']}, {r.get('matches', 'N/A')} matches)")
        print()
    
    if timeout:
        print("⏰ TIMEOUT GROUPS:")
        for r in timeout:
            print(f"   - {r['group']} (port {r['port']})")
        print()
    
    if errors:
        print("💥 ERROR GROUPS:")
        for r in errors:
            print(f"   - {r['group']} (port {r['port']})")
            if 'error' in r:
                print(f"     Error: {r['error'][:200]}")
        print()
    
    print(f"⏱️  Total time: {elapsed_time/60:.2f} minutes")
    print()
    print("=" * 100)
    
    # Write summary to file
    summary_file = OUTPUT_DIR / "resume_tournament_summary.txt"
    with open(summary_file, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("RESUME TOURNAMENT SUMMARY\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"Total Groups Resumed: {len(results)}\n")
        f.write(f"Newly Completed: {len(successful)}\n")
        f.write(f"Already Complete: {len(already_complete)}\n")
        f.write(f"Still Incomplete: {len(incomplete)}\n")
        f.write(f"Timeout: {len(timeout)}\n")
        f.write(f"Errors: {len(errors)}\n")
        f.write(f"Total Time: {elapsed_time/60:.2f} minutes\n\n")
        
        for status_name, status_results in [
            ("NEWLY COMPLETED", successful),
            ("ALREADY COMPLETE", already_complete),
            ("STILL INCOMPLETE", incomplete),
            ("TIMEOUT", timeout),
            ("ERRORS", errors)
        ]:
            if status_results:
                f.write(f"\n{status_name} GROUPS:\n")
                f.write("-" * 100 + "\n")
                for r in status_results:
                    f.write(f"Group: {r['group']}, Port: {r['port']}")
                    if 'matches' in r:
                        f.write(f", Matches: {r['matches']}")
                    f.write("\n")
                    if 'error' in r:
                        f.write(f"  Error: {r['error']}\n")
                    f.write("\n")
    
    print(f"📄 Summary written to: {summary_file}")
    print()

if __name__ == '__main__':
    # Handle Ctrl+C gracefully
    def signal_handler(sig, frame):
        print("\n\n🛑 Interrupted by user. Cleaning up...")
        # Kill all tournament-related processes
        subprocess.run(['pkill', '-9', '-f', 'web_server.py'], capture_output=True)
        subprocess.run(['pkill', '-9', '-f', 'test_bot_student.py'], capture_output=True)
        subprocess.run(['pkill', '-9', '-f', 'run_tournament'], capture_output=True)
        sys.exit(1)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    main()
