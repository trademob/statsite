#!/bin/bash
set -e

echo 'Eval and create statsite conf'

[[ -z "$STATS_UDP_PORT" ]]                   && STATS_UDP_PORT=8125
[[ -z "$STATS_TCP_PORT" ]]                   && STATS_TCP_PORT=8125
[[ -z "$LOG_LEVEL" ]]                  && LOG_LEVEL=INFO
[[ -z "$FLUSH_INTERVAL" ]]             && FLUSH_INTERVAL=2
[[ -z "$GLOBAL_PREFIX" ]]              && GLOBAL_PREFIX=service.container.
[[ -z "$COUNTS_PREFIX" ]]              && COUNTS_PREFIX=counters.
[[ -z "$EXTENDED_COUNTERS" ]]          && EXTENDED_COUNTERS=false
[[ -z "$LEGACY_EXTENDED_COUNTERS" ]]   && LEGACY_EXTENDED_COUNTERS=true
[[ -z "$TIMERS_INCLUDE" ]]             && TIMERS_INCLUDE=lower,mean,median,upper
[[ -z "$SINK_HOST" ]]                  && SINK_HOST=relay.metrics.eu-west-1.net0ps.com
[[ -z "$SINK_PORT" ]]                  && SINK_PORT=2013

cat << STATCONF > /usr/local/statsite.conf
[statsite]
port = $STATS_TCP_PORT
udp_port = $STATS_UDP_PORT
bind_address = 0.0.0.0
parse_stdin = 1
log_level = $LOG_LEVEL
log_facility = local0
flush_interval = $FLUSH_INTERVAL
global_prefix = $GLOBAL_PREFIX

counts_prefix = $COUNTS_PREFIX
extended_counters = $EXTENDED_COUNTERS
legacy_extended_counters = $LEGACY_EXTENDED_COUNTERS
timers_include = $TIMERS_INCLUDE
quantiles = 0.5

timer_eps = 0.01
set_eps = 0.02

stream_cmd = python /usr/local/share/statsite/sinks/graphite.py --host $SINK_HOST --port $SINK_PORT --normalize

STATCONF

echo 'Start statsite'

/usr/local/bin/statsite -f /usr/local/statsite.conf
