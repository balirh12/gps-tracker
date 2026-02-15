"""
Example Usage Patterns
Demonstrates common usage patterns for the GPS tracking system.
"""

from datetime import datetime, timedelta
from offline_collector import OfflineGPSCollector
from sync_service import SyncService
from spatial_queries import SpatialQueries
import config


def example_1_manual_gps_collection():
    """
    Example 1: Manually collect GPS coordinates (simulating a mobile app).
    """
    print("=== Example 1: Manual GPS Collection ===\n")
    
    collector = OfflineGPSCollector()
    
    try:
        # Collect a series of coordinates for a user
        user_id = "manual_user_001"
        
        # Simulate a user's journey with specific coordinates
        journey = [
            (33.5731, -7.5898, datetime.now()),  # Casablanca downtown
            (33.5751, -7.5918, datetime.now() + timedelta(minutes=5)),
            (33.5771, -7.5938, datetime.now() + timedelta(minutes=10)),
        ]
        
        for lat, lon, timestamp in journey:
            collector.collect_coordinate(user_id, lat, lon, timestamp)
            print(f"Collected: ({lat}, {lon}) at {timestamp}")
        
        print(f"\n✓ Collected {len(journey)} coordinates for {user_id}")
        
        # Check unsynced data
        unsynced = collector.get_unsynced_locations()
        print(f"Total unsynced locations: {len(unsynced)}")
        
    finally:
        collector.close()


def example_2_batch_sync_with_verification():
    """
    Example 2: Sync data with custom batch size and verification.
    """
    print("\n=== Example 2: Batch Sync with Verification ===\n")
    
    sync_service = SyncService()
    
    try:
        # Sync with smaller batch size
        print("Syncing with batch size of 50...")
        stats = sync_service.sync_offline_data(batch_size=50)
        
        print(f"\nSync Results:")
        print(f"  Batches: {stats['batches']}")
        print(f"  Total: {stats['total_processed']}")
        print(f"  Success: {stats['successful']}")
        print(f"  Failed: {stats['failed']}")
        
        # Verify the sync
        if stats['successful'] > 0:
            verification = sync_service.verify_sync()
            if verification['verified']:
                print(f"\n✓ Data verified successfully")
                print(f"  PostgreSQL count: {verification['total_in_postgres']}")
    
    finally:
        sync_service.close()


def example_3_find_nearby_users():
    """
    Example 3: Find users near a specific location.
    """
    print("\n=== Example 3: Find Nearby Users ===\n")
    
    sq = SpatialQueries()
    
    try:
        # Find users near a specific point (e.g., Hassan II Mosque)
        target_lat = 33.6084
        target_lon = -7.6324
        
        print(f"Finding users near ({target_lat}, {target_lon})...")
        
        nearest_users = sq.nearest_users(target_lat, target_lon, limit=5)
        
        if nearest_users:
            print(f"\nFound {len(nearest_users)} nearby users:")
            for i, user in enumerate(nearest_users, 1):
                distance_km = user['distance_meters'] / 1000
                print(f"{i}. {user['user_id']}: {distance_km:.2f} km away")
        else:
            print("No users found")
    
    finally:
        sq.close()


def example_4_analyze_user_movement():
    """
    Example 4: Analyze a specific user's movement patterns.
    """
    print("\n=== Example 4: Analyze User Movement ===\n")
    
    sq = SpatialQueries()
    
    try:
        user_id = "user_1"
        
        # Calculate total distance traveled
        print(f"Analyzing movement for {user_id}...")
        total_distance = sq.user_trajectory_length(user_id)
        
        if total_distance:
            print(f"\nMovement Statistics:")
            print(f"  Total distance: {total_distance:.2f} meters")
            print(f"  Total distance: {total_distance/1000:.2f} kilometers")
            
            # If we had time data, we could calculate average speed
            # This would require modifying the query to include time span
            print(f"\n  (To calculate speed, divide by time traveled)")
        
        # Find their clusters (favorite spots)
        print(f"\nFinding frequently visited areas...")
        clusters = sq.cluster_locations(distance_meters=50)
        
        user_clusters = [c for c in clusters if c['user_id'] == user_id]
        if user_clusters:
            print(f"Found {len(user_clusters)} frequently visited areas:")
            for cluster in user_clusters[:3]:  # Top 3
                print(f"  • Cluster {cluster['cluster_id']}: "
                      f"{cluster['point_count']} visits at "
                      f"({cluster['center_lat']:.6f}, {cluster['center_lon']:.6f})")
        else:
            print("No clusters found (user hasn't revisited areas)")
    
    finally:
        sq.close()


def example_5_radius_search():
    """
    Example 5: Find all locations within a radius of a point.
    """
    print("\n=== Example 5: Radius Search ===\n")
    
    sq = SpatialQueries()
    
    try:
        # Search around a specific point
        center_lat = 33.5731
        center_lon = -7.5898
        radius = 500  # meters
        
        print(f"Searching for locations within {radius}m of "
              f"({center_lat}, {center_lon})...")
        
        locations = sq.locations_within_radius(
            center_lat, center_lon, radius
        )
        
        if locations:
            print(f"\nFound {len(locations)} locations:")
            
            # Group by user
            users = {}
            for loc in locations:
                user = loc['user_id']
                if user not in users:
                    users[user] = 0
                users[user] += 1
            
            print(f"\nBy user:")
            for user, count in users.items():
                print(f"  {user}: {count} locations")
            
            # Show closest and farthest
            print(f"\nClosest: {locations[0]['distance_meters']:.2f}m "
                  f"({locations[0]['user_id']})")
            print(f"Farthest: {locations[-1]['distance_meters']:.2f}m "
                  f"({locations[-1]['user_id']})")
        else:
            print("No locations found in this radius")
    
    finally:
        sq.close()


def example_6_compare_user_distances():
    """
    Example 6: Compare distances between multiple user pairs.
    """
    print("\n=== Example 6: Compare User Distances ===\n")
    
    sq = SpatialQueries()
    
    try:
        users = ["user_1", "user_2", "user_3"]
        
        print("Distance matrix between users (in meters):\n")
        
        # Create distance matrix
        for i, user1 in enumerate(users):
            for user2 in users[i+1:]:
                distance = sq.distance_between_users(user1, user2)
                if distance:
                    print(f"{user1} ↔ {user2}: {distance:.2f}m "
                          f"({distance/1000:.3f}km)")
    
    finally:
        sq.close()


def example_7_bounding_box_query():
    """
    Example 7: Find users who have visited a specific area (bounding box).
    """
    print("\n=== Example 7: Bounding Box Query ===\n")
    
    sq = SpatialQueries()
    
    try:
        # Define area of interest (e.g., downtown Casablanca)
        min_lat = 33.57
        min_lon = -7.60
        max_lat = 33.58
        max_lon = -7.58
        
        print(f"Finding users who visited area:")
        print(f"  Lat: {min_lat} to {max_lat}")
        print(f"  Lon: {min_lon} to {max_lon}")
        
        users = sq.users_in_bounding_box(min_lat, min_lon, max_lat, max_lon)
        
        if users:
            print(f"\nFound {len(users)} users in this area:")
            for user in users:
                duration = user['last_seen'] - user['first_seen']
                print(f"\n{user['user_id']}:")
                print(f"  Visits: {user['location_count']}")
                print(f"  First seen: {user['first_seen']}")
                print(f"  Last seen: {user['last_seen']}")
                print(f"  Duration: {duration}")
        else:
            print("\nNo users found in this area")
    
    finally:
        sq.close()


def main():
    """
    Run all examples.
    """
    print("=" * 60)
    print("GPS Tracker - Usage Examples")
    print("=" * 60)
    
    examples = [
        ("Manual GPS Collection", example_1_manual_gps_collection),
        ("Batch Sync with Verification", example_2_batch_sync_with_verification),
        ("Find Nearby Users", example_3_find_nearby_users),
        ("Analyze User Movement", example_4_analyze_user_movement),
        ("Radius Search", example_5_radius_search),
        ("Compare User Distances", example_6_compare_user_distances),
        ("Bounding Box Query", example_7_bounding_box_query),
    ]
    
    print("\nAvailable examples:")
    for i, (name, _) in enumerate(examples, 1):
        print(f"  {i}. {name}")
    
    print("\nRun all examples? (y/n): ", end="")
    choice = input().strip().lower()
    
    if choice == 'y':
        for name, example_func in examples:
            try:
                example_func()
            except Exception as e:
                print(f"\n✗ Error in {name}: {e}\n")
    else:
        print("\nTo run a specific example, call it from the code:")
        print("  from examples import example_1_manual_gps_collection")
        print("  example_1_manual_gps_collection()")


if __name__ == "__main__":
    main()
