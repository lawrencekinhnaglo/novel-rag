#!/bin/bash
# Restore script for Novel RAG databases
# Run from the novel-rag directory

set -e

echo "=== Novel RAG Database Restore ==="
echo "Make sure all containers are running first: docker compose up -d"
echo ""

# Restore PostgreSQL
echo "Restoring PostgreSQL..."
docker exec -i novel-rag-postgres psql -U novelrag -d novel_rag_db < backups/postgres_backup.sql
echo "✅ PostgreSQL restored"

# Restore Redis
echo "Restoring Redis..."
docker cp backups/redis_backup.rdb novel-rag-redis:/data/dump.rdb
docker exec novel-rag-redis redis-cli SHUTDOWN NOSAVE || true
sleep 3
docker compose restart redis
echo "✅ Redis restored"

# Restore Qdrant
echo "Restoring Qdrant..."
# First, copy snapshot to container
docker cp backups/qdrant_backup.snapshot novel-rag-qdrant:/qdrant/snapshots/
# Then restore from snapshot (this restores all collections)
curl -X POST "http://localhost:6333/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/qdrant/snapshots/qdrant_backup.snapshot"}'
echo ""
echo "✅ Qdrant restored"

# Neo4j (if not empty)
if [ -s backups/neo4j_backup.cypher ] && ! grep -q "empty" backups/neo4j_backup.cypher; then
  echo "Restoring Neo4j..."
  cat backups/neo4j_backup.cypher | docker exec -i novel-rag-neo4j cypher-shell -u neo4j -p novelrag_neo4j
  echo "✅ Neo4j restored"
else
  echo "⏭️  Neo4j backup is empty, skipping"
fi

echo ""
echo "=== Restore Complete ==="

