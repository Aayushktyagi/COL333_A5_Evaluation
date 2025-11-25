#!/bin/bash
# Script to run Tournament T1 Elimination Stage with nohup and conda environment

# Activate conda environment and run tournament
source ~/anaconda3/etc/profile.d/conda.sh
conda activate Aayush_env

# Run tournament in background with nohup
nohup python /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/run_elimination_tournament.py > /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination_output.log 2>&1 &

# Save PID
echo $! > /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination.pid

echo "Tournament T1 Elimination Stage started with PID: $(cat /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination.pid)"
echo "Output log: /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination_output.log"
echo "To monitor: tail -f /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination_output.log"
echo "To stop: kill $(cat /home/aayush/Aayush/Learning/Courses/COL333_TA/A5/COL333_A5_Evaluation/tournament_t1_elimination.pid)"
