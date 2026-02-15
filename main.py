"""
Main Application
Orchestrates the complete GPS tracking workflow:
1. Simulate offline GPS collection
2. Sync data to PostgreSQL/PostGIS
3. Run spatial query examples
"""

import sys
import logging
from datetime import datetime
import config
from offline_collector import OfflineGPSCollector
from sync_service import SyncService
from spatial_queries import SpatialQueries

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


def print_separator(title: str = "", width: int = 60):
    """
    Print a formatted separator line.
    
    Args:
        title: Optional title to display
        width: Width of the separator
    """
    if title:
        print(f"\n{'=' * width}")
        print(f"{title.center(width)}")
        print(f"{'=' * width}\n")
    else:
        print(f"{'=' * width}\n")


def step_1_collect_offline_data():
    """
    Step 1: Simulate offline GPS data collection.
    """
    print_separator("STEP 1: OFFLINE GPS DATA COLLECTION")
    
    print(f"Simulating GPS collection for {config.SIMULATION_USERS} users...")
    print(f"Each user will have {config.SIMULATION_POINTS_PER_USER} GPS points collected")
    print(f"Data will be stored locally in SQLite: {config.SQLITE_DB_PATH}\n")
    
    collector = OfflineGPSCollector()
    
    try:
        # Simulate GPS collection for each user
        for i in range(1, config.SIMULATION_USERS + 1):
            user_id = f"user_{i}"
            print(f"Collecting data for {user_id}...", end=" ")
            
            collector.simulate_gps_collection(
                user_id,
                config.SIMULATION_POINTS_PER_USER
            )
            
            print("✓ Done")
        
        # Display collection statistics
        stats = collector.get_stats()
        print(f"\n✓ Collection Complete!")
        print(f"  Total locations: {stats['total']}")
        print(f"  Ready to sync: {stats['unsynced']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error during offline collection: {e}")
        print(f"✗ Error: {e}")
        return False
        
    finally:
        collector.close()


def step_2_sync_to_postgresql():
    """
    Step 2: Synchronize offline data to PostgreSQL/PostGIS.
    """
    print_separator("STEP 2: SYNC TO POSTGRESQL/POSTGIS")
    
    print("Connecting to PostgreSQL database...")
    print(f"Database: {config.DB_CONFIG['database']} @ {config.DB_CONFIG['host']}\n")
    
    sync_service = SyncService()
    
    try:
        # Perform synchronization
        print("Starting data synchronization...")
        stats = sync_service.sync_offline_data()
        
        # Display sync results
        if stats['successful'] > 0:
            print(f"\n✓ Synchronization Complete!")
            print(f"  Batches processed: {stats['batches']}")
            print(f"  Total records: {stats['total_processed']}")
            print(f"  Successfully synced: {stats['successful']}")
            
            if stats['failed'] > 0:
                print(f"  Failed: {stats['failed']}")
            
            # Verify data integrity
            print("\nVerifying data integrity...")
            verification = sync_service.verify_sync()
            
            if verification.get('verified'):
                print(f"✓ Verification successful!")
                print(f"  Total in PostgreSQL: {verification['total_in_postgres']}")
                print(f"  By user:")
                for user_id, count in verification['by_user'].items():
                    print(f"    {user_id}: {count} records")
            
            return True
        else:
            print(f"\n✗ Synchronization Failed!")
            print(f"  No records were synced")
            print(f"  Check logs for details: {config.LOG_FILE}")
            return False
            
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        print(f"\n✗ Error: {e}")
        return False
        
    finally:
        sync_service.close()


def step_3_run_spatial_queries():
    """
    Step 3: Demonstrate spatial queries using PostGIS.
    """
    print_separator("STEP 3: SPATIAL QUERY EXAMPLES")
    
    sq = SpatialQueries()
    
    try:
        # Calculate center point for queries
        center_lat = (config.SIMULATION_AREA['lat_min'] + 
                     config.SIMULATION_AREA['lat_max']) / 2
        center_lon = (config.SIMULATION_AREA['lon_min'] + 
                     config.SIMULATION_AREA['lon_max']) / 2
        
        # Query 1: Distance between users
        print("Query 1: Distance Between Two Users")
        print("-" * 50)
        distance = sq.distance_between_users("user_1", "user_2")
        if distance:
            print(f"Distance between user_1 and user_2: {distance:.2f} meters")
            print(f"That's {distance/1000:.3f} kilometers")
        else:
            print("Could not calculate distance (insufficient data)")
        print()
        
        # Query 2: Locations within radius
        print("Query 2: Locations Within 200m Radius")
        print("-" * 50)
        locations = sq.locations_within_radius(center_lat, center_lon, 200)
        print(f"Found {len(locations)} locations within 200 meters of center")
        if locations:
            print(f"Closest: {locations[0]['user_id']} at {locations[0]['distance_meters']:.2f}m")
            if len(locations) > 1:
                print(f"Farthest: {locations[-1]['user_id']} at {locations[-1]['distance_meters']:.2f}m")
        print()
        
        # Query 3: Nearest users
        print("Query 3: 3 Nearest Users to Center Point")
        print("-" * 50)
        nearest = sq.nearest_users(center_lat, center_lon, limit=3)
        for i, user in enumerate(nearest, 1):
            print(f"  {i}. {user['user_id']}: {user['distance_meters']:.2f}m away")
        print()
        
        # Query 4: Trajectory lengths
        print("Query 4: Total Distance Traveled by Each User")
        print("-" * 50)
        for i in range(1, config.SIMULATION_USERS + 1):
            user_id = f"user_{i}"
            distance = sq.user_trajectory_length(user_id)
            if distance:
                print(f"  {user_id}: {distance:.2f}m ({distance/1000:.3f}km)")
        print()
        
        # Query 5: Location clusters
        print("Query 5: Location Clusters (Frequently Visited Areas)")
        print("-" * 50)
        clusters = sq.cluster_locations(distance_meters=50)
        if clusters:
            print(f"Found {len(clusters)} clusters")
            # Show top 3 clusters by point count
            sorted_clusters = sorted(clusters, key=lambda x: x['point_count'], reverse=True)
            for i, cluster in enumerate(sorted_clusters[:3], 1):
                print(f"  {i}. {cluster['user_id']} - Cluster {cluster['cluster_id']}: "
                      f"{cluster['point_count']} points")
        else:
            print("No significant clusters found")
            print("(Clustering requires multiple close points)")
        
        return True
        
    except Exception as e:
        logger.error(f"Error running spatial queries: {e}")
        print(f"✗ Error: {e}")
        return False
        
    finally:
        sq.close()


def main():
    """
    Main application entry point.
    """
    print_separator("GPS TRACKER WITH OFFLINE SUPPORT", 70)
    
    start_time = datetime.now()
    
    print(f"Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {config.LOG_FILE}\n")
    
    # Track success of each step
    steps_completed = []
    
    # Step 1: Collect offline data
    if step_1_collect_offline_data():
        steps_completed.append("Collection")
        
        # Step 2: Sync to PostgreSQL
        if step_2_sync_to_postgresql():
            steps_completed.append("Synchronization")
            
            # Step 3: Run spatial queries
            if step_3_run_spatial_queries():
                steps_completed.append("Spatial Queries")
    
    # Summary
    print_separator("SUMMARY", 70)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    print(f"End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration: {duration:.2f} seconds\n")
    
    print("Completed steps:")
    for step in steps_completed:
        print(f"  ✓ {step}")
    
    if len(steps_completed) == 3:
        print(f"\n✓ All steps completed successfully!")
        print(f"\nNext steps:")
        print(f"  • Check logs: {config.LOG_FILE}")
        print(f"  • Query database: psql -U postgres -d {config.DB_CONFIG['database']}")
        print(f"  • Run individual modules:")
        print(f"    - python offline_collector.py")
        print(f"    - python sync_service.py")
        print(f"    - python spatial_queries.py")
    else:
        print(f"\n⚠ Some steps failed. Check logs for details: {config.LOG_FILE}")
        return 1
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        logger.info("Application interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        logger.exception("Unexpected error in main application")
        sys.exit(1)
