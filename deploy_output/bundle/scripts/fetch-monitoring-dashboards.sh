#!/bin/sh
set -eu

# Fetch Grafana performance overview dashboards from the pinned
# enter-the-metrics repository (https://github.com/nullroute-commits/enter-the-metrics.git @ 706ed92).
# Dashboards are provisioned into Grafana via the dashboard provider
# configuration in configuration/monitoring/grafana/provisioning/dashboards/.

DASHBOARD_DIR="${1:-configuration/monitoring/grafana/dashboards/performance_overview}"
mkdir -p "$DASHBOARD_DIR"

BASE_URL="https://raw.githubusercontent.com/nullroute-commits/enter-the-metrics/706ed92/grafana/data/dashboards/performance_overview"

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
    if ! wget -q -O "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"; then
      echo "WARNING: Failed to fetch $dashboard; continuing without it" >&2
      rm -f "$DASHBOARD_DIR/$dashboard"
    fi
  elif command -v curl >/dev/null 2>&1; then
    if ! curl -fsSL -o "$DASHBOARD_DIR/$dashboard" "$BASE_URL/$dashboard"; then
      echo "WARNING: Failed to fetch $dashboard; continuing without it" >&2
      rm -f "$DASHBOARD_DIR/$dashboard"
    fi
  else
    echo "ERROR: Neither wget nor curl is available" >&2
    exit 1
  fi
done

echo "Dashboards fetched to $DASHBOARD_DIR"
