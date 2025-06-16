#!/bin/sh

LOG_TAG="Runtime"
LOG_FILE="/sdcard/system_log.txt"


: > "$LOG_FILE"
logcat -s "$LOG_TAG" -v time -f "$LOG_FILE" &
LOGCAT_PID=$!
sleep 5
kill $LOGCAT_PID
sync