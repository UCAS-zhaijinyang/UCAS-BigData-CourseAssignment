SERVICE='kv-store'
if [ "$(uname)" = "Darwin" ]; then
    if pgrep -xq -- "${SERVICE}"; then
        pkill -f "${SERVICE}"
    fi
    rm -r 127.0.0.1:*.db || echo "no db to clean"
else
    set +e # killall will error if finds no process to kill
    killall "${SERVICE}"
    set -e
fi

rm -r 127.0.0.1:*.db 2>/dev/null || true

rm *.log 2>/dev/null || true
