"""
Offline GPS Collector
Simulates a mobile app collecting GPS coordinates while offline.
Stores coordinates locally in SQLite database.
"""

import sqlite3
import random
import logging
from datetime import datetime, timedelta
from typing import List, Tuple
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


class OfflineGPSCollector:
    """
    Simulates offline GPS data collection and stores it locally in SQLite.
    """
    
    def __init__(self, db_path: str = config.SQLITE_DB_PATH):
        """
        Initialize the offline collector with SQLite database.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._init_database()
        logger.info(f"Offline GPS Collector initialized with database: {db_path}")
    
    def _init_database(self):
        """
        Create SQLite database and table if they don't exist.
        """
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Create table for storing GPS coordinates offline
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS offline_locations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    synced INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_offline_locations_synced 
                ON offline_locations(synced)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_offline_locations_user 
                ON offline_locations(user_id)
            ''')
            
            self.conn.commit()
            logger.info("SQLite database initialized successfully")
            
        except sqlite3.Error as e:
            logger.error(f"Error initializing SQLite database: {e}")
            raise
    
    def collect_coordinate(self, user_id: str, latitude: float, longitude: float, 
                          timestamp: datetime = None):
        """
        Store a single GPS coordinate in the local database.
        
        Args:
            user_id: Unique identifier for the user
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            timestamp: Time when coordinate was captured (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO offline_locations (user_id, latitude, longitude, timestamp, synced)
                VALUES (?, ?, ?, ?, 0)
            ''', (user_id, latitude, longitude, timestamp.isoformat()))
            
            self.conn.commit()
            logger.debug(f"Collected coordinate for user {user_id}: ({latitude}, {longitude})")
            
        except sqlite3.Error as e:
            logger.error(f"Error storing coordinate: {e}")
            raise
    
    def get_unsynced_locations(self, limit: int = None) -> List[Tuple]:
        """
        Retrieve all locations that haven't been synced yet.
        
        Args:
            limit: Maximum number of records to retrieve (None for all)
            
        Returns:
            List of tuples (id, user_id, latitude, longitude, timestamp)
        """
        try:
            cursor = self.conn.cursor()
            
            query = '''
                SELECT id, user_id, latitude, longitude, timestamp
                FROM offline_locations
                WHERE synced = 0
                ORDER BY timestamp ASC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query)
            locations = cursor.fetchall()
            
            logger.info(f"Retrieved {len(locations)} unsynced locations")
            return locations
            
        except sqlite3.Error as e:
            logger.error(f"Error retrieving unsynced locations: {e}")
            return []
    
    def mark_as_synced(self, location_ids: List[int]):
        """
        Mark locations as successfully synced.
        
        Args:
            location_ids: List of location IDs that were successfully synced
        """
        if not location_ids:
            return
        
        try:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' * len(location_ids))
            cursor.execute(f'''
                UPDATE offline_locations
                SET synced = 1
                WHERE id IN ({placeholders})
            ''', location_ids)
            
            self.conn.commit()
            logger.info(f"Marked {len(location_ids)} locations as synced")
            
        except sqlite3.Error as e:
            logger.error(f"Error marking locations as synced: {e}")
            raise
    
    def get_stats(self) -> dict:
        """
        Get statistics about stored locations.
        
        Returns:
            Dictionary with total, synced, and unsynced counts
        """
        try:
            cursor = self.conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM offline_locations')
            total = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM offline_locations WHERE synced = 1')
            synced = cursor.fetchone()[0]
            
            stats = {
                'total': total,
                'synced': synced,
                'unsynced': total - synced
            }
            
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"Error getting statistics: {e}")
            return {'total': 0, 'synced': 0, 'unsynced': 0}
    
    def simulate_gps_collection(self, user_id: str, num_points: int = 50):
        """
        Simulate GPS collection for a user moving around.
        Generates realistic-looking GPS coordinates with small variations.
        
        Args:
            user_id: User identifier
            num_points: Number of GPS points to generate
        """
        logger.info(f"Starting GPS simulation for user {user_id} ({num_points} points)")
        
        # Starting position (within configured area)
        lat = random.uniform(
            config.SIMULATION_AREA['lat_min'], 
            config.SIMULATION_AREA['lat_max']
        )
        lon = random.uniform(
            config.SIMULATION_AREA['lon_min'], 
            config.SIMULATION_AREA['lon_max']
        )
        
        # Start time (simulate data from the past hour)
        start_time = datetime.now() - timedelta(hours=1)
        
        for i in range(num_points):
            # Small random movement (simulates walking/driving)
            # ~0.0001 degrees ≈ 11 meters
            lat += random.uniform(-0.0003, 0.0003)
            lon += random.uniform(-0.0003, 0.0003)
            
            # Ensure coordinates stay within bounds
            lat = max(config.SIMULATION_AREA['lat_min'], 
                     min(config.SIMULATION_AREA['lat_max'], lat))
            lon = max(config.SIMULATION_AREA['lon_min'], 
                     min(config.SIMULATION_AREA['lon_max'], lon))
            
            # Timestamp increments (simulate collecting every ~1-2 minutes)
            timestamp = start_time + timedelta(seconds=i * random.randint(60, 120))
            
            self.collect_coordinate(user_id, lat, lon, timestamp)
        
        logger.info(f"Completed GPS simulation for user {user_id}")
    
    def clear_synced_data(self):
        """
        Remove synced locations from local database to save space.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute('DELETE FROM offline_locations WHERE synced = 1')
            deleted = cursor.rowcount
            self.conn.commit()
            logger.info(f"Cleared {deleted} synced locations from local storage")
            
        except sqlite3.Error as e:
            logger.error(f"Error clearing synced data: {e}")
    
    def close(self):
        """
        Close database connection.
        """
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """
    Demo: Simulate GPS collection for multiple users.
    """
    collector = OfflineGPSCollector()
    
    try:
        # Simulate GPS collection for multiple users
        for i in range(1, config.SIMULATION_USERS + 1):
            user_id = f"user_{i}"
            collector.simulate_gps_collection(
                user_id, 
                config.SIMULATION_POINTS_PER_USER
            )
        
        # Display statistics
        stats = collector.get_stats()
        print(f"\n=== Collection Statistics ===")
        print(f"Total locations collected: {stats['total']}")
        print(f"Unsynced locations: {stats['unsynced']}")
        print(f"Synced locations: {stats['synced']}")
        
        # Show sample of unsynced data
        print(f"\n=== Sample Unsynced Locations ===")
        unsynced = collector.get_unsynced_locations(limit=5)
        for loc in unsynced:
            print(f"ID: {loc[0]}, User: {loc[1]}, "
                  f"Lat: {loc[2]:.6f}, Lon: {loc[3]:.6f}, "
                  f"Time: {loc[4]}")
    
    finally:
        collector.close()


if __name__ == "__main__":
    main()
