#!/bin/bash

echo "Setting up PostgreSQL test database..."

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "PostgreSQL is not running. Please start PostgreSQL first:"
    echo "  macOS: brew services start postgresql"
    echo "  Linux: sudo systemctl start postgresql"
    exit 1
fi

# Create database and user as postgres superuser
echo "Creating database and user..."
psql -h localhost -p 5432 -U postgres -c "CREATE DATABASE testdb;" 2>/dev/null || echo "Database testdb already exists"
psql -h localhost -p 5432 -U postgres -c "CREATE USER testuser WITH PASSWORD 'testpass';" 2>/dev/null || echo "User testuser already exists"
psql -h localhost -p 5432 -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE testdb TO testuser;"

# Run the setup script
echo "Creating tables and inserting test data..."
psql -h localhost -p 5432 -U postgres -d testdb -f setup_test_db.sql

echo "Test database setup complete!"
echo ""
echo "You can now test queries like:"
echo "  - 'show me all users'"
echo "  - 'list all products'"
echo "  - 'show me pending orders'"
echo "  - 'how many users do we have?'"