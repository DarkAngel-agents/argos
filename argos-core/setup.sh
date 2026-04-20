#!/bin/bash
# ARGOS Setup Script v4.5
# Usage: bash setup.sh
# Reads: ~/.argos/config/argos-setup.yaml

set -e

ARGOS_DIR="$HOME/.argos"
CONFIG_FILE="$ARGOS_DIR/config/argos-setup.yaml"
PRIVATE_FILE="$ARGOS_DIR/config/argos-private.yaml"
CORE_DIR="$ARGOS_DIR/argos-core"
ENV_FILE="$CORE_DIR/config/.env"

echo "╔══════════════════════════════════════╗"
echo "║         ARGOS Setup v4.5             ║"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── CHECK CONFIG FILE ───────────────────────────────────────────────────────
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: $CONFIG_FILE not found"
    echo "Copy argos-setup.yaml.example to ~/.argos/config/argos-setup.yaml and fill in your details"
    exit 1
fi

get_val() { grep "^$1:" "$CONFIG_FILE" 2>/dev/null | sed 's/^[^:]*: *//' | tr -d '"' | sed 's/ *#.*//'; }

USERNAME=$(get_val username)
LANGUAGE=$(get_val language)
CLAUDE_TOKEN=$(get_val claude_token)
GROK_TOKEN=$(get_val grok_token)
DB_PASSWORD=$(get_val db_password)
HOSTNAME_VAL=$(get_val hostname)
HA_URL=$(get_val ha_url)
HA_TOKEN=$(get_val ha_token)
GITHUB_TOKEN=$(get_val github_token)
GITHUB_REPO=$(get_val github_repo)

ERRORS=0
[ -z "$USERNAME" ] || [ "$USERNAME" = "your_linux_username" ] && echo "ERROR: username is required" && ERRORS=1
[ -z "$CLAUDE_TOKEN" ] || [ "$CLAUDE_TOKEN" = "sk-ant-..." ] && echo "ERROR: claude_token is required" && ERRORS=1
[ -z "$DB_PASSWORD" ] || [ "$DB_PASSWORD" = "choose_a_strong_password" ] && echo "ERROR: db_password is required" && ERRORS=1
[ -z "$HOSTNAME_VAL" ] || [ "$HOSTNAME_VAL" = "your_hostname" ] && echo "ERROR: hostname is required" && ERRORS=1
[ $ERRORS -ne 0 ] && exit 1

echo "✓ Config loaded for user: $USERNAME"
echo ""

# ─── CHECK DOCKER ─────────────────────────────────────────────────────────────
echo "→ Checking Docker..."
if ! command -v docker &>/dev/null; then
    echo "ERROR: Docker not installed"
    echo "Install: https://docs.docker.com/engine/install/"
    exit 1
fi
if ! docker ps &>/dev/null; then
    echo "ERROR: Docker not running or no permissions"
    echo "Run: sudo systemctl start docker && sudo usermod -aG docker \$USER && newgrp docker"
    exit 1
fi
echo "✓ Docker OK"
echo ""

# ─── DETECT GPU / VRAM ────────────────────────────────────────────────────────
echo "→ Detecting GPU..."
VRAM_MB=0
OLLAMA_MODEL="qwen2.5:3b"
GPU_NOTE="CPU only — no NVIDIA GPU detected"

if command -v nvidia-smi &>/dev/null; then
    VRAM_MB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ' || echo 0)
    VRAM_GB=$((VRAM_MB / 1024))
    echo "✓ NVIDIA GPU detected: ${VRAM_MB}MB VRAM (${VRAM_GB}GB)"
    if [ $VRAM_GB -ge 10 ]; then
        OLLAMA_MODEL="qwen3:14b"
        GPU_NOTE="VRAM >= 10GB — full model"
    elif [ $VRAM_GB -ge 4 ]; then
        OLLAMA_MODEL="qwen2.5:7b"
        GPU_NOTE="VRAM < 10GB — reduced model (untested, may be slower)"
        echo "⚠ WARNING: $GPU_NOTE"
    else
        OLLAMA_MODEL="qwen2.5:3b"
        GPU_NOTE="VRAM < 4GB — minimal model (untested)"
        echo "⚠ WARNING: $GPU_NOTE"
    fi
else
    echo "  No NVIDIA GPU — Ollama will use CPU (slow)"
fi
echo "  Ollama model: $OLLAMA_MODEL"
echo ""

# ─── INIT DOCKER SWARM ────────────────────────────────────────────────────────
echo "→ Initializing Docker Swarm..."
if docker info 2>/dev/null | grep -q "Swarm: active"; then
    echo "✓ Swarm already active"
else
    MY_IP=$(hostname -I | awk '{print $1}')
    docker swarm init --advertise-addr "$MY_IP" 2>/dev/null
    echo "✓ Swarm initialized on $MY_IP"
fi
echo ""

# ─── START POSTGRESQL ─────────────────────────────────────────────────────────
echo "→ Starting PostgreSQL..."
docker volume create argos-db-data 2>/dev/null || true

if docker ps -a --format '{{.Names}}' | grep -q "^argos-db$"; then
    echo "  argos-db container exists — starting if stopped"
    docker start argos-db 2>/dev/null || true
else
    docker run -d --name argos-db --restart unless-stopped \
        -e POSTGRES_USER=claude \
        -e POSTGRES_PASSWORD="$DB_PASSWORD" \
        -e POSTGRES_DB=claudedb \
        -v argos-db-data:/var/lib/postgresql/data \
        -p 5432:5432 postgres:17
fi

echo "  Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    docker exec argos-db pg_isready -U claude -q 2>/dev/null && break
    sleep 2
done
echo "✓ PostgreSQL ready"
echo ""

# ─── CREATE DB SCHEMA ─────────────────────────────────────────────────────────
echo "→ Creating database schema..."
# [E001] Write SQL to temp file — heredoc with docker exec is unreliable
SQL_FILE="/tmp/argos_schema.sql"
cat > "$SQL_FILE" << 'SQLEOF'
CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE SEQUENCE IF NOT EXISTS conversations_id_seq START 2;
CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER DEFAULT nextval('conversations_id_seq'),
    project_id INTEGER,
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (id)
);
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(20),
    content TEXT,
    tokens_input INTEGER DEFAULT 0,
    tokens_output INTEGER DEFAULT 0,
    cost_eur NUMERIC DEFAULT 0,
    pending BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS segments (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    summary TEXT,
    message_start_id INTEGER,
    message_end_id INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER,
    title TEXT,
    status VARCHAR(20) DEFAULT 'pending',
    segments JSONB DEFAULT '[]',
    current_segment INTEGER DEFAULT 0,
    results JSONB DEFAULT '[]',
    error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS authorizations (
    id SERIAL PRIMARY KEY,
    job_id INTEGER,
    operation TEXT,
    details TEXT,
    risk_level VARCHAR(20),
    status VARCHAR(20) DEFAULT 'pending',
    requested_at TIMESTAMP DEFAULT NOW(),
    decided_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS skills (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    filename VARCHAR(200),
    os_type VARCHAR(100),
    version VARCHAR(50),
    keywords TEXT[],
    loaded_when TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS skills_tree (
    id BIGINT PRIMARY KEY,
    path VARCHAR(200) NOT NULL UNIQUE,
    parent_path VARCHAR(200),
    name VARCHAR(200) NOT NULL,
    tags TEXT[] DEFAULT '{}',
    source VARCHAR(10) DEFAULT 'manual',
    emergency BOOLEAN DEFAULT false,
    usage_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    content TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS autonomy_rules (
    id SERIAL PRIMARY KEY,
    level INTEGER,
    pattern VARCHAR(200),
    action VARCHAR(50),
    description TEXT
);
CREATE TABLE IF NOT EXISTS prompt_modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    category VARCHAR(100),
    display_name VARCHAR(200),
    content TEXT,
    keywords TEXT[] DEFAULT '{}',
    priority INTEGER DEFAULT 50,
    active BOOLEAN DEFAULT true,
    version INTEGER DEFAULT 1,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS system_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    display_name VARCHAR(200),
    owner VARCHAR(100),
    os_type VARCHAR(100),
    os_version VARCHAR(100),
    hostname VARCHAR(200),
    ip VARCHAR(50),
    cpu VARCHAR(200),
    ram_gb INTEGER,
    storage TEXT,
    gpu VARCHAR(200),
    location VARCHAR(200),
    role VARCHAR(100),
    purpose TEXT,
    prompt_modules TEXT[],
    notes TEXT,
    active BOOLEAN DEFAULT true,
    nanite_node_id VARCHAR(100),
    online BOOLEAN DEFAULT false,
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS system_credentials (
    id SERIAL PRIMARY KEY,
    system_id INTEGER,
    credential_type VARCHAR(50),
    label VARCHAR(100),
    username VARCHAR(100),
    value_hint VARCHAR(200),
    notes TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    category VARCHAR(100),
    key VARCHAR(200),
    value TEXT,
    source VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS tool_scores (
    id SERIAL PRIMARY KEY,
    tool_name VARCHAR(100),
    task_type VARCHAR(100),
    success_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    avg_duration_ms INTEGER,
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS debug_logs (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20),
    code VARCHAR(20),
    category VARCHAR(50),
    message TEXT,
    context JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS notes (
    id SERIAL PRIMARY KEY,
    category VARCHAR(50) DEFAULT 'general',
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    priority INTEGER DEFAULT 5,
    public BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    done_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS memories (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200),
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS log_entries (
    id SERIAL PRIMARY KEY,
    level VARCHAR(20),
    message TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS nanite_nodes (
    id VARCHAR(100) PRIMARY KEY,
    ip VARCHAR(50),
    status VARCHAR(50),
    announced_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS artifacts (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER,
    name VARCHAR(200),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS file_versions (
    id SERIAL PRIMARY KEY,
    path VARCHAR(500),
    content TEXT,
    version INTEGER DEFAULT 1,
    label VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS iso_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS iso_builds (
    id SERIAL PRIMARY KEY,
    type_id INTEGER,
    status VARCHAR(50),
    output_path VARCHAR(500),
    log TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS iso_test_results (
    id SERIAL PRIMARY KEY,
    build_id INTEGER,
    result TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS proxmox_servers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    ip VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS archive_tags (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    display_name VARCHAR(100),
    color VARCHAR(20),
    icon VARCHAR(10),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS conversation_archives (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER,
    title VARCHAR(200),
    summary TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS module_preferences (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL,
    modules TEXT[] NOT NULL,
    confirmed_by_user BOOLEAN DEFAULT false,
    times_used INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS system_modules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100),
    active BOOLEAN DEFAULT true,
    config JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS config_index (
    id SERIAL PRIMARY KEY,
    key VARCHAR(200),
    value TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Instant conversation (ID=1, pinned)
INSERT INTO conversations (id, title, created_at, updated_at)
VALUES (1, 'Instant', NOW(), NOW())
ON CONFLICT (id) DO UPDATE SET title='Instant';
SQLEOF
# [E002] Copy SQL to container and execute
docker cp "$SQL_FILE" argos-db:/tmp/argos_schema.sql
docker exec argos-db psql -U claude -d claudedb -f /tmp/argos_schema.sql 2>&1 | grep -E "ERROR|FATAL" && { echo "[E002] Schema creation failed"; exit 1; } || true
rm -f "$SQL_FILE"
# [E003] Verify schema
TABLE_COUNT=$(docker exec argos-db psql -U claude -d claudedb -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
[ "$TABLE_COUNT" -lt "10" ] && echo "[E003] Schema verification failed — only $TABLE_COUNT tables created" && exit 1
echo "✓ Schema created ($TABLE_COUNT tables)"
echo ""

# ─── POPULATE SETTINGS ────────────────────────────────────────────────────────
echo "→ Writing settings to database..."
docker exec argos-db psql -U claude -d claudedb -c "
INSERT INTO settings (key, value) VALUES
  ('autonomy_level', '1'),
  ('language', '$LANGUAGE'),
  ('username', '$USERNAME'),
  ('hostname', '$HOSTNAME_VAL'),
  ('claude_enabled', 'true'),
  ('grok_enabled', 'false'),
  ('local_enabled', 'false'),
  ('ollama_model', '$OLLAMA_MODEL'),
  ('setup_complete', 'true'),
  ('version', '4.5')
ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW();
"

# HA settings if provided
if [ -n "$HA_URL" ] && [ "$HA_URL" != "your-ha-ip" ]; then
    docker exec argos-db psql -U claude -d claudedb -c "
    INSERT INTO settings (key, value) VALUES ('ha_url', '$HA_URL'), ('ha_token', '$HA_TOKEN')
    ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=NOW();"
fi


echo "✓ Settings written"
echo ""

# ─── COPY PROMPT_MODULES — RUN ON BEASTY AFTER SETUP ─────────────────────────
echo "⚠ prompt_modules not copied automatically."
echo "  After setup completes, run these commands ON BEASTY:"
echo ""
echo "  docker exec argos-db psql -U claude -d claudedb -c \"COPY prompt_modules TO '/tmp/pm.csv' CSV HEADER;\""
echo "  docker cp argos-db:/tmp/pm.csv /tmp/pm.csv"
echo "  scp /tmp/pm.csv \${USERNAME}@\${MY_IP}:/tmp/pm.csv"
echo "  ssh \${USERNAME}@\${MY_IP} \"docker cp /tmp/pm.csv argos-db:/tmp/pm.csv && docker exec argos-db psql -U claude -d claudedb -c \\\"DELETE FROM prompt_modules; COPY prompt_modules FROM '/tmp/pm.csv' CSV HEADER;\\\"\"
"
echo ""

# ─── CREATE .ENV FILE ─────────────────────────────────────────────────────────
echo "→ Creating .env file..."
mkdir -p "$CORE_DIR/config"
cat > "$ENV_FILE" << ENVEOF
ANTHROPIC_API_KEY=$CLAUDE_TOKEN
GROK_API_KEY=${GROK_TOKEN:-}
DB_HOST=127.0.0.1
DB_PORT=5432
DB_USER=claude
DB_PASSWORD=$DB_PASSWORD
DB_NAME=claudedb
HA_URL=${HA_URL:-}
HA_TOKEN=${HA_TOKEN:-}
GITHUB_TOKEN=${GITHUB_TOKEN:-}
GITHUB_REPO=${GITHUB_REPO:-}
OLLAMA_URL=http://172.17.0.1:11435
ENVEOF
chmod 600 "$ENV_FILE"
echo "✓ .env created"
echo ""

# ─── START OLLAMA ─────────────────────────────────────────────────────────────
echo "→ Starting Ollama..."
if docker ps -a --format '{{.Names}}' | grep -q "^argos-ollama$"; then
    docker start argos-ollama 2>/dev/null || true
else
    if [ $VRAM_MB -gt 0 ]; then
        docker run -d --name argos-ollama --restart unless-stopped \
            --gpus all \
            -v ollama-data:/root/.ollama \
            -p 11435:11434 ollama/ollama
    else
        docker run -d --name argos-ollama --restart unless-stopped \
            -v ollama-data:/root/.ollama \
            -p 11435:11434 ollama/ollama
    fi
fi
echo "  Pulling model $OLLAMA_MODEL (this may take a while)..."
sleep 5
docker exec argos-ollama ollama pull "$OLLAMA_MODEL" 2>/dev/null && echo "✓ Ollama model ready" || echo "⚠ Ollama model pull failed — will retry on first use"
echo ""

# ─── LOCAL REGISTRY ───────────────────────────────────────────────────────────
echo "→ Starting local registry..."
MY_IP=$(hostname -I | awk '{print $1}')
if ! docker ps -a --format '{{.Names}}' | grep -q "^argos-registry$"; then
    docker run -d --name argos-registry --restart unless-stopped \
        -p 5000:5000 registry:2
fi
# Configure insecure registry
DAEMON_JSON="/etc/docker/daemon.json"
if ! grep -q "$MY_IP:5000" "$DAEMON_JSON" 2>/dev/null; then
    echo "  Configuring insecure registry $MY_IP:5000..."
    sudo bash -c "echo '{\"insecure-registries\":[\"'$MY_IP':5000\"]}' > $DAEMON_JSON"
    sudo systemctl restart docker
    sleep 5
fi
echo "✓ Registry ready at $MY_IP:5000"
echo ""

# ─── BUILD AND DEPLOY ARGOS ───────────────────────────────────────────────────
echo "→ Building ARGOS image..."
cd "$ARGOS_DIR"
docker build -t argos:latest -f docker/Dockerfile . 2>&1 | tail -5
docker tag argos:latest "$MY_IP:5000/argos:latest"
docker push "$MY_IP:5000/argos:latest"
echo "✓ Image built and pushed"
echo ""

echo "→ Deploying ARGOS stack..."
mkdir -p "$ARGOS_DIR/backups/db"
mkdir -p "$HOME/.ssh" && chmod 700 "$HOME/.ssh"
# Replace placeholders in swarm-stack.yml
STACK_FILE="$ARGOS_DIR/docker/swarm-stack.yml"
sed "s|11.11.11.111:5000|$MY_IP:5000|g; s|11.11.11.111|$MY_IP|g" "$STACK_FILE" > /tmp/argos-stack.yml
docker stack deploy -c /tmp/argos-stack.yml argos-swarm
echo "  Waiting for ARGOS to start..."
sleep 20

# [E010] Check prompt_modules — critical for ARGOS to function
PM_COUNT=$(docker exec argos-db psql -U claude -d claudedb -t -c "SELECT COUNT(*) FROM prompt_modules;" 2>/dev/null | tr -d ' ')
if [ "${PM_COUNT:-0}" -eq 0 ]; then
    echo "⚠ prompt_modules empty — ARGOS will not function correctly"
    echo "  Run on source node: docker exec argos-db psql -U claude -d claudedb -c \"\COPY prompt_modules TO '/tmp/pm.csv' CSV HEADER;\""
    echo "  Then: scp source:/tmp/pm.csv /tmp/pm.csv && docker cp /tmp/pm.csv argos-db:/tmp/pm.csv"
    echo "  Then: docker exec argos-db psql -U claude -d claudedb -c \"\COPY prompt_modules FROM '/tmp/pm.csv' CSV HEADER;\""
else
    echo "✓ prompt_modules: $PM_COUNT entries"
fi

if curl -sf "http://127.0.0.1:666/health" &>/dev/null; then
    echo "✓ ARGOS running at http://$MY_IP:666"
else
    echo "⚠ ARGOS not responding yet — check: docker stack ps argos-swarm"
fi
echo ""

# ─── SAVE PRIVATE CONFIG AND CLEANUP ─────────────────────────────────────────
echo "→ Saving private config backup..."
cp "$CONFIG_FILE" "$PRIVATE_FILE"
chmod 600 "$PRIVATE_FILE"
rm -f "$CONFIG_FILE"
echo "✓ Private config saved to $PRIVATE_FILE"
echo "✓ Setup file deleted"
echo ""

echo "╔══════════════════════════════════════╗"
echo "║         ARGOS Setup Complete!        ║"
echo "╚══════════════════════════════════════╝"
echo ""
echo "  Web UI:    http://$MY_IP:666"
echo "  Node:      $HOSTNAME_VAL"
echo "  User:      $USERNAME"
echo "  Language:  $LANGUAGE"
echo "  Ollama:    $OLLAMA_MODEL"
[ -n "$GPU_NOTE" ] && echo "  GPU:       $GPU_NOTE"
echo ""
echo "  Private config: $PRIVATE_FILE"
echo "  Logs: docker stack ps argos-swarm"
echo ""

# ─── AUTOSTART SYSTEMD SERVICE ────────────────────────────────────────────────
echo "→ Creating ARGOS autostart service..."
MY_IP=$(hostname -I | awk '{print $1}')
sudo bash -c "cat > /etc/systemd/system/argos-autostart.service << SVCEOF
[Unit]
Description=ARGOS Docker Swarm Autostart
After=docker.service network-online.target
Wants=docker.service network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/bash -c 'MY_IP=\$(hostname -I | awk \"{print \\\$1}\") && sed \"s|11.11.11.111:5000|\$MY_IP:5000|g; s|11.11.11.111|\$MY_IP|g\" /home/$USERNAME/.argos/docker/swarm-stack.yml > /tmp/argos-stack.yml && docker stack deploy -c /tmp/argos-stack.yml argos-swarm'
User=root

[Install]
WantedBy=multi-user.target
SVCEOF"
sudo systemctl daemon-reload
sudo systemctl enable argos-autostart
echo "✓ ARGOS autostart enabled"
