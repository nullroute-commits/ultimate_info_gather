#!/bin/sh
set -eu

# Fetch Grafana performance overview dashboards from the pinned
# enter-the-metrics repository (https://github.com/nullroute-commits/enter-the-metrics.git @ abb9825).
# Dashboards are provisioned into Grafana via the dashboard provider
# configuration in configuration/monitoring/grafana/provisioning/dashboards/.

DASHBOARD_DIR="${1:-configuration/monitoring/grafana/dashboards/performance_overview}"
mkdir -p "$DASHBOARD_DIR"

BASE_URL="https://raw.githubusercontent.com/nullroute-commits/enter-the-metrics/abb9825/grafana/data/dashboards/performance_overview"

DASHBOARDS="
performance_overview_docker.json
performance_overview_grafana.json
performance_overview_loki.json
performance_overview_prometheus.json
prometheus_node_exporter.json
"

for dashboard in $DASHBOARDS; do
  echo "Fetching $dashboard ..."
  if command -v wget >/dev/null 2>&1; then
    wget -q -O "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL -o "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"
  else
    echo "ERROR: Neither wget nor curl is available" >&2
    exit 1
  fi
done

echo "Dashboards fetched to $DASHBOARD_DIR"
