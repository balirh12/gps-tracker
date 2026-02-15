"""
Configuration file for GPS Tracker application.
Contains database connection settings and application parameters.
"""

# PostgreSQL Database Configuration
# Update these values according to your PostgreSQL setup
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'gps_tracker'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'changeme'),
    'port': int(os.getenv('DB_PORT', 5432))
}

# Local SQLite Database (for offline storage)
SQLITE_DB_PATH = 'offline_gps.db'

# Sync Configuration
BATCH_SIZE = 100  # Number of records to sync at once
MAX_RETRIES = 3   # Maximum number of retry attempts for failed syncs
RETRY_DELAY = 5   # Seconds to wait between retries

# Logging Configuration
LOG_FILE = 'gps_tracker.log'
LOG_LEVEL = 'INFO'  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Simulation Parameters
SIMULATION_USERS = 3
SIMULATION_POINTS_PER_USER = 50
SIMULATION_AREA = {
    'lat_min': 33.64,  # Casablanca area
    'lat_max': 33.65,
    'lon_min': -7.60,
    'lon_max': -7.58
}
