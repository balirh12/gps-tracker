"""
Test Script
Verifies that all components are working correctly.
"""

import sys
import os
import sqlite3
import logging

# Suppress logging for tests
logging.basicConfig(level=logging.CRITICAL)


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...", end=" ")
    
    try:
        import psycopg2
        import config
        from offline_collector import OfflineGPSCollector
        from sync_service import SyncService
        from spatial_queries import SpatialQueries
        
        print("✓")
        return True
    except ImportError as e:
        print(f"✗\nError: {e}")
        return False


def test_config():
    """Test that configuration is valid."""
    print("Testing configuration...", end=" ")
    
    try:
        import config
        
        # Check required config values
        required = ['DB_CONFIG', 'SQLITE_DB_PATH', 'BATCH_SIZE']
        for key in required:
            if not hasattr(config, key):
                print(f"✗\nMissing config: {key}")
                return False
        
        # Check DB_CONFIG structure
        required_db_keys = ['host', 'database', 'user', 'password', 'port']
        for key in required_db_keys:
            if key not in config.DB_CONFIG:
                print(f"✗\nMissing DB_CONFIG key: {key}")
                return False
        
        print("✓")
        return True
    except Exception as e:
        print(f"✗\nError: {e}")
        return False


def test_sqlite_creation():
    """Test that SQLite database can be created."""
    print("Testing SQLite database...", end=" ")
    
    try:
        from offline_collector import OfflineGPSCollector
        
        # Create a test collector
        collector = OfflineGPSCollector('test_gps.db')
        
        # Verify table was created
        cursor = collector.conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='offline_locations'
        """)
        result = cursor.fetchone()
        
        collector.close()
        
        # Clean up
        if os.path.exists('test_gps.db'):
            os.remove('test_gps.db')
        
        if result:
            print("✓")
            return True
        else:
            print("✗\nTable not created")
            return False
            
    except Exception as e:
        print(f"✗\nError: {e}")
        return False


def test_gps_simulation():
    """Test GPS coordinate simulation."""
    print("Testing GPS simulation...", end=" ")
    
    try:
        from offline_collector import OfflineGPSCollector
        
        collector = OfflineGPSCollector('test_gps.db')
        
        # Simulate small dataset
        collector.simulate_gps_collection("test_user", 5)
        
        # Verify data was collected
        stats = collector.get_stats()
        
        collector.close()
        
        # Clean up
        if os.path.exists('test_gps.db'):
            os.remove('test_gps.db')
        
        if stats['total'] == 5:
            print("✓")
            return True
        else:
            print(f"✗\nExpected 5 points, got {stats['total']}")
            return False
            
    except Exception as e:
        print(f"✗\nError: {e}")
        if os.path.exists('test_gps.db'):
            os.remove('test_gps.db')
        return False


def test_postgresql_connection():
    """Test PostgreSQL connection."""
    print("Testing PostgreSQL connection...", end=" ")
    
    try:
        import psycopg2
        import config
        
        conn = psycopg2.connect(
            host=config.DB_CONFIG['host'],
            database=config.DB_CONFIG['database'],
            user=config.DB_CONFIG['user'],
            password=config.DB_CONFIG['password'],
            port=config.DB_CONFIG['port']
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        print("✓")
        return True
        
    except psycopg2.Error as e:
        print(f"✗\nError: {e}")
        print("\nPostgreSQL connection failed. Please check:")
        print("1. PostgreSQL is running")
        print("2. Database exists: CREATE DATABASE gps_tracker;")
        print("3. Credentials in config.py are correct")
        return False


def test_postgis_extension():
    """Test that PostGIS extension is enabled."""
    print("Testing PostGIS extension...", end=" ")
    
    try:
        import psycopg2
        import config
        
        conn = psycopg2.connect(
            host=config.DB_CONFIG['host'],
            database=config.DB_CONFIG['database'],
            user=config.DB_CONFIG['user'],
            password=config.DB_CONFIG['password'],
            port=config.DB_CONFIG['port']
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT PostGIS_Version();")
        version = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        print("✓")
        return True
        
    except psycopg2.Error as e:
        print(f"✗\nError: {e}")
        print("\nPostGIS extension not found. Enable it with:")
        print("  psql -U postgres -d gps_tracker -c 'CREATE EXTENSION postgis;'")
        return False


def test_table_schema():
    """Test that the user_locations table exists with correct schema."""
    print("Testing database schema...", end=" ")
    
    try:
        import psycopg2
        import config
        
        conn = psycopg2.connect(
            host=config.DB_CONFIG['host'],
            database=config.DB_CONFIG['database'],
            user=config.DB_CONFIG['user'],
            password=config.DB_CONFIG['password'],
            port=config.DB_CONFIG['port']
        )
        
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_locations'
            );
        """)
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            cursor.close()
            conn.close()
            print("✗\nTable 'user_locations' does not exist")
            print("Run: psql -U postgres -d gps_tracker -f database_setup.sql")
            return False
        
        # Check columns
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'user_locations';
        """)
        columns = [row[0] for row in cursor.fetchall()]
        
        required_columns = ['id', 'user_id', 'geom', 'timestamp']
        missing = [col for col in required_columns if col not in columns]
        
        cursor.close()
        conn.close()
        
        if missing:
            print(f"✗\nMissing columns: {', '.join(missing)}")
            return False
        
        print("✓")
        return True
        
    except psycopg2.Error as e:
        print(f"✗\nError: {e}")
        return False


def main():
    """
    Run all tests.
    """
    print("=" * 60)
    print("GPS Tracker - System Test")
    print("=" * 60)
    print()
    
    tests = [
        ("Module Imports", test_imports),
        ("Configuration", test_config),
        ("SQLite Database", test_sqlite_creation),
        ("GPS Simulation", test_gps_simulation),
        ("PostgreSQL Connection", test_postgresql_connection),
        ("PostGIS Extension", test_postgis_extension),
        ("Database Schema", test_table_schema),
    ]
    
    results = []
    
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"✗\nUnexpected error: {e}")
            results.append((name, False))
    
    # Summary
    print()
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print()
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! System is ready to use.")
        print("\nRun the demo:")
        print("  python main.py")
        return 0
    else:
        print(f"\n⚠ {total - passed} test(s) failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
