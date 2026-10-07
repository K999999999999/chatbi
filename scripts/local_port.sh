local_loopback_port_is_free() {
    local port="${1:-}"
    [[ "$port" =~ ^[0-9]{1,5}$ ]] || return 2
    (( 10#$port >= 1 && 10#$port <= 65535 )) || return 2

    if timeout 1 bash -c 'exec 3<>/dev/tcp/127.0.0.1/$1' _ "$port" \
        >/dev/null 2>&1; then
        return 1
    fi
    return 0
}

local_loopback_http_health_ok() {
    local port="${1:-}" status_line
    [[ "$port" =~ ^[0-9]{1,5}$ ]] || return 1
    (( 10#$port >= 1 && 10#$port <= 65535 )) || return 1

    status_line="$(timeout 4 bash -c '
        exec 3<>/dev/tcp/127.0.0.1/$1 || exit 1
        printf "GET /health HTTP/1.1\r\nHost: 127.0.0.1:%s\r\nConnection: close\r\n\r\n" "$1" >&3
        IFS= read -r -t 2 status_line <&3 || exit 1
        printf "%s" "$status_line"
    ' _ "$port" 2>/dev/null || true)"
    [[ "$status_line" =~ ^HTTP/1\.[01][[:space:]]+200([[:space:]]|$) ]]
}
