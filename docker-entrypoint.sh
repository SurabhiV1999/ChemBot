#!/bin/bash
set -e

echo "ChemBot Backend Starting..."

# Wait for MongoDB to be ready
echo "Waiting for MongoDB to be ready..."
until curl -s mongodb:27017 > /dev/null 2>&1; do
  echo "MongoDB is unavailable - sleeping"
  sleep 2
done
echo "MongoDB is ready!"

# Wait for Redis to be ready
echo "Waiting for Redis to be ready..."
until redis-cli -h redis ping > /dev/null 2>&1; do
  echo "Redis is unavailable - sleeping"
  sleep 2
done
echo "Redis is ready!"

# Run database initialization (creates indexes and sample users)
echo "Initializing database..."
python -m src.backend.init_db

echo "Starting application..."
exec "$@"