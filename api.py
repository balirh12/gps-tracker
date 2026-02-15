"""
GPS Tracker REST API - Enhanced Version
A modern REST API for GPS tracking with offline support and PostGIS spatial analysis.

Features:
- Real-time GPS collection
- Offline data synchronization
- Advanced spatial queries
- User management
- Analytics and statistics
- Geofencing
- Route optimization
"""

from fastapi import FastAPI, HTTPException, Query, Path, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uvicorn
import logging

from offline_collector import OfflineGPSCollector
from sync_service import SyncService
from spatial_queries import SpatialQueries

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="🌍 GPS Tracker API",
    description="Modern GPS tracking system with offline support and spatial analysis",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== DATA MODELS ====================

class GPSPoint(BaseModel):
    """GPS coordinate data model"""
    user_id: str = Field(..., description="Unique user identifier", min_length=1, max_length=50)
    latitude: float = Field(..., ge=-90, le=90, description="Latitude (-90 to 90)")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude (-180 to 180)")
    timestamp: Optional[datetime] = Field(None, description="Timestamp (auto-generated if not provided)")
    
    @field_validator('latitude')
    @classmethod
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        return v
    
    @field_validator('longitude')
    @classmethod
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        return v

class BulkGPSPoints(BaseModel):
    """Bulk GPS data collection"""
    points: List[GPSPoint] = Field(..., description="List of GPS points to collect")

class LocationQuery(BaseModel):
    """Location search query"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(..., gt=0, le=50000, description="Search radius in meters (max 50km)")

class GeofenceArea(BaseModel):
    """Geofence area definition"""
    name: str = Field(..., description="Geofence name")
    center_lat: float = Field(..., ge=-90, le=90)
    center_lon: float = Field(..., ge=-180, le=180)
    radius_meters: float = Field(..., gt=0, le=10000)

class TimeRange(BaseModel):
    """Time range filter"""
    start_time: datetime
    end_time: datetime

# ==================== HELPER FUNCTIONS ====================

def success_response(data: Any, message: str = "Success") -> Dict:
    """Standard success response format"""
    return {
        "status": "success",
        "message": message,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }

def error_response(message: str, details: str = None) -> Dict:
    """Standard error response format"""
    return {
        "status": "error",
        "message": message,
        "details": details,
        "timestamp": datetime.now().isoformat()
    }

# ==================== ROOT & INFO ENDPOINTS ====================

@app.get("/", tags=["Info"])
def root():
    """API root - Welcome message and available endpoints"""
    return {
        "message": "🌍 GPS Tracker API - Enhanced Version",
        "version": "2.0.0",
        "status": "operational",
        "documentation": "/docs",
        "endpoints": {
            "GPS Collection": {
                "POST /api/v1/gps/collect": "Collect single GPS point",
                "POST /api/v1/gps/collect/bulk": "Collect multiple GPS points",
                "POST /api/v1/gps/sync": "Sync offline data to database",
            },
            "Users": {
                "GET /api/v1/users": "List all users",
                "GET /api/v1/users/{user_id}": "Get user details",
                "GET /api/v1/users/{user_id}/locations": "Get user location history",
                "DELETE /api/v1/users/{user_id}": "Delete user and their data",
            },
            "Spatial Analysis": {
                "GET /api/v1/distance/{user_id_1}/{user_id_2}": "Distance between users",
                "POST /api/v1/locations/nearby": "Find nearby locations",
                "GET /api/v1/users/{user_id}/trajectory": "User trajectory analysis",
                "POST /api/v1/geofence/check": "Check if user is in geofence",
            },
            "Analytics": {
                "GET /api/v1/stats": "System statistics",
                "GET /api/v1/analytics/heatmap": "Location heatmap data",
                "GET /api/v1/analytics/active-users": "Active users in time range",
            },
            "Health": {
                "GET /health": "API health check",
                "GET /api/v1/database/status": "Database connection status",
            }
        }
    }

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        cursor.execute("SELECT 1;")
        cursor.close()
        sq.close()
        
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

# ==================== GPS COLLECTION ENDPOINTS ====================

@app.post("/api/v1/gps/collect", tags=["GPS Collection"], status_code=status.HTTP_201_CREATED)
def collect_gps_point(point: GPSPoint):
    """
    Collect a single GPS point (offline storage).
    
    The point is stored locally in SQLite and will be synced to PostgreSQL later.
    """
    try:
        collector = OfflineGPSCollector()
        collector.collect_coordinate(
            point.user_id,
            point.latitude,
            point.longitude,
            point.timestamp or datetime.now()
        )
        stats = collector.get_stats()
        collector.close()
        
        return success_response(
            {
                "user_id": point.user_id,
                "coordinates": {"lat": point.latitude, "lon": point.longitude},
                "pending_sync": stats['unsynced']
            },
            f"GPS point collected for {point.user_id}"
        )
    except Exception as e:
        logger.error(f"Error collecting GPS point: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to collect GPS point", str(e)))

@app.post("/api/v1/gps/collect/bulk", tags=["GPS Collection"], status_code=status.HTTP_201_CREATED)
def collect_bulk_gps_points(data: BulkGPSPoints):
    """
    Collect multiple GPS points at once (batch collection).
    
    Useful for syncing multiple offline collected points.
    """
    try:
        collector = OfflineGPSCollector()
        collected = 0
        
        for point in data.points:
            collector.collect_coordinate(
                point.user_id,
                point.latitude,
                point.longitude,
                point.timestamp or datetime.now()
            )
            collected += 1
        
        stats = collector.get_stats()
        collector.close()
        
        return success_response(
            {
                "collected": collected,
                "total_pending_sync": stats['unsynced']
            },
            f"Collected {collected} GPS points"
        )
    except Exception as e:
        logger.error(f"Error collecting bulk GPS points: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to collect bulk points", str(e)))

@app.post("/api/v1/gps/sync", tags=["GPS Collection"])
def sync_offline_data():
    """
    Synchronize offline collected data to PostgreSQL database.
    
    Performs batch upload of all pending GPS points.
    """
    try:
        sync = SyncService()
        stats = sync.sync_offline_data()
        sync.close()
        
        return success_response(
            {
                "batches_processed": stats['batches'],
                "total_records": stats['total_processed'],
                "successful": stats['successful'],
                "failed": stats['failed'],
                "success_rate": f"{(stats['successful']/stats['total_processed']*100):.1f}%" if stats['total_processed'] > 0 else "0%"
            },
            "Data synchronized successfully"
        )
    except Exception as e:
        logger.error(f"Error syncing data: {e}")
        raise HTTPException(status_code=500, detail=error_response("Synchronization failed", str(e)))

# ==================== USER MANAGEMENT ENDPOINTS ====================

@app.get("/api/v1/users", tags=["Users"])
def get_all_users():
    """Get list of all users with their statistics"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(*) as point_count,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen,
                ST_Y(ST_Centroid(ST_Collect(geom))) as center_lat,
                ST_X(ST_Centroid(ST_Collect(geom))) as center_lon
            FROM user_locations
            GROUP BY user_id
            ORDER BY point_count DESC;
        """)
        
        users = []
        for row in cursor.fetchall():
            users.append({
                "user_id": row[0],
                "point_count": row[1],
                "first_seen": row[2].isoformat() if row[2] else None,
                "last_seen": row[3].isoformat() if row[3] else None,
                "activity_center": {
                    "latitude": round(row[4], 6) if row[4] else None,
                    "longitude": round(row[5], 6) if row[5] else None
                }
            })
        
        cursor.close()
        sq.close()
        
        return success_response(
            {"users": users, "total": len(users)},
            f"Found {len(users)} users"
        )
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to fetch users", str(e)))

@app.get("/api/v1/users/{user_id}", tags=["Users"])
def get_user_details(user_id: str = Path(..., description="User identifier")):
    """Get detailed information about a specific user"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        # Basic stats
        cursor.execute("""
            SELECT 
                COUNT(*) as point_count,
                MIN(timestamp) as first_seen,
                MAX(timestamp) as last_seen
            FROM user_locations
            WHERE user_id = %s;
        """, (user_id,))
        
        result = cursor.fetchone()
        if not result or result[0] == 0:
            cursor.close()
            sq.close()
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        
        # Calculate trajectory
        distance = sq.user_trajectory_length(user_id)
        
        # Get latest position
        cursor.execute("""
            SELECT ST_Y(geom) as lat, ST_X(geom) as lon, timestamp
            FROM user_locations
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT 1;
        """, (user_id,))
        
        latest = cursor.fetchone()
        
        cursor.close()
        sq.close()
        
        return success_response({
            "user_id": user_id,
            "statistics": {
                "total_points": result[0],
                "first_seen": result[1].isoformat() if result[1] else None,
                "last_seen": result[2].isoformat() if result[2] else None,
                "total_distance_km": round(distance / 1000, 2) if distance else 0
            },
            "latest_position": {
                "latitude": round(latest[0], 6) if latest else None,
                "longitude": round(latest[1], 6) if latest else None,
                "timestamp": latest[2].isoformat() if latest else None
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user details: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to fetch user details", str(e)))

@app.get("/api/v1/users/{user_id}/locations", tags=["Users"])
def get_user_locations(
    user_id: str = Path(..., description="User identifier"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of locations to return"),
    offset: int = Query(0, ge=0, description="Number of locations to skip")
):
    """Get location history for a specific user (paginated)"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        cursor.execute("""
            SELECT 
                ST_Y(geom) as latitude,
                ST_X(geom) as longitude,
                timestamp
            FROM user_locations
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s;
        """, (user_id, limit, offset))
        
        locations = []
        for row in cursor.fetchall():
            locations.append({
                "latitude": round(row[0], 6),
                "longitude": round(row[1], 6),
                "timestamp": row[2].isoformat()
            })
        
        # Get total count
        cursor.execute("SELECT COUNT(*) FROM user_locations WHERE user_id = %s;", (user_id,))
        total = cursor.fetchone()[0]
        
        cursor.close()
        sq.close()
        
        return success_response({
            "user_id": user_id,
            "locations": locations,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(locations),
                "total": total
            }
        })
    except Exception as e:
        logger.error(f"Error fetching user locations: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to fetch locations", str(e)))

@app.delete("/api/v1/users/{user_id}", tags=["Users"])
def delete_user(user_id: str = Path(..., description="User identifier")):
    """Delete a user and all their GPS data"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT COUNT(*) FROM user_locations WHERE user_id = %s;", (user_id,))
        count = cursor.fetchone()[0]
        
        if count == 0:
            cursor.close()
            sq.close()
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        
        # Delete user data
        cursor.execute("DELETE FROM user_locations WHERE user_id = %s;", (user_id,))
        sq.conn.commit()
        
        cursor.close()
        sq.close()
        
        return success_response(
            {"deleted_points": count},
            f"User '{user_id}' and {count} GPS points deleted"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to delete user", str(e)))

# ==================== SPATIAL ANALYSIS ENDPOINTS ====================

@app.get("/api/v1/distance/{user_id_1}/{user_id_2}", tags=["Spatial Analysis"])
def calculate_distance_between_users(
    user_id_1: str = Path(..., description="First user ID"),
    user_id_2: str = Path(..., description="Second user ID")
):
    """Calculate distance between two users' latest positions"""
    try:
        sq = SpatialQueries()
        distance = sq.distance_between_users(user_id_1, user_id_2)
        sq.close()
        
        if distance is None:
            raise HTTPException(status_code=404, detail="One or both users not found")
        
        return success_response({
            "user_1": user_id_1,
            "user_2": user_id_2,
            "distance_meters": round(distance, 2),
            "distance_km": round(distance / 1000, 3),
            "distance_miles": round(distance / 1609.34, 3)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating distance: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to calculate distance", str(e)))

@app.post("/api/v1/locations/nearby", tags=["Spatial Analysis"])
def find_nearby_locations(query: LocationQuery):
    """Find all locations within a specified radius"""
    try:
        sq = SpatialQueries()
        locations = sq.locations_within_radius(
            query.latitude,
            query.longitude,
            query.radius_meters
        )
        sq.close()
        
        # Group by user
        users_summary = {}
        for loc in locations:
            user = loc['user_id']
            if user not in users_summary:
                users_summary[user] = 0
            users_summary[user] += 1
        
        return success_response({
            "query": {
                "center": {"latitude": query.latitude, "longitude": query.longitude},
                "radius_meters": query.radius_meters,
                "radius_km": round(query.radius_meters / 1000, 2)
            },
            "results": {
                "total_locations": len(locations),
                "unique_users": len(users_summary),
                "users_summary": users_summary,
                "locations": locations[:50]  # Limit to 50 for response size
            }
        })
    except Exception as e:
        logger.error(f"Error finding nearby locations: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to find nearby locations", str(e)))

@app.get("/api/v1/users/{user_id}/trajectory", tags=["Spatial Analysis"])
def get_user_trajectory(user_id: str = Path(..., description="User identifier")):
    """Calculate total distance traveled by a user"""
    try:
        sq = SpatialQueries()
        distance = sq.user_trajectory_length(user_id)
        sq.close()
        
        if distance is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        
        return success_response({
            "user_id": user_id,
            "trajectory": {
                "total_distance_meters": round(distance, 2),
                "total_distance_km": round(distance / 1000, 3),
                "total_distance_miles": round(distance / 1609.34, 3)
            }
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating trajectory: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to calculate trajectory", str(e)))

@app.post("/api/v1/geofence/check", tags=["Spatial Analysis"])
def check_geofence(geofence: GeofenceArea, user_id: str = Query(..., description="User to check")):
    """Check if a user's latest position is within a geofence area"""
    try:
        sq = SpatialQueries()
        
        # Get user's latest position
        cursor = sq.conn.cursor()
        cursor.execute("""
            SELECT ST_Y(geom) as lat, ST_X(geom) as lon, timestamp
            FROM user_locations
            WHERE user_id = %s
            ORDER BY timestamp DESC
            LIMIT 1;
        """, (user_id,))
        
        result = cursor.fetchone()
        if not result:
            cursor.close()
            sq.close()
            raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")
        
        user_lat, user_lon, timestamp = result
        
        # Calculate distance from geofence center
        cursor.execute("""
            SELECT ST_Distance(
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
            ) as distance;
        """, (user_lon, user_lat, geofence.center_lon, geofence.center_lat))
        
        distance = cursor.fetchone()[0]
        is_inside = distance <= geofence.radius_meters
        
        cursor.close()
        sq.close()
        
        return success_response({
            "user_id": user_id,
            "geofence": {
                "name": geofence.name,
                "center": {"latitude": geofence.center_lat, "longitude": geofence.center_lon},
                "radius_meters": geofence.radius_meters
            },
            "user_position": {
                "latitude": round(user_lat, 6),
                "longitude": round(user_lon, 6),
                "timestamp": timestamp.isoformat()
            },
            "is_inside": is_inside,
            "distance_from_center_meters": round(distance, 2)
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking geofence: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to check geofence", str(e)))

# ==================== ANALYTICS ENDPOINTS ====================

@app.get("/api/v1/stats", tags=["Analytics"])
def get_system_statistics():
    """Get comprehensive system statistics"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        # Total points
        cursor.execute("SELECT COUNT(*) FROM user_locations;")
        total_points = cursor.fetchone()[0]
        
        # Unique users
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM user_locations;")
        total_users = cursor.fetchone()[0]
        
        # Date range
        cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM user_locations;")
        date_range = cursor.fetchone()
        
        # Last sync
        cursor.execute("""
            SELECT sync_time, records_synced, status 
            FROM sync_logs 
            ORDER BY sync_time DESC 
            LIMIT 1;
        """)
        last_sync = cursor.fetchone()
        
        # Average points per user
        avg_points = total_points / total_users if total_users > 0 else 0
        
        cursor.close()
        sq.close()
        
        return success_response({
            "overview": {
                "total_gps_points": total_points,
                "total_users": total_users,
                "average_points_per_user": round(avg_points, 1)
            },
            "date_range": {
                "earliest": date_range[0].isoformat() if date_range[0] else None,
                "latest": date_range[1].isoformat() if date_range[1] else None
            },
            "last_sync": {
                "time": last_sync[0].isoformat() if last_sync and last_sync[0] else None,
                "records": last_sync[1] if last_sync else 0,
                "status": last_sync[2] if last_sync else None
            }
        })
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to fetch statistics", str(e)))

@app.get("/api/v1/analytics/heatmap", tags=["Analytics"])
def get_heatmap_data(
    min_lat: float = Query(..., ge=-90, le=90),
    max_lat: float = Query(..., ge=-90, le=90),
    min_lon: float = Query(..., ge=-180, le=180),
    max_lon: float = Query(..., ge=-180, le=180)
):
    """Get location density data for heatmap visualization"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        cursor.execute("""
            SELECT 
                ST_Y(geom) as latitude,
                ST_X(geom) as longitude,
                COUNT(*) as density
            FROM user_locations
            WHERE ST_Within(
                geom,
                ST_MakeEnvelope(%s, %s, %s, %s, 4326)
            )
            GROUP BY ST_Y(geom), ST_X(geom)
            ORDER BY density DESC
            LIMIT 1000;
        """, (min_lon, min_lat, max_lon, max_lat))
        
        heatmap_points = []
        for row in cursor.fetchall():
            heatmap_points.append({
                "latitude": round(row[0], 6),
                "longitude": round(row[1], 6),
                "density": row[2]
            })
        
        cursor.close()
        sq.close()
        
        return success_response({
            "bounds": {
                "min_lat": min_lat,
                "max_lat": max_lat,
                "min_lon": min_lon,
                "max_lon": max_lon
            },
            "points": heatmap_points,
            "total_points": len(heatmap_points)
        })
    except Exception as e:
        logger.error(f"Error generating heatmap data: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to generate heatmap", str(e)))

@app.get("/api/v1/analytics/active-users", tags=["Analytics"])
def get_active_users(
    hours: int = Query(24, ge=1, le=168, description="Time window in hours (max 1 week)")
):
    """Get list of users active within the specified time window"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        cursor.execute("""
            SELECT 
                user_id,
                COUNT(*) as points,
                MAX(timestamp) as last_activity
            FROM user_locations
            WHERE timestamp >= %s
            GROUP BY user_id
            ORDER BY last_activity DESC;
        """, (cutoff_time,))
        
        active_users = []
        for row in cursor.fetchall():
            active_users.append({
                "user_id": row[0],
                "points_in_period": row[1],
                "last_activity": row[2].isoformat()
            })
        
        cursor.close()
        sq.close()
        
        return success_response({
            "time_window_hours": hours,
            "cutoff_time": cutoff_time.isoformat(),
            "active_users_count": len(active_users),
            "users": active_users
        })
    except Exception as e:
        logger.error(f"Error fetching active users: {e}")
        raise HTTPException(status_code=500, detail=error_response("Failed to fetch active users", str(e)))

@app.get("/api/v1/database/status", tags=["Health"])
def check_database_status():
    """Check PostgreSQL and PostGIS database status"""
    try:
        sq = SpatialQueries()
        cursor = sq.conn.cursor()
        
        # PostgreSQL version
        cursor.execute("SELECT version();")
        pg_version = cursor.fetchone()[0]
        
        # PostGIS version
        cursor.execute("SELECT PostGIS_Version();")
        postgis_version = cursor.fetchone()[0]
        
        # Table stats
        cursor.execute("SELECT COUNT(*) FROM user_locations;")
        total_records = cursor.fetchone()[0]
        
        # Database size
        cursor.execute("""
            SELECT pg_size_pretty(pg_database_size(current_database()));
        """)
        db_size = cursor.fetchone()[0]
        
        cursor.close()
        sq.close()
        
        return success_response({
            "status": "connected",
            "postgresql_version": pg_version.split(',')[0],
            "postgis_version": postgis_version,
            "database_size": db_size,
            "total_records": total_records
        })
    except Exception as e:
        logger.error(f"Database status check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=error_response("Database connection failed", str(e))
        )

# ==================== STARTUP ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🌍 GPS Tracker API - Enhanced Version")
    print("=" * 60)
    print(f"📍 API Server: http://localhost:8000")
    print(f"📖 Documentation: http://localhost:8000/docs")
    print(f"📊 ReDoc: http://localhost:8000/redoc")
    print(f"❤️  Health Check: http://localhost:8000/health")
    print("=" * 60)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )