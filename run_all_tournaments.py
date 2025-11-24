#!/usr/bin/env python3
"""
Parallel Tournament Runner for All Groups
Runs tournaments for all 32 groups in parallel using multiprocessing
Each group gets a unique port to avoid conflicts
"""

import os
import sys
import subprocess
import time
from pathlib import Path
from multiprocessing import Pool, cpu_count
import signal

# Configuration
GROUP_STAGE_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/Tournament/Group_stage")
OUTPUT_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_results")
EVALUATION_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation")
TOURNAMENT_SCRIPT = EVALUATION_DIR / "run_tournament.py"

# Base port - each group will use BASE_PORT + group_number
BASE_PORT = 9500
NUM_WORKERS = 32  # Use all 32 CPU cores

def modify_tournament_script_for_port(group_num):
    """
    Create a modified version of run_tournament.py with a specific port for this group.
    This avoids port conflicts when running multiple tournaments in parallel.
    """
    port = BASE_PORT + group_num
    return port

def run_single_tournament(args):
    """Run tournament for a single group"""
    group_num, group_dir = args
    group_name = group_dir.name
    port = BASE_PORT + group_num
    
    print(f"🚀 Starting tournament for {group_name} on port {port}")
    
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
        
        if result.returncode == 0:
            print(f"✅ {group_name} completed successfully on port {port}")
            return {
                'group': group_name,
                'status': 'success',
                'port': port,
                'output': result.stdout[-500:] if result.stdout else ''
            }
        else:
            print(f"❌ {group_name} failed on port {port}")
            return {
                'group': group_name,
                'status': 'failed',
                'port': port,
                'error': result.stderr[-500:] if result.stderr else 'Unknown error'
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
    print("🏆 PARALLEL TOURNAMENT RUNNER FOR ALL GROUPS")
    print("=" * 100)
    print()
    
    # Find all group directories
    group_dirs = sorted([d for d in GROUP_STAGE_DIR.iterdir() if d.is_dir() and d.name.startswith('Group')])
    
    if not group_dirs:
        print(f"❌ No groups found in {GROUP_STAGE_DIR}")
        sys.exit(1)
    
    print(f"📁 Found {len(group_dirs)} groups")
    print(f"💻 Using {NUM_WORKERS} CPU cores")
    print(f"🔌 Port range: {BASE_PORT} to {BASE_PORT + len(group_dirs) - 1}")
    print()
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Prepare arguments for each group
    # Extract group number from group name (e.g., "Group1" -> 1)
    def get_group_num(group_dir):
        group_name = group_dir.name
        return int(group_name.replace('Group', ''))
    
    group_args = [(get_group_num(d), d) for d in group_dirs]
    
    print(f"🚀 Starting {len(group_args)} tournaments in parallel...")
    print(f"⏰ Maximum time per tournament: 2 hours")
    print()
    
    start_time = time.time()
    
    # Run tournaments in parallel
    with Pool(processes=NUM_WORKERS) as pool:
        results = pool.map(run_single_tournament, group_args)
    
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # Summary
    print()
    print("=" * 100)
    print("📊 TOURNAMENT RESULTS SUMMARY")
    print("=" * 100)
    print()
    
    successful = [r for r in results if r['status'] == 'success']
    failed = [r for r in results if r['status'] == 'failed']
    timeout = [r for r in results if r['status'] == 'timeout']
    errors = [r for r in results if r['status'] == 'error']
    
    print(f"✅ Successful: {len(successful)}")
    print(f"❌ Failed: {len(failed)}")
    print(f"⏰ Timeout: {len(timeout)}")
    print(f"💥 Errors: {len(errors)}")
    print()
    
    if successful:
        print("✅ SUCCESSFUL GROUPS:")
        for r in successful:
            print(f"   - {r['group']} (port {r['port']})")
        print()
    
    if failed:
        print("❌ FAILED GROUPS:")
        for r in failed:
            print(f"   - {r['group']} (port {r['port']})")
            if 'error' in r:
                print(f"     Error: {r['error'][:200]}")
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
    print(f"📁 Results saved to: {OUTPUT_DIR}")
    print()
    print("=" * 100)
    
    # Write summary to file
    summary_file = OUTPUT_DIR / "tournament_summary.txt"
    with open(summary_file, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("PARALLEL TOURNAMENT SUMMARY\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"Total Groups: {len(results)}\n")
        f.write(f"Successful: {len(successful)}\n")
        f.write(f"Failed: {len(failed)}\n")
        f.write(f"Timeout: {len(timeout)}\n")
        f.write(f"Errors: {len(errors)}\n")
        f.write(f"Total Time: {elapsed_time/60:.2f} minutes\n\n")
        
        for status_name, status_results in [
            ("SUCCESSFUL", successful),
            ("FAILED", failed),
            ("TIMEOUT", timeout),
            ("ERRORS", errors)
        ]:
            if status_results:
                f.write(f"\n{status_name} GROUPS:\n")
                f.write("-" * 100 + "\n")
                for r in status_results:
                    f.write(f"Group: {r['group']}, Port: {r['port']}\n")
                    if 'error' in r:
                        f.write(f"  Error: {r['error']}\n")
                    if 'output' in r and r['output']:
                        f.write(f"  Last output: {r['output'][:200]}\n")
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
