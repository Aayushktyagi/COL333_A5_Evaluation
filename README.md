# Assignment 5 Evaluation System

## Overview

This evaluation system tests all student submissions against a random agent using the web server architecture. It ensures single-threaded execution with GPU support and generates a comprehensive CSV report.

## Directory Structure

```
evaluation/
├── parse_submissions.py      # Step 1: Scan and parse all submissions
├── test_single_submission.py # Test individual submissions
├── run_tournament.py         # Step 2: Run full tournament
├── submissions/              # Copied submissions for testing
├── results/                  # CSV results
│   ├── submissions_list.csv  # Initial list with student IDs
│   └── tournament_results.csv # Final results with scores
└── logs/                     # Individual game logs
```

## Setup

### Prerequisites

```bash
# Install required packages
pip install flask flask-socketio requests

# Ensure you have the reference implementation
# Path: /Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/A5_final/COL333_2025_A5/client_server
```

### Submissions Location

Submissions are in: `/Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/assignment_7153640_export`

## Usage

### Step 1: Parse Submissions

Extract student IDs and check for forbidden imports:

```bash
cd /Users/aayushtyagi/Aayush/PhD/Learning/COL333_TA_25A/A5/evaluation
python3 parse_submissions.py
```

This creates `results/submissions_list.csv` with:
- **folder_name**: Submission folder name
- **student_id**: Student ID(s) from report.txt first line
- **type**: python/cpp/mixed
- **has_report**: Whether report.txt exists
- **has_cmake**: Whether CMakeLists.txt exists (for C++)
- **forbidden_imports**: List of forbidden libraries detected
- **status**: pending/completed/failed/skipped
- **compilation_status**: not_tested/success/failed
- **score_vs_random**: Score against random agent
- **errors**: Error messages if any

### Step 2: Test Single Submission (Optional)

Test one submission before running full tournament:

```bash
python3 test_single_submission.py submission_369130981
```

This will:
1. Copy the submission to `submissions/` directory
2. Start web server on port 9500
3. Start student bot (circle player)
4. Start random bot (square player)
5. Monitor the game until completion

You can open `http://localhost:9500` to watch the game in your browser.

### Step 3: Run Full Tournament

Run all submissions against random agent:

```bash
python3 run_tournament.py
```

This will:
- Test each submission sequentially
- Skip submissions with forbidden imports
- Compile C++ submissions if needed
- Run each game with timeout
- Update `results/tournament_results.csv` with scores
- Save logs to `logs/<folder_name>.log`

## Environment Settings

The system enforces:
- **Single-threaded**: `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, etc.
- **GPU support**: `CUDA_VISIBLE_DEVICES=0` (if GPU available)
- **Timeout**: 3 minutes per game
- **Board size**: Medium (15×14) by default
- **Time per player**: 60 seconds

## Forbidden Libraries

Submissions using these libraries will be **skipped**:
- ~~torch / pytorch~~ **[NOW ALLOWED]**
- tensorflow
- keras
- sklearn / scikit-learn
- cv2 / opencv
- pandas
- matplotlib / seaborn / plotly

## CSV Output Format

### submissions_list.csv (after parse_submissions.py)

```csv
folder_name,student_id,type,has_report,has_cmake,forbidden_imports,status,compilation_status,score_vs_random,errors
submission_369130981,2023CS50077,2023CS10322,python,True,False,NONE,pending,not_tested,,
submission_369109993,2022EE11672,python,True,False,torch,pending,not_tested,,
...
```

### tournament_results.csv (after run_tournament.py)

Same format, but with updated:
- **status**: completed/failed/skipped
- **compilation_status**: success/failed/n/a
- **score_vs_random**: Numeric score (0-100)
- **errors**: Any error messages

## Troubleshooting

### CMake not found (for C++ submissions)

```bash
# macOS
brew install cmake

# Linux
sudo apt-get install cmake
```

### Port already in use

Edit the `PORT` variable in the scripts:
- `test_single_submission.py`: Line 13
- `run_tournament.py`: Line 18

### Submission fails to load

Check the log file in `logs/<folder_name>.log` for detailed error messages.

## Results Summary

After running the tournament, check:

```bash
# View CSV
cat results/tournament_results.csv

# Count results
grep "completed" results/tournament_results.csv | wc -l  # Successful tests
grep "failed" results/tournament_results.csv | wc -l     # Failed tests
grep "skipped" results/tournament_results.csv | wc -l    # Skipped (forbidden imports)
```

## Current Status

**Total submissions**: 123
- Python: 67
- Mixed (Python+C++): 56
- C++ only: 0
- With forbidden imports: 1 (will be skipped)

## Next Steps

1. Run `parse_submissions.py` to create initial CSV ✅ DONE
2. Test a few submissions with `test_single_submission.py`
3. Run full tournament with `run_tournament.py`
4. Analyze results in `tournament_results.csv`
5. Generate final rankings and reports
