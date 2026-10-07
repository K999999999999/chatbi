#!/usr/bin/env bash

select_build_cache_commit() {
    local source_commit="$1" repository="$2" image cache_commit revision candidate
    local has_explicit_cache_label=0 legacy_candidate=''
    local -A cached_cache_commits=() cached_legacy_revisions=()
    while IFS= read -r image; do
        [[ -n "$image" ]] || continue
        case "$image" in
            chatbi-local-api:*|chatbi-local-postgres:*) ;;
            *) continue ;;
        esac
        cache_commit="$(docker image inspect \
            --format '{{index .Config.Labels "com.chatbi.build-cache-commit"}}' \
            "$image" 2>/dev/null || true)"
        if [[ "$cache_commit" =~ ^[0-9a-f]{40}$ ]]; then
            has_explicit_cache_label=1
            cached_cache_commits["$cache_commit"]=1
            continue
        fi
        revision="$(docker image inspect \
            --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' \
            "$image" 2>/dev/null || true)"
        [[ "$revision" =~ ^[0-9a-f]{40}$ ]] || continue
        cached_legacy_revisions["$revision"]=1
    done < <(docker image ls --format '{{.Repository}}:{{.Tag}}')

    if (( has_explicit_cache_label )); then
        while IFS= read -r candidate; do
            if [[ -n "${cached_cache_commits[$candidate]:-}" ]]; then
                printf '%s\n' "$candidate"
                return 0
            fi
        done < <(git -C "$repository" rev-list "$source_commit")
        printf '%s\n' "$source_commit"
        return 0
    fi

    while IFS= read -r candidate; do
        if [[ -n "${cached_legacy_revisions[$candidate]:-}" ]]; then
            legacy_candidate="$candidate"
        fi
    done < <(git -C "$repository" rev-list "$source_commit")
    if [[ -n "$legacy_candidate" ]]; then
        printf '%s\n' "$legacy_candidate"
        return 0
    fi
    printf '%s\n' "$source_commit"
}
