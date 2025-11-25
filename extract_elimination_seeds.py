#!/usr/bin/env python3
"""
Extract top players from each group for elimination tournament (Tournament T1)
Ranks players based on total wins and scores across all matches
For T1: Each match has 2 games with role swaps (game1 and game2)
"""

import csv
import re
from pathlib import Path
import pandas as pd

# Paths
TOURNAMENT_RESULTS_DIR = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/Tournament_T1_Group_Stage_Results")
OUTPUT_FILE = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/elimination_seeds_T1.csv")
SUMMARY_FILE = Path("/home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/elimination_seeds_T1_summary.txt")

def extract_scores_from_log(log_file):
    """Extract final scores from server log file"""
    if not log_file.exists():
        return None, None
    
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            # Look for final scores in log
            # Pattern: "Final Scores - Circle: XX.XX, Square: YY.YY"
            match = re.search(r'Final Scores - Circle:\s*([\d.]+),\s*Square:\s*([\d.]+)', content)
            if match:
                return float(match.group(1)), float(match.group(2))
    except Exception as e:
        print(f"      Warning: Could not parse log {log_file.name}: {e}")
    return None, None

def extract_group_winner(group_dir):
    """Extract the winner (top player) from a group (T1 format)"""
    csv_file = group_dir / f"{group_dir.name}_results.csv"
    matches_dir = group_dir / "matches"
    
    if not csv_file.exists():
        print(f"⚠️  No results file found for {group_dir.name}")
        return None
    
    # Read results
    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        results = list(reader)
    
    if not results:
        print(f"⚠️  Empty results for {group_dir.name}")
        return None
    
    # Calculate stats for each player
    player_stats = {}
    
    for result in results:
        player1 = result['player1']
        player2 = result['player2']
        match_num = result['match_num']
        player1_id = result['player1_id']
        player2_id = result['player2_id']
        
        # Initialize if not seen
        if player1 not in player_stats:
            player_stats[player1] = {'wins': 0, 'losses': 0, 'draws': 0, 'total_score': 0.0, 'games_played': 0, 'player_id': player1.replace('submission_', '')}
        if player2 not in player_stats:
            player_stats[player2] = {'wins': 0, 'losses': 0, 'draws': 0, 'total_score': 0.0, 'games_played': 0, 'player_id': player2.replace('submission_', '')}
        
        # Process T1 format: small board only, 2 games per match
        board_size = 'small'
        
        # Try to get scores from CSV first, then fall back to logs
        p1_total = result.get(f'{board_size}_player1_total_score', '')
        p2_total = result.get(f'{board_size}_player2_total_score', '')
        
        # If CSV has total scores, use them
        if p1_total and p2_total:
            try:
                player_stats[player1]['total_score'] += float(p1_total)
                player_stats[player2]['total_score'] += float(p2_total)
            except:
                pass
        else:
            # Fall back to extracting from logs
            match_dir = matches_dir / f"match_{match_num}_{player1_id}_vs_{player2_id}"
            if match_dir.exists():
                # Game 1: player1=circle, player2=square
                game1_log = match_dir / f"{board_size}_game1_server.log"
                circle_score_g1, square_score_g1 = extract_scores_from_log(game1_log)
                
                # Game 2: player2=circle, player1=square
                game2_log = match_dir / f"{board_size}_game2_server.log"
                circle_score_g2, square_score_g2 = extract_scores_from_log(game2_log)
                
                # Add scores
                if circle_score_g1 is not None:
                    player_stats[player1]['total_score'] += circle_score_g1
                if square_score_g1 is not None:
                    player_stats[player2]['total_score'] += square_score_g1
                if circle_score_g2 is not None:
                    player_stats[player2]['total_score'] += circle_score_g2
                if square_score_g2 is not None:
                    player_stats[player1]['total_score'] += square_score_g2
        
        # Count wins based on overall_winner
        overall_winner = result.get(f'{board_size}_overall_winner', '')
        if overall_winner == 'player1':
            player_stats[player1]['wins'] += 1
            player_stats[player2]['losses'] += 1
        elif overall_winner == 'player2':
            player_stats[player2]['wins'] += 1
            player_stats[player1]['losses'] += 1
        elif overall_winner == 'draw':
            player_stats[player1]['draws'] += 1
            player_stats[player2]['draws'] += 1
        
        # Each match = 1 game played (2 rounds but counts as 1 match)
        player_stats[player1]['games_played'] += 1
        player_stats[player2]['games_played'] += 1
    
    # Calculate win rate and score per game
    for player, stats in player_stats.items():
        if stats['games_played'] > 0:
            stats['win_rate'] = stats['wins'] / stats['games_played']
            stats['avg_score'] = stats['total_score'] / stats['games_played']
        else:
            stats['win_rate'] = 0
            stats['avg_score'] = 0
    
    # Sort by wins, then by total score, then by win rate
    sorted_players = sorted(
        player_stats.items(),
        key=lambda x: (x[1]['wins'], x[1]['total_score'], x[1]['win_rate']),
        reverse=True
    )
    
    if sorted_players:
        winner_name, winner_stats = sorted_players[0]
        return {
            'group': group_dir.name,
            'player': winner_name,
            'player_id': winner_stats['player_id'],
            'wins': winner_stats['wins'],
            'losses': winner_stats['losses'],
            'draws': winner_stats['draws'],
            'total_score': winner_stats['total_score'],
            'games_played': winner_stats['games_played'],
            'win_rate': winner_stats['win_rate'],
            'avg_score': winner_stats['avg_score']
        }
    
    return None

def main():
    print("=" * 100)
    print("🏆 EXTRACTING TOP PLAYERS FROM EACH GROUP (TOURNAMENT T1)")
    print("=" * 100)
    print()
    
    # Find all group result directories
    group_dirs = sorted([d for d in TOURNAMENT_RESULTS_DIR.iterdir() 
                        if d.is_dir() and d.name.startswith('Group')],
                        key=lambda x: int(x.name.replace('Group', '')))
    
    print(f"📁 Found {len(group_dirs)} group directories")
    print()
    
    # Extract winners
    winners = []
    for group_dir in group_dirs:
        print(f"Processing {group_dir.name}...")
        winner = extract_group_winner(group_dir)
        if winner:
            winners.append(winner)
            print(f"   ✅ Winner: {winner['player']} - {winner['wins']}W/{winner['losses']}L/{winner['draws']}D, Score: {winner['total_score']:.2f}")
        else:
            print(f"   ❌ No winner found")
        print()
    
    if len(winners) != 32:
        print(f"⚠️  Warning: Expected 32 winners, got {len(winners)}")
    
    # Sort winners by performance (wins, then total score, then win rate)
    winners.sort(key=lambda x: (x['wins'], x['total_score'], x['win_rate']), reverse=True)
    
    # Assign seeds
    for i, winner in enumerate(winners, 1):
        winner['seed'] = i
    
    print("=" * 100)
    print("📊 SEEDING RESULTS (TOP TO BOTTOM)")
    print("=" * 100)
    print()
    print(f"{'Seed':<6} {'Group':<10} {'Player':<30} {'W/L/D':<12} {'Total Score':<12} {'Win Rate':<10}")
    print("-" * 100)
    
    for winner in winners:
        wld = f"{winner['wins']}/{winner['losses']}/{winner['draws']}"
        print(f"{winner['seed']:<6} {winner['group']:<10} {winner['player']:<30} {wld:<12} {winner['total_score']:<12.2f} {winner['win_rate']:<10.2%}")
    
    # Save to CSV
    with open(OUTPUT_FILE, 'w', newline='') as f:
        fieldnames = ['seed', 'group', 'player', 'player_id', 'wins', 'losses', 'draws', 
                     'total_score', 'games_played', 'win_rate', 'avg_score']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(winners)
    
    # Create summary file
    with open(SUMMARY_FILE, 'w') as f:
        f.write("=" * 100 + "\n")
        f.write("TOURNAMENT T1 - ELIMINATION STAGE SEEDS\n")
        f.write("=" * 100 + "\n\n")
        f.write(f"Total Qualified Players: {len(winners)}\n")
        f.write(f"Date: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("SEEDING (TOP TO BOTTOM):\n")
        f.write("-" * 100 + "\n")
        f.write(f"{'Seed':<6} {'Group':<10} {'Player':<30} {'ID':<15} {'W/L/D':<12} {'Score':<10} {'Win Rate':<10}\n")
        f.write("-" * 100 + "\n")
        
        for winner in winners:
            wld = f"{winner['wins']}/{winner['losses']}/{winner['draws']}"
            f.write(f"{winner['seed']:<6} {winner['group']:<10} {winner['player']:<30} "
                   f"{winner['player_id']:<15} {wld:<12} {winner['total_score']:<10.2f} {winner['win_rate']:<10.2%}\n")
        
        f.write("\n" + "=" * 100 + "\n")
        f.write("\nELIMINATION BRACKET PAIRINGS:\n")
        f.write("-" * 100 + "\n")
        f.write("Round of 32:\n")
        for i in range(16):
            high = winners[i]
            low = winners[31 - i]
            f.write(f"  Match {i+1}: #{high['seed']} {high['player']} vs #{low['seed']} {low['player']}\n")
    
    print()
    print(f"✅ Seeds saved to: {OUTPUT_FILE}")
    print(f"✅ Summary saved to: {SUMMARY_FILE}")
    print()

if __name__ == '__main__':
    main()
