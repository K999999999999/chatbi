#!/usr/bin/env bash

append_deployment_release_arguments() {
    local -n output_args="$1"
    local prefix="$2"
    shift 2
    [[ "$prefix" == active || "$prefix" == baseline ]] || return 2
    (( $# == 5 )) || return 2
    output_args+=(
        "--${prefix}-source-commit" "$1"
        "--${prefix}-api-image" "$2"
        "--${prefix}-api-image-id" "$3"
        "--${prefix}-database-runtime-image" "$4"
        "--${prefix}-database-runtime-image-id" "$5"
    )
}
