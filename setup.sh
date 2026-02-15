#!/bin/bash
# Quick Start Script for GPS Tracker Project
# This script helps set up the PostgreSQL database

echo "=========================================="
echo "GPS Tracker Setup Script"
echo "=========================================="
echo ""

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "❌ PostgreSQL is not installed!"
    echo ""
    echo "Install PostgreSQL:"
    echo "  Ubuntu/Debian: sudo apt-get install postgresql postgresql-contrib postgis"
    echo "  macOS: brew install postgresql postgis"
    exit 1
fi

echo "✓ PostgreSQL found"

# Check if PostGIS is available
echo "Checking PostGIS availability..."

# Database name
DB_NAME="gps_tracker"
DB_USER="postgres"

# Create database
echo ""
echo "Creating database '$DB_NAME'..."
sudo -u postgres psql -c "CREATE DATABASE $DB_NAME;" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ Database created"
else
    echo "ℹ Database already exists or could not create"
fi

# Enable PostGIS extension
echo ""
echo "Enabling PostGIS extension..."
sudo -u postgres psql -d $DB_NAME -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✓ PostGIS enabled"
else
    echo "❌ Could not enable PostGIS"
    exit 1
fi

# Run database setup script
echo ""
echo "Setting up database schema..."
sudo -u postgres psql -d $DB_NAME -f database_setup.sql
if [ $? -eq 0 ]; then
    echo "✓ Database schema created"
else
    echo "❌ Could not create schema"
    exit 1
fi

# Install Python dependencies
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt
if [ $? -eq 0 ]; then
    echo "✓ Python packages installed"
else
    echo "❌ Could not install Python packages"
    exit 1
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Edit config.py and set your PostgreSQL password"
echo "2. Run the demo: python main.py"
echo ""
echo "Individual components:"
echo "  • Collect data: python offline_collector.py"
echo "  • Sync data: python sync_service.py"
echo "  • Run queries: python spatial_queries.py"
echo ""
