"""
Configuration file for evaluation system.
Update these paths for your machine.
"""

# Path to the directory containing all submission_* folders
SUBMISSIONS_BASE = "/path/to/assignment_7153640_export"

# Path to the reference implementation (contains gameEngine.py, agent.py, web_server.py, etc.)
REFERENCE_DIR = "/path/to/COL333_2025_A5/client_server"

# Path to this evaluation directory
EVALUATION_DIR = "/path/to/evaluation"

# Output CSV location
OUTPUT_CSV = "/path/to/evaluation/results/submissions_list.csv"

# Parallel testing configuration
NUM_PARALLEL_SERVERS = 8  # Number of parallel servers (adjust based on CPU cores)
BASE_PORT = 9500  # Starting port number
TIMEOUT_PER_GAME = 300  # Timeout per game in seconds (5 minutes)

# Board sizes to test with
BOARD_SIZES = ['small', 'medium', 'large']

# Forbidden libraries (PyTorch is ALLOWED)
FORBIDDEN_LIBRARIES = [
    'tensorflow', 'keras', 'sklearn', 'cv2', 'opencv',
    'pandas', 'matplotlib', 'seaborn', 'plotly'
]
