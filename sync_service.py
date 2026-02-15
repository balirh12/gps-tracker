"""
Sync Service
Synchronizes offline GPS data from SQLite to PostgreSQL with PostGIS.
Includes batch processing, error handling, and retry logic.
"""

import psycopg2
from psycopg2 import sql, extras
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
import time
from typing import List, Tuple
from datetime import datetime
import config
from offline_collector import OfflineGPSCollector

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


class SyncService:
    """
    Handles synchronization of GPS data from local SQLite to PostgreSQL/PostGIS.
    """
    
    def __init__(self, db_config: dict = None):
        """
        Initialize the sync service with database configuration.
        
        Args:
            db_config: Dictionary with PostgreSQL connection parameters
        """
        self.db_config = db_config or config.DB_CONFIG
        self.conn = None
        logger.info("Sync Service initialized")
    
    def connect_to_postgres(self, retry: int = 3) -> bool:
        """
        Establish connection to PostgreSQL database with retry logic.
        
        Args:
            retry: Number of connection attempts
            
        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(1, retry + 1):
            try:
                logger.info(f"Attempting to connect to PostgreSQL (attempt {attempt}/{retry})...")
                
                self.conn = psycopg2.connect(
                    host=self.db_config['host'],
                    database=self.db_config['database'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    port=self.db_config['port']
                )
                
                # Test connection
                cursor = self.conn.cursor()
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]
                logger.info(f"Successfully connected to PostgreSQL: {version}")
                
                # Check PostGIS extension
                cursor.execute("SELECT PostGIS_Version();")
                postgis_version = cursor.fetchone()[0]
                logger.info(f"PostGIS version: {postgis_version}")
                
                cursor.close()
                return True
                
            except psycopg2.Error as e:
                logger.error(f"Connection attempt {attempt} failed: {e}")
                
                if attempt < retry:
                    wait_time = config.RETRY_DELAY * attempt
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error("All connection attempts failed")
                    return False
        
        return False
    
    def batch_insert_locations(self, locations: List[Tuple]) -> Tuple[int, List[int]]:
        """
        Insert multiple GPS locations into PostgreSQL using batch processing.
        Uses PostGIS ST_SetSRID and ST_MakePoint for geometry creation.
        
        Args:
            locations: List of tuples (id, user_id, latitude, longitude, timestamp)
            
        Returns:
            Tuple of (number of successful inserts, list of successfully inserted IDs)
        """
        if not locations:
            logger.warning("No locations to insert")
            return 0, []
        
        if not self.conn:
            logger.error("No database connection available")
            return 0, []
        
        try:
            cursor = self.conn.cursor()
            
            # Prepare data for batch insert
            # Format: [(user_id, longitude, latitude, timestamp), ...]
            insert_data = [
                (
                    loc[1],  # user_id
                    loc[3],  # longitude (X coordinate)
                    loc[2],  # latitude (Y coordinate)
                    loc[4]   # timestamp
                )
                for loc in locations
            ]
            
            # Use execute_values for efficient batch insert
            # ST_SetSRID(ST_MakePoint(lon, lat), 4326) creates PostGIS geometry
            insert_query = """
                INSERT INTO user_locations (user_id, geom, timestamp)
                VALUES %s
            """
            
            # Template for each row - creates PostGIS POINT geometry with SRID 4326
            template = "(%(user_id)s, ST_SetSRID(ST_MakePoint(%(lon)s, %(lat)s), 4326), %(timestamp)s)"
            
            # Convert to list of dicts for named parameters
            named_data = [
                {
                    'user_id': row[0],
                    'lon': row[1],
                    'lat': row[2],
                    'timestamp': row[3]
                }
                for row in insert_data
            ]
            
            # Execute batch insert
            extras.execute_values(
                cursor, 
                insert_query, 
                named_data,
                template=template,
                page_size=config.BATCH_SIZE
            )
            
            # Commit transaction
            self.conn.commit()
            
            # Get IDs of successfully inserted locations
            inserted_ids = [loc[0] for loc in locations]
            
            logger.info(f"Successfully inserted {len(locations)} locations")
            
            # Log to sync_logs table
            self._log_sync(len(locations), 'success')
            
            cursor.close()
            return len(locations), inserted_ids
            
        except psycopg2.Error as e:
            logger.error(f"Error during batch insert: {e}")
            self.conn.rollback()
            self._log_sync(0, 'failed', str(e))
            return 0, []
    
    def sync_offline_data(self, batch_size: int = None) -> dict:
        """
        Main synchronization method - reads from SQLite and syncs to PostgreSQL.
        
        Args:
            batch_size: Number of records to process per batch
            
        Returns:
            Dictionary with sync statistics
        """
        batch_size = batch_size or config.BATCH_SIZE
        
        logger.info("Starting offline data synchronization...")
        
        stats = {
            'total_processed': 0,
            'successful': 0,
            'failed': 0,
            'batches': 0
        }
        
        # Initialize offline collector to read data
        collector = OfflineGPSCollector()
        
        try:
            # Connect to PostgreSQL
            if not self.connect_to_postgres():
                logger.error("Failed to connect to PostgreSQL - aborting sync")
                stats['failed'] = collector.get_stats()['unsynced']
                return stats
            
            # Process data in batches
            while True:
                # Get next batch of unsynced locations
                unsynced = collector.get_unsynced_locations(limit=batch_size)
                
                if not unsynced:
                    logger.info("No more data to sync")
                    break
                
                stats['batches'] += 1
                stats['total_processed'] += len(unsynced)
                
                logger.info(f"Processing batch {stats['batches']} ({len(unsynced)} records)...")
                
                # Insert batch into PostgreSQL
                inserted_count, inserted_ids = self.batch_insert_locations(unsynced)
                
                if inserted_count > 0:
                    stats['successful'] += inserted_count
                    
                    # Mark as synced in SQLite
                    collector.mark_as_synced(inserted_ids)
                    logger.info(f"Batch {stats['batches']} completed successfully")
                else:
                    stats['failed'] += len(unsynced)
                    logger.error(f"Batch {stats['batches']} failed")
                    break  # Stop on error
                
                # Small delay between batches to avoid overwhelming the server
                time.sleep(0.1)
            
            logger.info("Synchronization completed")
            logger.info(f"Total processed: {stats['total_processed']}, "
                       f"Successful: {stats['successful']}, "
                       f"Failed: {stats['failed']}")
            
        except Exception as e:
            logger.error(f"Unexpected error during sync: {e}")
            stats['failed'] = stats['total_processed'] - stats['successful']
        
        finally:
            collector.close()
            self.close()
        
        return stats
    
    def _log_sync(self, records_synced: int, status: str, error_message: str = None):
        """
        Log sync attempt to sync_logs table.
        
        Args:
            records_synced: Number of records synced
            status: 'success', 'partial', or 'failed'
            error_message: Error description if applicable
        """
        if not self.conn:
            return
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT INTO sync_logs (records_synced, status, error_message)
                VALUES (%s, %s, %s)
            """, (records_synced, status, error_message))
            self.conn.commit()
            cursor.close()
        except psycopg2.Error as e:
            logger.error(f"Failed to log sync: {e}")
    
    def verify_sync(self) -> dict:
        """
        Verify data integrity after sync by comparing counts.
        
        Returns:
            Dictionary with verification results
        """
        if not self.conn:
            logger.error("No database connection")
            return {'verified': False}
        
        try:
            cursor = self.conn.cursor()
            
            # Count total records in PostgreSQL
            cursor.execute("SELECT COUNT(*) FROM user_locations")
            pg_count = cursor.fetchone()[0]
            
            # Count by user
            cursor.execute("""
                SELECT user_id, COUNT(*) 
                FROM user_locations 
                GROUP BY user_id 
                ORDER BY user_id
            """)
            user_counts = cursor.fetchall()
            
            cursor.close()
            
            results = {
                'verified': True,
                'total_in_postgres': pg_count,
                'by_user': {user_id: count for user_id, count in user_counts}
            }
            
            logger.info(f"Verification: {pg_count} total records in PostgreSQL")
            for user_id, count in user_counts:
                logger.info(f"  {user_id}: {count} records")
            
            return results
            
        except psycopg2.Error as e:
            logger.error(f"Error during verification: {e}")
            return {'verified': False, 'error': str(e)}
    
    def close(self):
        """
        Close database connection.
        """
        if self.conn:
            self.conn.close()
            logger.info("PostgreSQL connection closed")


def main():
    """
    Demo: Sync offline data to PostgreSQL.
    """
    print("=== GPS Data Synchronization ===\n")
    
    # Initialize sync service
    sync_service = SyncService()
    
    try:
        # Perform synchronization
        stats = sync_service.sync_offline_data()
        
        print(f"\n=== Sync Statistics ===")
        print(f"Batches processed: {stats['batches']}")
        print(f"Total records: {stats['total_processed']}")
        print(f"Successfully synced: {stats['successful']}")
        print(f"Failed: {stats['failed']}")
        
        # Verify sync
        if stats['successful'] > 0:
            print(f"\n=== Verification ===")
            verification = sync_service.verify_sync()
            if verification['verified']:
                print(f"✓ Verification successful")
                print(f"Total in PostgreSQL: {verification['total_in_postgres']}")
                print(f"By user:")
                for user_id, count in verification['by_user'].items():
                    print(f"  {user_id}: {count} records")
    
    finally:
        sync_service.close()


if __name__ == "__main__":
    main()
