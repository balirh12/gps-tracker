# GPS Tracker with Offline Support and PostGIS

A Python project demonstrating offline GPS data collection with PostgreSQL/PostGIS synchronization.

## Features

- 📍 Simulates offline GPS coordinate collection
- 💾 Stores data locally in SQLite
- 🔄 Batch synchronization to PostgreSQL/PostGIS
- 📊 Spatial queries using PostGIS
- 🔒 Error handling and retry logic
- 📝 Comprehensive logging

## Project Structure

```
gps-tracker/
├── README.md
├── requirements.txt
├── config.py              # Database configuration
├── database_setup.sql     # PostgreSQL schema
├── offline_collector.py   # Simulates offline data collection
├── sync_service.py        # Syncs data to PostgreSQL
├── spatial_queries.py     # PostGIS query examples
└── main.py               # Demo orchestration
```

## Prerequisites

- Python 3.8+
- PostgreSQL 12+ with PostGIS extension
- pip (Python package manager)

## Setup Instructions

### 1. Install PostgreSQL and PostGIS

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib postgis
```

**macOS (with Homebrew):**
```bash
brew install postgresql postgis
```

### 2. Create Database and Enable PostGIS

```bash
# Connect to PostgreSQL
sudo -u postgres psql

# In PostgreSQL shell:
CREATE DATABASE gps_tracker;
\c gps_tracker
CREATE EXTENSION postgis;
\q
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Database Connection

Edit `config.py` with your PostgreSQL credentials:
```python
DB_CONFIG = {
    'host': 'localhost',
    'database': 'gps_tracker',
    'user': 'postgres',
    'password': 'your_password',
    'port': 5432
}
```

### 5. Initialize Database Schema

```bash
psql -U postgres -d gps_tracker -f database_setup.sql
```

## Usage

### Run Complete Demo

```bash
python main.py
```

This will:
1. Simulate offline GPS collection for 3 users
2. Store data locally in SQLite
3. Sync data to PostgreSQL/PostGIS
4. Run spatial query examples

### Individual Components

**Collect GPS data offline:**
```bash
python offline_collector.py
```

**Sync to PostgreSQL:**
```bash
python sync_service.py
```

**Run spatial queries:**
```bash
python spatial_queries.py
```

## Database Schema

The PostgreSQL table stores:
- `id`: Auto-incrementing primary key
- `user_id`: User identifier
- `geom`: PostGIS POINT geometry (SRID 4326)
- `timestamp`: When the coordinate was recorded
- `synced_at`: When the data was uploaded

## Example Spatial Queries

- Find distance between two users
- Get all locations within a radius
- Find nearest users to a location
- Calculate user movement trajectory length

## Error Handling

The sync service includes:
- Database connection retry logic
- Batch insert transaction handling
- Failed sync logging and retry queue
- Network error recovery

## Logging

Logs are written to `gps_tracker.log` with:
- Offline collection events
- Sync attempts and results
- Error details
- Query execution times
