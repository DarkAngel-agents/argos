-- Argos DB Schema
-- Generat 2026-03-25

CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(20),
    content TEXT,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_eur FLOAT DEFAULT 0,
    pending BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    title TEXT,
    steps JSONB,
    target VARCHAR(100),
    risk_level VARCHAR(20),
    status VARCHAR(30) DEFAULT 'pending_approval',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS authorizations (
    id SERIAL PRIMARY KEY,
    job_id INTEGER REFERENCES jobs(id),
    approved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS file_versions (
    id SERIAL PRIMARY KEY,
    module_name VARCHAR(200),
    version_type VARCHAR(20),
    content TEXT,
    hash VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS prompt_modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE,
    content TEXT,
    keywords TEXT[],
    priority INTEGER DEFAULT 10
);

CREATE TABLE IF NOT EXISTS system_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    hostname VARCHAR(100),
    os_type VARCHAR(50),
    location VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_credentials (
    id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES system_profiles(id),
    credential_type VARCHAR(30) NOT NULL,
    label VARCHAR(100) NOT NULL,
    username VARCHAR(100),
    value_hint VARCHAR(50),
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    category VARCHAR(30) NOT NULL,
    os_type VARCHAR(30),
    os_version VARCHAR(30),
    command_type VARCHAR(30),
    action TEXT NOT NULL,
    outcome VARCHAR(10) NOT NULL,
    reason TEXT,
    skip BOOLEAN DEFAULT FALSE,
    skip_reason TEXT,
    success_rate FLOAT DEFAULT 1.0,
    times_tried INTEGER DEFAULT 1,
    last_tried_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(os_type, os_version, command_type, action)
);

CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    filename VARCHAR(200) NOT NULL,
    os_type VARCHAR(50),
    version VARCHAR(50),
    keywords TEXT[],
    loaded_when TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tool_scores (
    id SERIAL PRIMARY KEY,
    tool_name VARCHAR(50) NOT NULL,
    task_type VARCHAR(50) DEFAULT 'general',
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_duration_ms INTEGER DEFAULT 0,
    last_used TIMESTAMP DEFAULT NOW(),
    UNIQUE(tool_name, task_type)
);

CREATE TABLE IF NOT EXISTS autonomy_rules (
    id SERIAL PRIMARY KEY,
    level INTEGER NOT NULL,
    pattern VARCHAR(200) NOT NULL,
    action VARCHAR(20) NOT NULL,
    description TEXT,
    UNIQUE(level, pattern)
);

CREATE TABLE IF NOT EXISTS debug_logs (
    id SERIAL PRIMARY KEY,
    ts TIMESTAMP DEFAULT NOW(),
    level VARCHAR(10) NOT NULL,
    module VARCHAR(30) NOT NULL,
    code VARCHAR(10) NOT NULL,
    message TEXT NOT NULL,
    context JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS nanite_nodes (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(100),
    ip VARCHAR(50),
    hardware JSONB,
    announced_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS log_entries (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation_archives (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER,
    title TEXT,
    summary TEXT,
    archived_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ha_entities (
    id SERIAL PRIMARY KEY,
    entity_id VARCHAR(200),
    name TEXT,
    state TEXT,
    domain VARCHAR(50),
    attributes JSONB,
    last_seen TIMESTAMP DEFAULT NOW(),
    last_state TEXT
);

CREATE TABLE IF NOT EXISTS ha_automations (
    id SERIAL PRIMARY KEY,
    automation_id VARCHAR(200),
    alias TEXT,
    description TEXT,
    enabled BOOLEAN,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ha_devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(200),
    name TEXT,
    manufacturer TEXT,
    model TEXT,
    area TEXT,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ha_integrations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) UNIQUE,
    last_seen TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ha_scenes (
    id SERIAL PRIMARY KEY,
    scene_id VARCHAR(200),
    name TEXT,
    last_seen TIMESTAMP DEFAULT NOW()
);

-- Cristin schema
CREATE SCHEMA IF NOT EXISTS cristin;
CREATE TABLE IF NOT EXISTS cristin.devices (
    id SERIAL PRIMARY KEY,
    mac VARCHAR(20),
    ip VARCHAR(50),
    hostname TEXT,
    device_type VARCHAR(50),
    location TEXT,
    last_seen TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cristin.events (
    id SERIAL PRIMARY KEY,
    severity VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS cristin.network_snapshots (
    id SERIAL PRIMARY KEY,
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Grant
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO claude;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO claude;
GRANT ALL PRIVILEGES ON SCHEMA cristin TO claude;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cristin TO claude;
