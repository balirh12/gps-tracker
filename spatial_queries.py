"""
Spatial Queries Module
Demonstrates various PostGIS spatial queries for GPS tracking application.
"""

import psycopg2
from psycopg2 import sql
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime, timedelta
import config

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SpatialQueries:
    """
    Collection of spatial query methods using PostGIS functions.
    """
    
    def __init__(self, db_config: dict = None):
        """
        Initialize with database configuration.
        
        Args:
            db_config: PostgreSQL connection parameters
        """
        self.db_config = db_config or config.DB_CONFIG
        self.conn = None
        self._connect()
    
    def _connect(self):
        """
        Establish connection to PostgreSQL.
        """
        try:
            self.conn = psycopg2.connect(
                host=self.db_config['host'],
                database=self.db_config['database'],
                user=self.db_config['user'],
                password=self.db_config['password'],
                port=self.db_config['port']
            )
            logger.info("Connected to PostgreSQL for spatial queries")
        except psycopg2.Error as e:
            logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise
    
    def distance_between_users(self, user_id1: str, user_id2: str, 
                               use_latest: bool = True) -> Optional[float]:
        """
        Calculate the distance between two users' latest (or average) locations.
        Uses ST_Distance with geography type for accurate distances in meters.
        
        Args:
            user_id1: First user ID
            user_id2: Second user ID
            use_latest: If True, use latest positions; if False, use average position
            
        Returns:
            Distance in meters, or None if calculation fails
        """
        try:
            cursor = self.conn.cursor()
            
            if use_latest:
                # Get distance between latest positions
                query = """
                    WITH latest_positions AS (
                        SELECT DISTINCT ON (user_id)
                            user_id,
                            geom
                        FROM user_locations
                        WHERE user_id IN (%s, %s)
                        ORDER BY user_id, timestamp DESC
                    )
                    SELECT 
                        ST_Distance(
                            ST_Transform(p1.geom, 4326)::geography,
                            ST_Transform(p2.geom, 4326)::geography
                        ) as distance_meters
                    FROM 
                        (SELECT geom FROM latest_positions WHERE user_id = %s) p1,
                        (SELECT geom FROM latest_positions WHERE user_id = %s) p2;
                """
                cursor.execute(query, (user_id1, user_id2, user_id1, user_id2))
            else:
                # Get distance between average positions (centroid)
                query = """
                    SELECT 
                        ST_Distance(
                            ST_Centroid(ST_Collect(p1.geom))::geography,
                            ST_Centroid(ST_Collect(p2.geom))::geography
                        ) as distance_meters
                    FROM 
                        (SELECT geom FROM user_locations WHERE user_id = %s) p1,
                        (SELECT geom FROM user_locations WHERE user_id = %s) p2;
                """
                cursor.execute(query, (user_id1, user_id2))
            
            result = cursor.fetchone()
            distance = result[0] if result else None
            
            cursor.close()
            
            if distance is not None:
                logger.info(f"Distance between {user_id1} and {user_id2}: {distance:.2f} meters")
            
            return distance
            
        except psycopg2.Error as e:
            logger.error(f"Error calculating distance: {e}")
            return None
    
    def locations_within_radius(self, center_lat: float, center_lon: float, 
                                radius_meters: float, user_id: str = None) -> List[Dict]:
        """
        Find all locations within a specified radius of a point.
        
        Args:
            center_lat: Latitude of center point
            center_lon: Longitude of center point
            radius_meters: Search radius in meters
            user_id: Optional filter by specific user
            
        Returns:
            List of dictionaries with location information
        """
        try:
            cursor = self.conn.cursor()
            
            # Base query
            query = """
                SELECT 
                    id,
                    user_id,
                    ST_Y(geom) as latitude,
                    ST_X(geom) as longitude,
                    timestamp,
                    ST_Distance(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) as distance_meters
                FROM user_locations
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                )
            """
            
            params = [center_lon, center_lat, center_lon, center_lat, radius_meters]
            
            # Add user filter if specified
            if user_id:
                query += " AND user_id = %s"
                params.append(user_id)
            
            query += " ORDER BY distance_meters ASC"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            locations = []
            for row in results:
                locations.append({
                    'id': row[0],
                    'user_id': row[1],
                    'latitude': row[2],
                    'longitude': row[3],
                    'timestamp': row[4],
                    'distance_meters': row[5]
                })
            
            cursor.close()
            
            logger.info(f"Found {len(locations)} locations within {radius_meters}m "
                       f"of ({center_lat}, {center_lon})")
            
            return locations
            
        except psycopg2.Error as e:
            logger.error(f"Error finding locations within radius: {e}")
            return []
    
    def nearest_users(self, target_lat: float, target_lon: float, 
                     limit: int = 5) -> List[Dict]:
        """
        Find the nearest users to a target location.
        Uses each user's most recent position.
        
        Args:
            target_lat: Target latitude
            target_lon: Target longitude
            limit: Maximum number of users to return
            
        Returns:
            List of nearest users with their distances
        """
        try:
            cursor = self.conn.cursor()
            
            query = """
                WITH latest_positions AS (
                    SELECT DISTINCT ON (user_id)
                        user_id,
                        geom,
                        timestamp
                    FROM user_locations
                    ORDER BY user_id, timestamp DESC
                )
                SELECT 
                    user_id,
                    ST_Y(geom) as latitude,
                    ST_X(geom) as longitude,
                    timestamp,
                    ST_Distance(
                        geom::geography,
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                    ) as distance_meters
                FROM latest_positions
                ORDER BY distance_meters ASC
                LIMIT %s;
            """
            
            cursor.execute(query, (target_lon, target_lat, limit))
            results = cursor.fetchall()
            
            users = []
            for row in results:
                users.append({
                    'user_id': row[0],
                    'latitude': row[1],
                    'longitude': row[2],
                    'timestamp': row[3],
                    'distance_meters': row[4]
                })
            
            cursor.close()
            
            logger.info(f"Found {len(users)} nearest users to ({target_lat}, {target_lon})")
            
            return users
            
        except psycopg2.Error as e:
            logger.error(f"Error finding nearest users: {e}")
            return []
    
    def user_trajectory_length(self, user_id: str, 
                              start_time: datetime = None, 
                              end_time: datetime = None) -> Optional[float]:
        """
        Calculate the total distance traveled by a user along their trajectory.
        Uses ST_MakeLine to create a line string and ST_Length for distance.
        
        Args:
            user_id: User identifier
            start_time: Optional start time filter
            end_time: Optional end time filter
            
        Returns:
            Total distance in meters, or None if calculation fails
        """
        try:
            cursor = self.conn.cursor()
            
            # Build query with optional time filters
            query = """
                SELECT 
                    ST_Length(
                        ST_MakeLine(geom ORDER BY timestamp)::geography
                    ) as total_distance_meters
                FROM user_locations
                WHERE user_id = %s
            """
            
            params = [user_id]
            
            if start_time:
                query += " AND timestamp >= %s"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= %s"
                params.append(end_time)
            
            cursor.execute(query, params)
            result = cursor.fetchone()
            distance = result[0] if result else None
            
            cursor.close()
            
            if distance is not None:
                logger.info(f"User {user_id} traveled {distance:.2f} meters")
            
            return distance
            
        except psycopg2.Error as e:
            logger.error(f"Error calculating trajectory length: {e}")
            return None
    
    def users_in_bounding_box(self, min_lat: float, min_lon: float,
                             max_lat: float, max_lon: float) -> List[Dict]:
        """
        Find all users who have been within a bounding box area.
        
        Args:
            min_lat: Minimum latitude
            min_lon: Minimum longitude
            max_lat: Maximum latitude
            max_lon: Maximum longitude
            
        Returns:
            List of users with their location counts in the area
        """
        try:
            cursor = self.conn.cursor()
            
            query = """
                SELECT 
                    user_id,
                    COUNT(*) as location_count,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM user_locations
                WHERE ST_Within(
                    geom,
                    ST_MakeEnvelope(%s, %s, %s, %s, 4326)
                )
                GROUP BY user_id
                ORDER BY location_count DESC;
            """
            
            cursor.execute(query, (min_lon, min_lat, max_lon, max_lat))
            results = cursor.fetchall()
            
            users = []
            for row in results:
                users.append({
                    'user_id': row[0],
                    'location_count': row[1],
                    'first_seen': row[2],
                    'last_seen': row[3]
                })
            
            cursor.close()
            
            logger.info(f"Found {len(users)} users in bounding box")
            
            return users
            
        except psycopg2.Error as e:
            logger.error(f"Error finding users in bounding box: {e}")
            return []
    
    def cluster_locations(self, distance_meters: float = 50) -> List[Dict]:
        """
        Group nearby locations into clusters using ST_ClusterDBSCAN.
        Useful for identifying frequently visited areas.
        
        Args:
            distance_meters: Maximum distance between points in a cluster
            
        Returns:
            List of clusters with their properties
        """
        try:
            cursor = self.conn.cursor()
            
            query = """
                WITH clustered AS (
                    SELECT 
                        user_id,
                        geom,
                        timestamp,
                        ST_ClusterDBSCAN(geom::geography, eps := %s, minpoints := 3) 
                            OVER (PARTITION BY user_id) as cluster_id
                    FROM user_locations
                )
                SELECT 
                    user_id,
                    cluster_id,
                    COUNT(*) as point_count,
                    ST_Y(ST_Centroid(ST_Collect(geom))) as center_lat,
                    ST_X(ST_Centroid(ST_Collect(geom))) as center_lon,
                    MIN(timestamp) as first_visit,
                    MAX(timestamp) as last_visit
                FROM clustered
                WHERE cluster_id IS NOT NULL
                GROUP BY user_id, cluster_id
                ORDER BY user_id, point_count DESC;
            """
            
            cursor.execute(query, (distance_meters,))
            results = cursor.fetchall()
            
            clusters = []
            for row in results:
                clusters.append({
                    'user_id': row[0],
                    'cluster_id': row[1],
                    'point_count': row[2],
                    'center_lat': row[3],
                    'center_lon': row[4],
                    'first_visit': row[5],
                    'last_visit': row[6]
                })
            
            cursor.close()
            
            logger.info(f"Identified {len(clusters)} location clusters")
            
            return clusters
            
        except psycopg2.Error as e:
            logger.error(f"Error clustering locations: {e}")
            return []
    
    def close(self):
        """
        Close database connection.
        """
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """
    Demo: Run various spatial queries.
    """
    print("=== Spatial Query Examples ===\n")
    
    sq = SpatialQueries()
    
    try:
        # 1. Distance between two users
        print("1. Distance Between Users")
        print("-" * 50)
        distance = sq.distance_between_users("user_1", "user_2")
        if distance:
            print(f"Distance between user_1 and user_2: {distance:.2f} meters")
            print(f"That's approximately {distance/1000:.2f} kilometers")
        print()
        
        # 2. Find locations within radius
        print("2. Locations Within Radius")
        print("-" * 50)
        # Use center of simulation area
        center_lat = (config.SIMULATION_AREA['lat_min'] + 
                     config.SIMULATION_AREA['lat_max']) / 2
        center_lon = (config.SIMULATION_AREA['lon_min'] + 
                     config.SIMULATION_AREA['lon_max']) / 2
        
        locations = sq.locations_within_radius(center_lat, center_lon, 200)
        print(f"Found {len(locations)} locations within 200m of center")
        if locations:
            print(f"Closest location: {locations[0]['distance_meters']:.2f}m away")
        print()
        
        # 3. Nearest users
        print("3. Nearest Users to a Point")
        print("-" * 50)
        nearest = sq.nearest_users(center_lat, center_lon, limit=3)
        for i, user in enumerate(nearest, 1):
            print(f"{i}. {user['user_id']}: {user['distance_meters']:.2f}m away")
        print()
        
        # 4. User trajectory length
        print("4. User Trajectory Length")
        print("-" * 50)
        for i in range(1, config.SIMULATION_USERS + 1):
            user_id = f"user_{i}"
            distance = sq.user_trajectory_length(user_id)
            if distance:
                print(f"{user_id} traveled: {distance:.2f} meters "
                      f"({distance/1000:.2f} km)")
        print()
        
        # 5. Users in bounding box
        print("5. Users in Bounding Box")
        print("-" * 50)
        users = sq.users_in_bounding_box(
            config.SIMULATION_AREA['lat_min'],
            config.SIMULATION_AREA['lon_min'],
            config.SIMULATION_AREA['lat_max'],
            config.SIMULATION_AREA['lon_max']
        )
        for user in users:
            print(f"{user['user_id']}: {user['location_count']} locations")
        print()
        
        # 6. Location clusters
        print("6. Location Clusters (Frequently Visited Areas)")
        print("-" * 50)
        clusters = sq.cluster_locations(distance_meters=50)
        if clusters:
            for cluster in clusters[:5]:  # Show top 5
                print(f"{cluster['user_id']} - Cluster {cluster['cluster_id']}: "
                      f"{cluster['point_count']} points at "
                      f"({cluster['center_lat']:.6f}, {cluster['center_lon']:.6f})")
        else:
            print("No significant clusters found (need more data or closer points)")
    
    finally:
        sq.close()


if __name__ == "__main__":
    main()
