# GPS Tracker Architecture Documentation

## System Overview

This project implements an offline-first GPS tracking system with PostgreSQL/PostGIS backend.

```
┌─────────────────────────────────────────────────────────────────┐
│                          Mobile Device                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │               Offline GPS Collector                       │  │
│  │  • Collects GPS coordinates (lat, lon, timestamp)        │  │
│  │  • Stores locally in SQLite                              │  │
│  │  • Works without internet connection                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                │ Internet Available
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Sync Service                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Reads unsynced data from SQLite                       │  │
│  │  • Batch inserts into PostgreSQL                         │  │
│  │  • Handles errors and retries                            │  │
│  │  • Marks data as synced                                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PostgreSQL + PostGIS                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Table: user_locations                                    │  │
│  │  ┌─────────┬──────────┬────────┬───────────────────────┐ │  │
│  │  │ user_id │   geom   │ timestamp │     synced_at     │ │  │
│  │  ├─────────┼──────────┼───────────┼───────────────────┤ │  │
│  │  │ user_1  │ POINT(x,y)│ 2025-...  │ 2025-...          │ │  │
│  │  └─────────┴──────────┴───────────┴───────────────────┘ │  │
│  │                                                           │  │
│  │  Spatial Indexes: GIST(geom)                             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Spatial Queries                            │
│  • Distance calculations                                        │
│  • Radius searches                                              │
│  • Trajectory analysis                                          │
│  • Clustering                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. Offline Collector (`offline_collector.py`)

**Purpose**: Simulates a mobile app collecting GPS coordinates while offline.

**Key Features**:
- SQLite database for local storage
- No internet required
- Tracks sync status
- Generates realistic GPS simulation

**Database Schema (SQLite)**:
```sql
CREATE TABLE offline_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timestamp TEXT NOT NULL,
    synced INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Main Methods**:
- `collect_coordinate()`: Store a single GPS point
- `get_unsynced_locations()`: Retrieve data pending sync
- `mark_as_synced()`: Update sync status
- `simulate_gps_collection()`: Generate test data

### 2. Sync Service (`sync_service.py`)

**Purpose**: Synchronizes offline data to PostgreSQL with error handling.

**Key Features**:
- Batch processing for efficiency
- Transaction handling
- Connection retry logic
- Sync logging

**Sync Process**:
1. Connect to PostgreSQL (with retries)
2. Read batch from SQLite
3. Transform coordinates to PostGIS POINT
4. Execute batch insert
5. Mark as synced on success
6. Log results

**PostGIS Geometry Creation**:
```sql
ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
```
- `ST_MakePoint`: Creates point from lon/lat
- `ST_SetSRID`: Sets coordinate system (4326 = WGS84)

### 3. Spatial Queries (`spatial_queries.py`)

**Purpose**: Demonstrates PostGIS spatial analysis capabilities.

**Available Queries**:

1. **Distance Between Users**
   ```sql
   ST_Distance(point1::geography, point2::geography)
   ```
   - Returns distance in meters
   - Uses geography type for accuracy

2. **Radius Search**
   ```sql
   ST_DWithin(point::geography, center::geography, radius)
   ```
   - Finds all points within radius
   - Efficient with spatial index

3. **Nearest Neighbors**
   ```sql
   ORDER BY ST_Distance(point, target) ASC
   ```
   - Finds N closest points
   - Useful for "find nearby users"

4. **Trajectory Length**
   ```sql
   ST_Length(ST_MakeLine(points)::geography)
   ```
   - Calculates total distance traveled
   - Creates line from ordered points

5. **Clustering**
   ```sql
   ST_ClusterDBSCAN(point::geography, eps, minpoints)
   ```
   - Groups nearby locations
   - Identifies frequently visited areas

### 4. Database Schema (`database_setup.sql`)

**Main Table**: `user_locations`

```sql
CREATE TABLE user_locations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(50) NOT NULL,
    geom GEOMETRY(POINT, 4326) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes**:
- B-tree on `user_id` (user filtering)
- GIST on `geom` (spatial queries)
- B-tree on `timestamp` (time filtering)

**View for Easy Querying**:
```sql
CREATE VIEW user_locations_view AS
SELECT 
    id,
    user_id,
    ST_Y(geom) AS latitude,
    ST_X(geom) AS longitude,
    timestamp
FROM user_locations;
```

## Data Flow

### Collection Phase
```
GPS Hardware → Offline Collector → SQLite
  (lat, lon)     (simulation)      (local)
```

### Sync Phase
```
SQLite → Sync Service → PostgreSQL/PostGIS
(local)   (batch upload)   (cloud)
```

### Query Phase
```
PostgreSQL/PostGIS → Spatial Queries → Results
    (geometry)      (ST_* functions)   (analysis)
```

## Performance Considerations

### 1. Batch Processing
- Sync uses `execute_values()` for efficient batch inserts
- Default batch size: 100 records
- Reduces round trips to database

### 2. Spatial Indexes
- GIST index on geometry column
- Dramatically speeds up spatial queries
- Essential for large datasets

### 3. Geography vs Geometry
- **Geometry**: Flat plane, fast, less accurate
- **Geography**: Spherical earth, slower, accurate
- Use geography for distance calculations

### 4. Connection Pooling
- Consider connection pooling for production
- psycopg2.pool module
- Reduces connection overhead

## Error Handling

### Sync Failures
1. **Connection Error**: Retry with exponential backoff
2. **Batch Error**: Rollback transaction, log error
3. **Partial Failure**: Continue with next batch

### Data Integrity
- Transactions ensure all-or-nothing inserts
- Sync status prevents duplicate uploads
- Constraints ensure valid coordinates

## Security Considerations

### Database
- Use strong passwords
- Limit user permissions
- Enable SSL for production

### Application
- Sanitize user input
- Use parameterized queries (prevents SQL injection)
- Store credentials in environment variables (not in code)

## Scaling Strategies

### For Large Datasets
1. **Partition tables** by time or user
2. **Archive old data** to separate tables
3. **Use materialized views** for common queries
4. **Implement connection pooling**

### For High Traffic
1. **Read replicas** for query workload
2. **Cache frequent queries** (Redis/Memcached)
3. **Queue sync operations** (Celery/RabbitMQ)
4. **Load balancing** for API endpoints

## PostGIS Functions Reference

### Distance Functions
- `ST_Distance()`: Distance between geometries
- `ST_DWithin()`: Check if within distance
- `ST_Length()`: Length of line string

### Geometric Functions
- `ST_MakePoint()`: Create point from coordinates
- `ST_MakeLine()`: Create line from points
- `ST_Centroid()`: Center point of geometry

### Spatial Relationships
- `ST_Within()`: Check if geometry is inside another
- `ST_Contains()`: Check if geometry contains another
- `ST_Intersects()`: Check if geometries overlap

### Coordinate Systems
- `ST_SetSRID()`: Set spatial reference ID
- `ST_Transform()`: Convert between coordinate systems
- SRID 4326: WGS84 (lat/lon)

## Configuration Options

### Database (`config.py`)
- `DB_CONFIG`: PostgreSQL connection parameters
- `SQLITE_DB_PATH`: Local database location
- `BATCH_SIZE`: Records per sync batch
- `MAX_RETRIES`: Connection retry attempts

### Simulation (`config.py`)
- `SIMULATION_USERS`: Number of simulated users
- `SIMULATION_POINTS_PER_USER`: Points per user
- `SIMULATION_AREA`: Geographic bounds

## Testing

### Unit Tests
```bash
python test_system.py
```

Tests:
- Module imports
- Configuration validity
- SQLite creation
- GPS simulation
- PostgreSQL connection
- PostGIS extension
- Database schema

### Integration Tests
```bash
python main.py
```

Full workflow:
- Collect offline data
- Sync to PostgreSQL
- Run spatial queries

## Monitoring

### Logs
- File: `gps_tracker.log`
- Levels: DEBUG, INFO, WARNING, ERROR
- Includes timestamps and module names

### Sync Statistics
```sql
SELECT * FROM sync_logs 
ORDER BY sync_time DESC 
LIMIT 10;
```

## Troubleshooting

### Common Issues

1. **"psycopg2 not found"**
   ```bash
   pip install psycopg2-binary
   ```

2. **"PostGIS extension not found"**
   ```sql
   CREATE EXTENSION postgis;
   ```

3. **"Connection refused"**
   - Check PostgreSQL is running
   - Verify credentials in config.py
   - Check firewall settings

4. **"No data to sync"**
   - Run offline_collector.py first
   - Check SQLite database exists
   - Verify unsynced count

## Production Deployment

### Checklist
- [ ] Use environment variables for credentials
- [ ] Enable SSL/TLS connections
- [ ] Set up automated backups
- [ ] Configure log rotation
- [ ] Implement monitoring/alerting
- [ ] Set up connection pooling
- [ ] Create database user with minimal permissions
- [ ] Enable query logging
- [ ] Set up regular VACUUM operations
- [ ] Configure firewall rules

### Environment Variables
```bash
export PGHOST=localhost
export PGDATABASE=gps_tracker
export PGUSER=gps_app_user
export PGPASSWORD=secure_password
export PGPORT=5432
```

### Docker Deployment
```dockerfile
FROM python:3.9
RUN apt-get update && apt-get install -y postgresql-client
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . /app
WORKDIR /app
CMD ["python", "main.py"]
```

## Future Enhancements

### Possible Features
1. **Real-time tracking** with WebSocket connections
2. **Geofencing** with polygon queries
3. **Heat maps** of user activity
4. **Route optimization** using pgRouting
5. **Mobile app** (React Native/Flutter)
6. **Web dashboard** for visualization
7. **API layer** (FastAPI/Flask)
8. **Push notifications** for proximity alerts

### Advanced Queries
1. **Time-space clustering** (where + when)
2. **Predictive routing** (ML integration)
3. **Anomaly detection** (unusual movements)
4. **Privacy zones** (exclude sensitive areas)
