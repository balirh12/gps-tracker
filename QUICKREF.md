# GPS Tracker Quick Reference Guide

## Installation

### One-Line Setup (Linux/macOS)
```bash
chmod +x setup.sh && ./setup.sh
```

### Manual Setup
```bash
# 1. Install PostgreSQL with PostGIS
sudo apt-get install postgresql postgresql-contrib postgis

# 2. Create database
sudo -u postgres psql -c "CREATE DATABASE gps_tracker;"
sudo -u postgres psql -d gps_tracker -c "CREATE EXTENSION postgis;"

# 3. Initialize schema
psql -U postgres -d gps_tracker -f database_setup.sql

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Configure credentials
nano config.py  # Update DB password
```

## Quick Start

### Run Complete Demo
```bash
python main.py
```

### Test Installation
```bash
python test_system.py
```

## Common Tasks

### 1. Collect GPS Data
```python
from offline_collector import OfflineGPSCollector

collector = OfflineGPSCollector()
collector.collect_coordinate("user_1", 33.5731, -7.5898)
collector.close()
```

### 2. Sync to PostgreSQL
```python
from sync_service import SyncService

sync = SyncService()
stats = sync.sync_offline_data()
sync.close()
```

### 3. Find Distance Between Users
```python
from spatial_queries import SpatialQueries

sq = SpatialQueries()
distance = sq.distance_between_users("user_1", "user_2")
print(f"Distance: {distance:.2f} meters")
sq.close()
```

### 4. Find Nearby Locations
```python
from spatial_queries import SpatialQueries

sq = SpatialQueries()
locations = sq.locations_within_radius(33.5731, -7.5898, 500)
for loc in locations:
    print(f"{loc['user_id']}: {loc['distance_meters']:.2f}m away")
sq.close()
```

## SQL Queries

### View All Data
```sql
SELECT 
    user_id,
    ST_Y(geom) as latitude,
    ST_X(geom) as longitude,
    timestamp
FROM user_locations
ORDER BY timestamp DESC
LIMIT 10;
```

### Count Records Per User
```sql
SELECT user_id, COUNT(*) as count
FROM user_locations
GROUP BY user_id;
```

### Find Closest Points
```sql
SELECT 
    user_id,
    ST_Distance(
        geom::geography,
        ST_SetSRID(ST_MakePoint(-7.5898, 33.5731), 4326)::geography
    ) as distance
FROM user_locations
ORDER BY distance
LIMIT 5;
```

### Calculate Travel Distance
```sql
SELECT 
    user_id,
    ST_Length(ST_MakeLine(geom ORDER BY timestamp)::geography) as meters
FROM user_locations
GROUP BY user_id;
```

## Configuration

### Database Settings (`config.py`)
```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'gps_tracker',
    'user': 'postgres',
    'password': 'your_password',
    'port': 5432
}
```

### Sync Settings
```python
BATCH_SIZE = 100      # Records per batch
MAX_RETRIES = 3       # Connection retries
RETRY_DELAY = 5       # Seconds between retries
```

### Simulation Settings
```python
SIMULATION_USERS = 3
SIMULATION_POINTS_PER_USER = 50
SIMULATION_AREA = {
    'lat_min': 33.64,
    'lat_max': 33.65,
    'lon_min': -7.60,
    'lon_max': -7.58
}
```

## Troubleshooting

### Database Connection Failed
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -U postgres -d gps_tracker -c "SELECT 1;"
```

### PostGIS Not Found
```sql
-- Enable PostGIS
\c gps_tracker
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Import Errors
```bash
# Reinstall dependencies
pip install --force-reinstall -r requirements.txt
```

### Clear All Data
```bash
# Clear PostgreSQL
psql -U postgres -d gps_tracker -c "TRUNCATE user_locations;"

# Clear SQLite
rm offline_gps.db
```

## File Structure

```
gps-tracker/
├── main.py                 # Main demo script
├── offline_collector.py    # GPS collection
├── sync_service.py         # Data synchronization
├── spatial_queries.py      # PostGIS queries
├── examples.py             # Usage examples
├── test_system.py          # System tests
├── config.py               # Configuration
├── database_setup.sql      # Database schema
├── requirements.txt        # Python dependencies
├── setup.sh                # Setup script
├── README.md               # Main documentation
└── ARCHITECTURE.md         # Technical details
```

## Command Line Usage

### Run Individual Modules
```bash
# Collect data
python offline_collector.py

# Sync to database
python sync_service.py

# Run queries
python spatial_queries.py

# Run examples
python examples.py
```

### Database Management
```bash
# Connect to database
psql -U postgres -d gps_tracker

# View table structure
\d user_locations

# View all tables
\dt

# Exit psql
\q
```

### Check Logs
```bash
# View logs
tail -f gps_tracker.log

# Search logs
grep "ERROR" gps_tracker.log
```

## PostGIS Functions

### Distance Calculations
```sql
-- Distance in meters
ST_Distance(geom1::geography, geom2::geography)

-- Check if within distance
ST_DWithin(geom1::geography, geom2::geography, distance)
```

### Geometry Creation
```sql
-- Create point
ST_MakePoint(longitude, latitude)

-- Set coordinate system
ST_SetSRID(geometry, 4326)

-- Create line from points
ST_MakeLine(geom ORDER BY timestamp)
```

### Spatial Relationships
```sql
-- Within bounds
ST_Within(geom, ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326))

-- Intersection
ST_Intersects(geom1, geom2)

-- Contains
ST_Contains(geom1, geom2)
```

## Performance Tips

### For Large Datasets
1. Use batch inserts (already implemented)
2. Create indexes on frequently queried columns
3. Partition tables by date/user
4. Use `EXPLAIN ANALYZE` to optimize queries

### Query Optimization
```sql
-- Check query plan
EXPLAIN ANALYZE
SELECT * FROM user_locations
WHERE ST_DWithin(geom::geography, point::geography, 1000);

-- Vacuum regularly
VACUUM ANALYZE user_locations;
```

## Environment Variables

### Set Database Credentials
```bash
export PGHOST=localhost
export PGDATABASE=gps_tracker
export PGUSER=postgres
export PGPASSWORD=your_password
export PGPORT=5432
```

### Python Environment
```bash
# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

## API Example (Future Enhancement)

### FastAPI Integration
```python
from fastapi import FastAPI
from spatial_queries import SpatialQueries

app = FastAPI()
sq = SpatialQueries()

@app.get("/users/nearby")
def get_nearby_users(lat: float, lon: float, radius: float):
    locations = sq.locations_within_radius(lat, lon, radius)
    return {"locations": locations}
```

## Backup and Restore

### Backup PostgreSQL
```bash
# Full backup
pg_dump -U postgres gps_tracker > backup.sql

# Data only
pg_dump -U postgres --data-only gps_tracker > data_backup.sql
```

### Restore PostgreSQL
```bash
# Restore full backup
psql -U postgres gps_tracker < backup.sql

# Restore data only
psql -U postgres gps_tracker < data_backup.sql
```

## Security Best Practices

1. **Never commit credentials** to version control
2. **Use environment variables** for sensitive data
3. **Create limited database user** for application
4. **Enable SSL** for production databases
5. **Validate input** before processing
6. **Use prepared statements** (already implemented)

## Resources

### Documentation
- PostGIS: https://postgis.net/docs/
- PostgreSQL: https://www.postgresql.org/docs/
- psycopg2: https://www.psycopg.org/docs/

### Learning
- PostGIS Workshop: https://postgis.net/workshops/
- PostgreSQL Tutorial: https://www.postgresqltutorial.com/

## Support

### Getting Help
1. Check logs: `gps_tracker.log`
2. Run tests: `python test_system.py`
3. Review documentation: `README.md`, `ARCHITECTURE.md`

### Common Error Messages

**"relation user_locations does not exist"**
→ Run: `psql -U postgres -d gps_tracker -f database_setup.sql`

**"no such module: psycopg2"**
→ Run: `pip install psycopg2-binary`

**"FATAL: password authentication failed"**
→ Check credentials in `config.py`

**"could not connect to server"**
→ Check PostgreSQL is running: `sudo systemctl status postgresql`
