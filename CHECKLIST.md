# Quick Start Checklist

## Before Running on New Machine

### 1. Install Dependencies
```bash
pip install flask flask-socketio pygame requests
```

### 2. Update Paths in Scripts

Edit the following constants in each script:

#### parse_submissions.py
- [ ] Line ~12: `SUBMISSIONS_BASE = "/your/path/to/assignment_export"`
- [ ] Line ~13: `OUTPUT_CSV = "/your/path/to/evaluation/results/submissions_list.csv"`

#### run_all_tests_parallel.py
- [ ] Line ~14: `SUBMISSIONS_CSV = "/your/path/to/evaluation/results/submissions_list.csv"`
- [ ] Line ~15: `EVALUATION_DIR = "/your/path/to/evaluation"`
- [ ] Line ~16: `REFERENCE_DIR = "/your/path/to/reference/client_server"`
- [ ] Line ~17: `SUBMISSIONS_BASE = "/your/path/to/assignment_export"`

### 3. Set Environment Variables (Optional)
```bash
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export CUDA_VISIBLE_DEVICES=0
```

### 4. Run Evaluation

```bash
# Step 1: Parse submissions
python3 parse_submissions.py

# Step 2: Run parallel tests
python3 run_all_tests_parallel.py
```

## Files You Need

### On New Machine
1. This evaluation/ directory (all scripts)
2. Reference implementation directory (gameEngine.py, agent.py, web_server.py, etc.)
3. Submissions directory (all submission_* folders)

### What Gets Created
- results/submissions_list.csv (submission catalog and results)
- temp_tests/ (temporary test directories with logs)

## Expected Results

After completion, you'll see:
- ✅ Number of completed submissions
- ❌ Number of failed submissions with errors
- ⏱️ Number of timeout submissions
- 🏆 Winner statistics (student vs random)
- Updated submissions_list.csv with all results

## Common Issues

1. **Port conflicts**: Change BASE_PORT in run_all_tests_parallel.py
2. **Timeouts**: Increase TIMEOUT_PER_GAME
3. **Memory issues**: Reduce NUM_PARALLEL_SERVERS
4. **Path errors**: Double-check all path updates
