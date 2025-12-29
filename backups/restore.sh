#!/bin/bash
# Restore script for Novel RAG databases
# Run from the novel-rag directory (where docker-compose.yml is located)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== Novel RAG Database Restore ==="
echo "Script directory: $SCRIPT_DIR"
echo "Project directory: $PROJECT_DIR"
echo ""

# Check if we're in the right directory
if [ ! -f "$PROJECT_DIR/docker-compose.yml" ]; then
    echo "❌ Error: docker-compose.yml not found in $PROJECT_DIR"
    echo "   Please run this script from the novel-rag directory"
    exit 1
fi

cd "$PROJECT_DIR"

# Check if containers are running
if ! docker compose ps | grep -q "novel-rag-postgres"; then
    echo "❌ Error: Containers not running. Start them first:"
    echo "   docker compose up -d"
    echo "   # Wait 30 seconds for services to be healthy"
    echo "   sleep 30"
    echo "   ./backups/restore.sh"
    exit 1
fi

echo "✅ Containers are running"
echo ""

# ============================================
# Restore PostgreSQL
# ============================================
echo "📦 Restoring PostgreSQL..."
echo "   (This will DROP and recreate all tables)"

# The backup uses --clean flag so it will DROP tables before CREATE
docker exec -i novel-rag-postgres psql -U novelrag -d novel_rag_db < "$SCRIPT_DIR/postgres_backup.sql" 2>&1 | grep -v "does not exist, skipping" || true

echo "✅ PostgreSQL restored"
echo ""

# ============================================
# Restore Redis
# ============================================
echo "📦 Restoring Redis..."

# Copy RDB file
docker cp "$SCRIPT_DIR/redis_backup.rdb" novel-rag-redis:/data/dump.rdb

# Restart Redis to load the RDB
docker compose restart redis
sleep 3

echo "✅ Redis restored"
echo ""

# ============================================
# Restore Qdrant
# ============================================
echo "📦 Restoring Qdrant..."

# Copy snapshot to container
docker cp "$SCRIPT_DIR/qdrant_backup.snapshot" novel-rag-qdrant:/qdrant/snapshots/

# Wait for Qdrant to be ready
sleep 2

# Recover from snapshot
QDRANT_RESPONSE=$(curl -s -X POST "http://localhost:6335/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/qdrant/snapshots/qdrant_backup.snapshot"}' 2>&1)

if echo "$QDRANT_RESPONSE" | grep -q '"status":"ok"'; then
    echo "✅ Qdrant restored"
else
    echo "⚠️  Qdrant restore response: $QDRANT_RESPONSE"
    echo "   You may need to restart Qdrant: docker compose restart qdrant"
fi
echo ""

# ============================================
# Restore Neo4j (if has data)
# ============================================
echo "📦 Checking Neo4j backup..."

if [ -s "$SCRIPT_DIR/neo4j_backup.cypher" ] && ! grep -q "Status: Empty" "$SCRIPT_DIR/neo4j_backup.cypher"; then
    echo "   Restoring Neo4j data..."
    # Filter out comments and empty lines
    grep -v "^--" "$SCRIPT_DIR/neo4j_backup.cypher" | grep -v "^$" | \
        docker exec -i novel-rag-neo4j cypher-shell -u neo4j -p novelrag_neo4j 2>&1 || true
    echo "✅ Neo4j restored"
else
    echo "⏭️  Neo4j backup is empty (no graph data yet), skipping"
fi
echo ""

# ============================================
# Verification
# ============================================
echo "=== Verifying Restore ==="

# Check PostgreSQL
PG_TABLES=$(docker exec novel-rag-postgres psql -U novelrag -d novel_rag_db -t -c "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
echo "📊 PostgreSQL tables: $PG_TABLES"

# Check Qdrant collections
QDRANT_COLLECTIONS=$(curl -s http://localhost:6335/collections | grep -o '"name":"[^"]*"' | wc -l | tr -d ' ')
echo "📊 Qdrant collections: $QDRANT_COLLECTIONS"

# Check Redis keys
REDIS_KEYS=$(docker exec novel-rag-redis redis-cli DBSIZE | awk '{print $2}')
echo "📊 Redis keys: $REDIS_KEYS"

echo ""
echo "=== Restore Complete ==="
echo ""
echo "You can now access the application at http://localhost:5173"
