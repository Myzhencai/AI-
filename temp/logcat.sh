#!/bin/sh

LOG_TAG="Runtime"
LOG_FILE="/sdcard/system_log.txt"

logcat -c
: > "$LOG_FILE"
logcat -s "$LOG_TAG" -v time -f "$LOG_FILE" &
LOGCAT_PID=$!
sleep 60
kill $LOGCAT_PID
sync