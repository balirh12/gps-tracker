-- GPS Tracker Database Schema
-- This script creates the necessary tables for storing GPS coordinates with PostGIS

-- Ensure PostGIS extension is enabled
CREATE EXTENSION IF NOT EXISTS postgis;

-- Drop existing table if it exists (for clean setup)
DROP TABLE IF EXISTS user_locations;

-- Create the main table for storing user GPS locations
CREATE TABLE user_locations (
    id SERIAL PRIMARY KEY,                                    -- Auto-incrementing ID
    user_id VARCHAR(50) NOT NULL,                             -- User identifier
    geom GEOMETRY(POINT, 4326) NOT NULL,                      -- PostGIS point geometry (WGS84)
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,              -- When coordinate was recorded
    synced_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP, -- When uploaded to server
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP -- Database insert time
);

-- Create index on user_id for faster queries by user
CREATE INDEX idx_user_locations_user_id ON user_locations(user_id);

-- Create spatial index on geometry column for efficient spatial queries
CREATE INDEX idx_user_locations_geom ON user_locations USING GIST(geom);

-- Create index on timestamp for time-based queries
CREATE INDEX idx_user_locations_timestamp ON user_locations(timestamp);

-- Create a composite index for user + time queries
CREATE INDEX idx_user_locations_user_time ON user_locations(user_id, timestamp);

-- Add a check constraint to ensure coordinates are within valid ranges
-- Latitude: -90 to 90, Longitude: -180 to 180
ALTER TABLE user_locations ADD CONSTRAINT check_valid_coordinates
    CHECK (
        ST_Y(geom) >= -90 AND ST_Y(geom) <= 90 AND
        ST_X(geom) >= -180 AND ST_X(geom) <= 180
    );

-- Optional: Create a table to track sync statistics
CREATE TABLE IF NOT EXISTS sync_logs (
    id SERIAL PRIMARY KEY,
    sync_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    records_synced INTEGER,
    status VARCHAR(20),  -- 'success', 'partial', 'failed'
    error_message TEXT
);

-- Create a view for easier querying with lat/lon columns
CREATE OR REPLACE VIEW user_locations_view AS
SELECT 
    id,
    user_id,
    ST_Y(geom) AS latitude,
    ST_X(geom) AS longitude,
    geom,
    timestamp,
    synced_at,
    created_at
FROM user_locations;

-- Grant permissions (adjust as needed for your setup)
-- GRANT ALL PRIVILEGES ON TABLE user_locations TO your_app_user;
-- GRANT ALL PRIVILEGES ON TABLE sync_logs TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE user_locations_id_seq TO your_app_user;
-- GRANT USAGE, SELECT ON SEQUENCE sync_logs_id_seq TO your_app_user;

-- Display table information
\d user_locations
