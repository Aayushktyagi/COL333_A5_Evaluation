# Evaluation System for COL333 Assignment 5

This directory contains the evaluation infrastructure for testing student submissions in parallel.

## Essential Files

```
evaluation/
├── parse_submissions.py         # Scans and catalogs all submissions
├── run_all_tests_parallel.py    # Runs all submissions in parallel (MAIN SCRIPT)
├── test_bot_student.py          # Bot client for student agent
├── test_bot_random.py           # Bot client for random agent
└── results/
    └── submissions_list.csv     # Catalog of all submissions with results
```

## Prerequisites

### 1. Python Environment

Python 3.9+ with required packages:
```bash
pip install flask flask-socketio pygame requests
```

### 2. Directory Structure Required

You need three directories:
- **Reference implementation** - Path to clean gameEngine.py, agent.py, web_server.py, etc.
- **Submissions directory** - Path to folder containing all submission_* folders
- **Evaluation directory** - This directory (where scripts are)

### 3. Update Paths in Scripts

Edit these paths in the scripts to match your machine:

**In `parse_submissions.py`:**
```python
SUBMISSIONS_BASE = "/path/to/assignment_export"
OUTPUT_CSV = "/path/to/evaluation/results/submissions_list.csv"
```

**In `run_all_tests_parallel.py`:**
```python
SUBMISSIONS_CSV = "/path/to/evaluation/results/submissions_list.csv"
EVALUATION_DIR = "/path/to/evaluation"
REFERENCE_DIR = "/path/to/reference/client_server"
SUBMISSIONS_BASE = "/path/to/assignment_export"
```

**In `test_bot_student.py` and `test_bot_random.py`:**
No changes needed - they receive paths as arguments.

### 4. Environment Variables (Optional but Recommended)

For consistent single-threaded execution:
```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=0
```

## Step-by-Step Usage

### Step 1: Parse All Submissions

First, scan and catalog all submissions:

```bash
cd evaluation
python3 parse_submissions.py
```

This creates `results/submissions_list.csv` with:
- Student IDs extracted from reports
- Submission types (python/cpp/mixed)
- Forbidden imports detection (PyTorch is ALLOWED)
- Duplicate submission detection
- Report file locations (handles typos, subdirectories, PDFs)

### Step 2: Run Parallel Tests

Test all eligible Python submissions in parallel:

```bash
python3 run_all_tests_parallel.py
```

**Configuration (edit in script):**
- `NUM_PARALLEL_SERVERS = 8` - Number of parallel servers (adjust based on CPU cores)
- `BASE_PORT = 9500` - Starting port number
- `TIMEOUT_PER_GAME = 300` - Timeout per game in seconds (5 minutes)

**What it does:**
- Creates 8 parallel servers on ports 9500-9507
- Tests each Python submission vs random agent
- Automatically rotates submissions across servers
- Updates `submissions_list.csv` with results
- Provides detailed summary of successes/failures

**Output:**
```
✅ COMPLETED: X submissions
❌ ERRORS: Y submissions  
⏱️  TIMEOUTS: Z submissions

Lists:
- All completed submissions with winners and scores
- All failed submissions with error messages
- All timeout submissions
```

## Understanding Results

### submissions_list.csv Columns

- `folder_name` - Submission folder name
- `student_id` - Student ID(s) from report file
- `type` - python/cpp/mixed
- `has_report` - True/False
- `report_file` - Path to report (handles typos: .rxt, .tzt, subdirs, PDFs)
- `forbidden_imports` - Forbidden libraries found (or NONE)
- `duplicate_of` - If duplicate, shows which submission to keep
- `status` - COMPLETED/ERROR/TIMEOUT/SKIPPED
- `score_vs_random` - Format: `winner|S:student_score|R:random_score|T:turns`
- `errors` - Error messages if failed

### Submission Selection Criteria

Tests only submissions that are:
- ✅ Python type
- ✅ No forbidden imports
- ✅ Not marked as duplicate

## Troubleshooting

### Port Conflicts
If ports 9500-9507 are in use:
```bash
# Check what's using the ports
lsof -i :9500-9507

# Change BASE_PORT in run_all_tests_parallel.py
BASE_PORT = 10000  # Use different port range
```

### Timeout Issues
If games timeout frequently, increase timeout:
```python
TIMEOUT_PER_GAME = 600  # 10 minutes
```

### Memory Issues
If running out of memory, reduce parallel servers:
```python
NUM_PARALLEL_SERVERS = 4  # Use fewer parallel processes
```

### Failed to Start Errors
- Check that reference files exist and are accessible
- Verify Python environment has all required packages
- Check file permissions

## Performance

With 8 parallel servers:
- ~65 Python submissions
- ~8-9 batches of games
- Each game: 30s - 5min
- Total time: ~40-60 minutes

Sequential would take: ~5-8 hours

## Notes

- **PyTorch is ALLOWED** (removed from forbidden list)
- **C++ submissions** are skipped (require compilation infrastructure)
- **Duplicate submissions** are automatically detected and marked
- **Board sizes** are randomly assigned (small/medium/large)
- **Logs** are saved in `temp_tests/` directory for debugging
- **Results** are automatically saved to CSV after completion
