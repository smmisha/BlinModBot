#!/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

LOCK_FILE="/tmp/blinmodbot.lock"

# Защита от дубликатов: разрешаем работу только одному экземпляру скрипта
exec 200>"$LOCK_FILE"
flock -n 200 || {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ОШИБКА: Копия run_bot.sh уже запущена (PID $(cat $LOCK_FILE 2>/dev/null))! Завершаю дубликат."
    exit 1
}
echo "$$" > "$LOCK_FILE"

# Авто-подключение виртуального окружения
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
trap "echo '[$(date \"+%Y-%m-%d %H:%M:%S\")] Скрипт остановлен.' >> \"$LOG_FILE\"; rm -f \"$LOCK_FILE\"; exit 0" SIGINT SIGTERM

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Служба автоперезапуска запущена (PID: $$)" >> "$LOG_FILE"

while true; do
    # Убеждаемся, что нет зависших копий bot.py
    pkill -9 -f "bot.py" 2>/dev/null
    sleep 1

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Старт bot.py..." >> "$LOG_FILE"
    python3 -u bot.py >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Бот завершил работу с кодом $EXIT_CODE. Перезапуск через 5 сек..." >> "$LOG_FILE"
    sleep 5
done