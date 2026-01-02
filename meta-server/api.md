# api

## DATA api

1、写入操作（增加/更新键值）

/write POST

```json
{"Put":{ "key":key, "value":value }}
```

```json
"OK"
"Err"
```

2、写入操作（删除键值）

/write POST

```json
{"Del":{ "key":key }}
```

```json
"OK"
"Err"
```

3、读取操作（读取单个键值）

/read POST

```json
"key"
```

```json
{"OK": "bar"} // 没有该键值则返回""
```

```json
{"err" : ... }
```

4、读取操作（读取所有键值）

/read-all GET

```json
{"OK":{ "k":k1, "v":v1 }, { "k":k2, "v":v2 }...}
```

```json
{"err"}
```

## Cluster api

5、添加learner节点

/add-learner POST

```json
[2, "127.0.0.1:21002"]
```

```json
{
  "Ok": {
    "log_id": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 5
    },
    "data": {
      "value": null
    },
    "membership": {
      "configs": [[1]],
      "nodes": {
        "1": { "addr": "127.0.0.1:21001" },
        "2": { "addr": "127.0.0.1:21002" },
        "3": { "addr": "127.0.0.1:21002" },
      }
    }
  }
}

```

6、改变节点属性

/change-membership POST

```json
    [1, 2]
```

```json
{
  "Ok": {
    "log_id": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 5
    },
    "data": {
      "value": null
    },
    "membership": {
      "configs": [[1, 2]],
      "nodes": {
        "1": { "addr": "127.0.0.1:21001" },
        "2": { "addr": "127.0.0.1:21002" },
      }
    }
  }
}

```

7、查询集群状态

/metrics GET

```json
    null
```

```json
{
  "Ok": {
    "running_state": {
      "Ok": null
    },
    "id": 1,
    "current_term": 1,
    "vote": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "committed": true
    },
    "last_log_index": 3,
    "last_applied": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 3
    },
    "snapshot": null,
    "purged": null,
    "state": "Leader",
    "current_leader": 1,
    "millis_since_quorum_ack": 0,
    "last_quorum_acked": 1766401699240929138,
    "membership_config": {
      "log_id": {
        "leader_id": {
          "term": 1,
          "node_id": 1
        },
        "index": 3
      },
      "membership": {
        "configs": [
          [
            1
          ]
        ],
        "nodes": {
          "1": {
            "addr": "127.0.0.1:21001"
          },
          "2": {
            "addr": "127.0.0.1:21002"
          },
          "3": {
            "addr": "127.0.0.1:21003"
          }
        }
      }
    }
  },
  "heartbeat": {
    "1": 1766401699239579794,
    "2": 1766401699235113724,
    "3": 1766401699235113722
  },
  "replication": {
    "1": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 3
    },
    "2": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 3
    },
    "3": {
      "leader_id": {
        "term": 1,
        "node_id": 1
      },
      "index": 3
    }
  }
}


```

