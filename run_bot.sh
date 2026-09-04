#!/bin/bash

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

if [ -f "$DIR/venv/bin/activate" ]; then
    source "$DIR/venv/bin/activate"
elif [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
elif [ -d "$HOME/.virtualenvs" ]; then
    for v in "$HOME/.virtualenvs"/*/bin/activate; do
        if [ -f "$v" ]; then
            source "$v"
            break
        fi
    done
fi

LOG_FILE="$DIR/bot.log"

trap "echo '[$(date \"+%Y-%m-%d %H:%M:%S\")] Скрипт остановлен.' >> \"$LOG_FILE\"; exit 0" SIGINT SIGTERM

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Запуск службы автоперезапуска BlinModBot..." >> "$LOG_FILE"

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Старт bot.py..." >> "$LOG_FILE"
    python3 bot.py >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Бот завершил работу с кодом $EXIT_CODE. Перезапуск через 5 секунд..." >> "$LOG_FILE"
    sleep 5
done