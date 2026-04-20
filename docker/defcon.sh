#!/run/current-system/sw/bin/bash
# ARGOS DEFCON Monitor
# Runs on both Beasty and Hermes
# Checks every 30 seconds

HA_URL="https://11.11.11.201:8123"
HA_TOKEN="${HA_TOKEN:-}"
ARGOS_URL="http://11.11.11.111:666"
BEASTY_IP="11.11.11.111"
HERMES_IP="11.11.11.98"
THIS_NODE=$(cat /etc/hostname 2>/dev/null || hostname)
LOG_FILE="/tmp/defcon.log"
DEFCON_FILE="/tmp/defcon_level"
OLLAMA_CONTAINER="argos-ollama"
DB_CONTAINER="argos-db"
REGISTRY_CONTAINER="argos-registry"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"; }

notify_ha() {
    local title="$1"
    local message="$2"
    local level="$3"
    curl -sk -X POST \
        -H "Authorization: Bearer $HA_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"title\":\"ARGOS $level: $title\",\"message\":\"$message\",\"data\":{\"tag\":\"argos_defcon\",\"importance\":\"high\"}}" \
        "$HA_URL/api/services/notify/mobile_app_s24ultra" > /dev/null 2>&1
}

get_defcon() { cat "$DEFCON_FILE" 2>/dev/null || echo "5"; }
set_defcon() { echo "$1" > "$DEFCON_FILE"; }

check_container() {
    docker inspect "$1" --format='{{.State.Status}}' 2>/dev/null | grep -q "running"
}

restart_container() {
    local name="$1"
    log "Restarting container: $name"
    docker restart "$name" 2>/dev/null
    sleep 5
    check_container "$name"
}

check_argos_health() {
    curl -sf --max-time 5 "http://11.11.11.111:666/health" > /dev/null 2>&1
}

check_db_health() {
    docker exec "$DB_CONTAINER" pg_isready -U claude -d claudedb -q 2>/dev/null
}

check_other_node() {
    local other_ip
    if [ "$THIS_NODE" = "Beasty" ]; then
        other_ip="$HERMES_IP"
    else
        other_ip="$BEASTY_IP"
    fi
    ping -c 2 -W 3 "$other_ip" > /dev/null 2>&1
}

analyze_container_failure() {
    local name="$1"
    local logs
    logs=$(docker logs "$name" --tail 20 2>&1)
    echo "$logs"
}

defcon5() {
    # All OK
    local prev
    prev=$(get_defcon)
    if [ "$prev" != "5" ]; then
        log "DEFCON 5: System nominal"
        notify_ha "System recovered" "All systems nominal. Previous level: $prev" "D5"
        set_defcon 5
    fi
}

defcon4() {
    local container="$1"
    local prev
    prev=$(get_defcon)
    log "DEFCON 4: Container $container down — attempting restart"
    set_defcon 4

    local analysis
    analysis=$(analyze_container_failure "$container")

    if restart_container "$container"; then
        log "DEFCON 4: $container restarted OK"
        notify_ha "Container recovered" "$container restarted successfully" "D4"
    else
        log "DEFCON 4: $container restart failed — escalating to DEFCON 3"
        defcon3_container "$container" "$analysis"
    fi
}

defcon3_container() {
    local container="$1"
    local analysis="$2"
    set_defcon 3
    log "DEFCON 3: Container $container failed to restart"

    # Try to identify cause
    local cause="Unknown"
    if echo "$analysis" | grep -qi "no space left"; then
        cause="Disk full"
    elif echo "$analysis" | grep -qi "out of memory\|oom"; then
        cause="Out of memory"
    elif echo "$analysis" | grep -qi "permission denied"; then
        cause="Permission error"
    elif echo "$analysis" | grep -qi "port.*already\|bind.*failed"; then
        cause="Port conflict"
    fi

    local disk_info
    disk_info=$(df -h / | tail -1 | awk '{print $5}')
    local mem_info
    mem_info=$(free -h | grep Mem | awk '{print $3"/"$2}')

    local message="Container: $container
Cause: $cause
Disk: $disk_info used
RAM: $mem_info
Log tail: $(echo "$analysis" | tail -3 | tr '\n' '|')"

    notify_ha "Container DOWN - action needed" "$message" "D3"
    log "DEFCON 3: $message"
}

defcon3_db() {
    set_defcon 3
    log "DEFCON 3: DB inaccessible"

    # Try restart DB container
    if [ "$THIS_NODE" = "Beasty" ]; then
        log "Attempting DB container restart"
        if restart_container "$DB_CONTAINER"; then
            sleep 3
            if check_db_health; then
                log "DB recovered after restart"
                notify_ha "DB recovered" "PostgreSQL container restarted OK" "D3"
                set_defcon 4
                return
            fi
        fi
        # Try restore from backup
        log "DB restart failed — checking backup"
        local latest_backup
        latest_backup=$(ls -t ~/.argos/backups/db/*.sql.gz 2>/dev/null | head -1)
        if [ -n "$latest_backup" ]; then
            notify_ha "DB DOWN - restore available" "Latest backup: $(basename $latest_backup). Reply 'restore' to confirm." "D3"
        else
            notify_ha "DB DOWN - no backup found" "Manual intervention required" "D3"
        fi
    fi
}

defcon2() {
    set_defcon 2
    local other_node
    if [ "$THIS_NODE" = "Beasty" ]; then
        other_node="Hermes ($HERMES_IP)"
    else
        other_node="Beasty ($BEASTY_IP)"
    fi

    log "DEFCON 2: $other_node not responding"

    # Try to get more info via alternative paths
    local ping_result="TIMEOUT"
    local ssh_result="FAILED"

    if ping -c 1 -W 2 "${HERMES_IP:-$BEASTY_IP}" > /dev/null 2>&1; then
        ping_result="OK"
    fi

    # Check if Swarm still working
    local swarm_status="UNKNOWN"
    if command -v docker > /dev/null 2>&1; then
        if docker node ls > /dev/null 2>&1; then
            swarm_status="OK - this node is manager"
        else
            swarm_status="NO MANAGER ACCESS"
        fi
    fi

    local message="Node $other_node unreachable
Ping: $ping_result
Swarm: $swarm_status
This node ($THIS_NODE) continues serving
Argos health: $(check_argos_health && echo OK || echo FAIL)"

    notify_ha "Node unreachable" "$message" "D2"
    log "DEFCON 2: $message"

    # If this is Beasty and Hermes (leader) is dead, promote self
    if [ "$THIS_NODE" = "Beasty" ] && ! check_other_node; then
        log "DEFCON 2: Hermes leader down — checking if Swarm needs recovery"
        if ! docker service ls > /dev/null 2>&1; then
            log "DEFCON 2: No Swarm manager available — initiating force-new-cluster"
            notify_ha "Swarm recovery initiated" "Beasty promoting to manager. Argos will restart." "D2"
            docker swarm init --force-new-cluster --advertise-addr "$BEASTY_IP" 2>/dev/null
            sleep 5
            docker stack deploy -c ~/.argos/docker/swarm-stack.yml argos-swarm 2>/dev/null
        fi
    fi
}

defcon1() {
    set_defcon 1
    log "DEFCON 1: CRITICAL — multiple failures"
    notify_ha "CRITICAL - Multiple failures" "Both nodes may be affected. DB may be corrupt. Immediate attention required." "D1"
}

# Main monitoring loop
log "DEFCON Monitor starting on $THIS_NODE"

CONTAINER_FAIL_COUNT=0
DB_FAIL_COUNT=0
NODE_FAIL_COUNT=0

while true; do
    # Check containers (only on Beasty where they run)
    if [ "$THIS_NODE" = "Beasty" ]; then
        for container in "$DB_CONTAINER" "$REGISTRY_CONTAINER"; do
            if ! check_container "$container"; then
                CONTAINER_FAIL_COUNT=$((CONTAINER_FAIL_COUNT + 1))
                if [ $CONTAINER_FAIL_COUNT -ge 2 ]; then
                    defcon4 "$container"
                    CONTAINER_FAIL_COUNT=0
                fi
            else
                CONTAINER_FAIL_COUNT=0
            fi
        done

        # Check Ollama (standalone container)
        if ! check_container "$OLLAMA_CONTAINER"; then
            log "Ollama container down — restarting"
            docker restart "$OLLAMA_CONTAINER" 2>/dev/null
            sleep 5
            if check_container "$OLLAMA_CONTAINER"; then
                log "Ollama restarted OK"
                notify_ha "Ollama recovered" "GPU container restarted OK" "D4"
            else
                notify_ha "Ollama DOWN" "GPU container failed to restart. Fallback to Grok/Claude active." "D3"
            fi
        fi

        # Check DB health
        if ! check_db_health; then
            DB_FAIL_COUNT=$((DB_FAIL_COUNT + 1))
            if [ $DB_FAIL_COUNT -ge 2 ]; then
                defcon3_db
                DB_FAIL_COUNT=0
            fi
        else
            DB_FAIL_COUNT=0
        fi
    fi

    # Check Argos health
    if ! check_argos_health; then
        log "Argos health check failed"
    fi

    # Check other node
    if ! check_other_node; then
        NODE_FAIL_COUNT=$((NODE_FAIL_COUNT + 1))
        if [ $NODE_FAIL_COUNT -ge 3 ]; then
            defcon2
            NODE_FAIL_COUNT=0
        fi
    else
        NODE_FAIL_COUNT=0
        # If we were in DEFCON 2, recover
        if [ "$(get_defcon)" = "2" ]; then
            defcon5
        fi
    fi

    # All good
    if [ "$(get_defcon)" = "4" ] && check_argos_health && check_db_health 2>/dev/null; then
        defcon5
    fi

    sleep 30
done
