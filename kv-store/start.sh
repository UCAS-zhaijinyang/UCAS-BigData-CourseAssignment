#!/bin/sh

set -o errexit

cargo build

kill_all() {
    SERVICE='kv-store'
    if [ "$(uname)" = "Darwin" ]; then
        if pgrep -xq -- "${SERVICE}"; then
            pkill -f "${SERVICE}"
        fi
        rm -r 127.0.0.1:*.db || echo "no db to clean"
    else
        set +e 
        killall "${SERVICE}"
        set -e
    fi
}

# Ctrl+C
on_exit() {
    echo
    echo "caught interrupt, cleaning up..."
    set +e
    [ -n "${PID1:-}" ] && kill "${PID1}" 2>/dev/null || true
    [ -n "${PID2:-}" ] && kill "${PID2}" 2>/dev/null || true
    [ -n "${PID3:-}" ] && kill "${PID3}" 2>/dev/null || true

    kill_all

    rm -rf 127.0.0.1:*.db || true

    exit 0
}

# 捕获 ctrl+C
trap 'on_exit' INT TERM

rpc() {
    local uri=$1
    local body="$2"

    echo '---'" rpc(:$uri, $body)"

    {
        if [ ".$body" = "." ]; then
            time curl --silent "127.0.0.1:$uri"
        else
            time curl --silent "127.0.0.1:$uri" -H "Content-Type: application/json" -d "$body"
        fi
    } | {
        if type jq > /dev/null 2>&1; then
            jq
        else
            cat
        fi
    }

    echo
    echo
}

export RUST_LOG=info
export RUST_BACKTRACE=0
bin=./target/debug/kv-store

echo "Killing all running kv-store and cleaning up old data..."

kill_all
sleep 1

if ls 127.0.0.1:*.db
then
    rm -r 127.0.0.1:*.db || echo "no db to clean"
fi

echo "启动 3 个 kv-store server..."

${bin} --id 1 --addr 127.0.0.1:21001 > n1.log 2>&1 &
PID1=$!
sleep 1
echo "Server 1 started"

nohup ${bin} --id 2 --addr 127.0.0.1:21002 > n2.log 2>&1 &
PID2=$!
sleep 1
echo "Server 2 started"

nohup ${bin} --id 3 --addr 127.0.0.1:21003 > n3.log 2>&1 &
PID3=$!
sleep 1
echo "Server 3 started"
sleep 1

echo "初始化 server 1 作为 raft 集群..."
sleep 2
echo
rpc 21001/init '[]'

echo "Server 1 is a leader now"

tail -f n1.log
