#!/bin/sh
set -eu
# Does not test production authentication. Runs over Docker-internal network.
DOCKER_NET="${DOCKER_NET:-osint_mcp_internal}"
for body in '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"osint-smoke","version":"1.0"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'; do
  docker run --rm --network "$DOCKER_NET" curlimages/curl:8.12.1 \
    -fsS -H 'Host: localhost:8000' -H 'Content-Type: application/json' \
    -H 'Accept: application/json, text/event-stream' \
    --data "$body" http://osint-mcp:8000/mcp
  printf '\n'
done
