-- ==============================================================================
-- ResumeMatch PostgreSQL Initialization Script
-- Executed ONLY when the database cluster is first created (empty data volume).
-- Does NOT execute on existing database volumes and will NEVER overwrite data.
-- ==============================================================================

-- Enable UUID generation extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pgvector extension for dense vector similarity search
CREATE EXTENSION IF NOT EXISTS "vector";
