"""
基于Flask框架的模拟数据库服务器
模拟Raft集群的HTTP API（端口21001），用于测试其他组件
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import threading

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 内存数据库（模拟键值存储）
database = {}
db_lock = threading.Lock()

# 集群状态（模拟Raft集群信息）
cluster_state = {
    'current_term': 1,
    'node_id': 1,
    'log_index': 0,
    'members': {
        '1': {'addr': '127.0.0.1:21001'},
    },
    'configs': [[1]],
    'learners': {}
}


def generate_log_id():
    """生成日志ID"""
    cluster_state['log_index'] += 1
    return {
        "leader_id": {
            "term": cluster_state['current_term'],
            "node_id": cluster_state['node_id']
        },
        "index": cluster_state['log_index']
    }


def generate_membership_response():
    """生成成员关系响应"""
    return {
        "log_id": generate_log_id(),
        "data": {
            "value": None
        },
        "membership": {
            "configs": cluster_state['configs'],
            "nodes": cluster_state['members']
        }
    }


@app.route('/write', methods=['POST'])
def write():
    """写入操作（增加/更新/删除键值）"""
    try:
        data = request.get_json()
        
        if not data:
            return "Err", 400
        
        # 处理Put操作
        if 'Put' in data:
            put_data = data['Put']
            key = put_data.get('key')
            value = put_data.get('value')
            
            if key is None or value is None:
                return "Err", 400
            
            with db_lock:
                database[key] = value
            
            return "Ok", 200
        
        # 处理Del操作
        elif 'Del' in data:
            del_data = data['Del']
            key = del_data.get('key')
            
            if key is None:
                return "Err", 400
            
            with db_lock:
                if key in database:
                    del database[key]
                    return "Ok", 200
                else:
                    return "Err", 200  # 键不存在也返回Err
        
        else:
            return "Err", 400
    
    except Exception as e:
        print(f"写入操作错误: {e}")
        return "Err", 500


@app.route('/read', methods=['POST'])
def read():
    """读取操作（读取单个键值）"""
    try:
        # 根据API文档，read接收的是字符串key
        key = request.get_json()
        
        if key is None:
            return jsonify({"err": "缺少key参数"}), 400
        
        # 如果传入的是字符串，直接使用
        if isinstance(key, str):
            key_str = key
        # 如果传入的是其他类型，尝试转换
        else:
            return jsonify({"err": "key必须是字符串"}), 400
        
        with db_lock:
            if key_str in database:
                return jsonify({"Ok": database[key_str]}), 200
            else:
                # 没有该键值则返回空字符串
                return jsonify({"Ok": ""}), 200
    
    except Exception as e:
        print(f"读取操作错误: {e}")
        return jsonify({"err": str(e)}), 500


@app.route('/read-all', methods=['GET'])
def read_all():
    """读取操作（读取所有键值）"""
    try:
        with db_lock:
            if not database:
                return jsonify({"OK": []}), 200
            
            # 格式: {"OK": [{ "k":k1, "v":v1 }, { "k":k2, "v":v2 }...]}
            result = [{"k": k, "v": v} for k, v in database.items()]
            return jsonify({"Ok": result}), 200
    
    except Exception as e:
        print(f"读取所有操作错误: {e}")
        return jsonify({"err": str(e)}), 500


@app.route('/add-learner', methods=['POST'])
def add_learner():
    """添加learner节点"""
    try:
        data = request.get_json()
        
        if not data or not isinstance(data, list) or len(data) != 2:
            return jsonify({"err": "参数格式错误，应为[node_id, api_addr]"}), 400
        
        node_id = str(data[0])
        api_addr = data[1]
        
        # 添加到learners
        cluster_state['learners'][node_id] = api_addr
        
        # 添加到members（如果不存在）
        if node_id not in cluster_state['members']:
            cluster_state['members'][node_id] = {'addr': api_addr}
        
        # 生成响应
        response = {
            "Ok": generate_membership_response()
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"添加learner节点错误: {e}")
        return jsonify({"err": str(e)}), 500


@app.route('/change-membership', methods=['POST'])
def change_membership():
    """改变节点属性"""
    try:
        data = request.get_json()
        
        if not data or not isinstance(data, list):
            return jsonify({"err": "参数格式错误，应为[node_id1, node_id2, ...]"}), 400
        
        # 更新配置
        node_ids = [int(nid) for nid in data]
        cluster_state['configs'] = [node_ids]
        
        # 生成响应
        response = {
            "Ok": generate_membership_response()
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"改变成员关系错误: {e}")
        return jsonify({"err": str(e)}), 500


@app.route('/metrics', methods=['GET'])
def metrics():
    """查询集群状态"""
    try:
        current_time = int(time.time() * 1_000_000_000)  # 纳秒时间戳
        
        # 生成心跳信息
        heartbeat = {}
        for node_id in cluster_state['members'].keys():
            heartbeat[node_id] = current_time - (len(cluster_state['members']) - int(node_id)) * 1000000
        
        # 生成复制信息
        replication = {}
        for node_id in cluster_state['members'].keys():
            replication[node_id] = {
                "leader_id": {
                    "term": cluster_state['current_term'],
                    "node_id": cluster_state['node_id']
                },
                "index": cluster_state['log_index']
            }
        
        # 构建响应
        response = {
            "Ok": {
                "running_state": {
                    "Ok": None
                },
                "id": cluster_state['node_id'],
                "current_term": cluster_state['current_term'],
                "vote": {
                    "leader_id": {
                        "term": cluster_state['current_term'],
                        "node_id": cluster_state['node_id']
                    },
                    "committed": True
                },
                "last_log_index": cluster_state['log_index'],
                "last_applied": {
                    "leader_id": {
                        "term": cluster_state['current_term'],
                        "node_id": cluster_state['node_id']
                    },
                    "index": cluster_state['log_index']
                },
                "snapshot": None,
                "purged": None,
                "state": "Leader",
                "current_leader": cluster_state['node_id'],
                "millis_since_quorum_ack": 0,
                "last_quorum_acked": current_time,
                "membership_config": {
                    "log_id": {
                        "leader_id": {
                            "term": cluster_state['current_term'],
                            "node_id": cluster_state['node_id']
                        },
                        "index": cluster_state['log_index']
                    },
                    "membership": {
                        "configs": cluster_state['configs'],
                        "nodes": cluster_state['members']
                    }
                }
            },
            "heartbeat": heartbeat,
            "replication": replication
        }
        
        return jsonify(response), 200
    
    except Exception as e:
        print(f"查询集群状态错误: {e}")
        return jsonify({"err": str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "database_size": len(database),
        "cluster_state": "running"
    }), 200


@app.route('/', methods=['GET'])
def index():
    """API文档"""
    return jsonify({
        "message": "模拟数据库服务器 (端口21001)",
        "endpoints": {
            "POST /write": "写入操作（Put/Del）",
            "POST /read": "读取单个键值",
            "GET /read-all": "读取所有键值",
            "POST /add-learner": "添加learner节点",
            "POST /change-membership": "改变节点属性",
            "GET /metrics": "查询集群状态",
            "GET /health": "健康检查"
        },
        "current_database_size": len(database)
    }), 200


if __name__ == '__main__':
    print("=" * 60)
    print("模拟数据库服务器启动")
    print("=" * 60)
    print("模拟Raft集群HTTP API (端口21001)")
    print("=" * 60)
    print("API端点:")
    print("  POST /write - 写入操作（增加/更新/删除键值）")
    print("  POST /read - 读取单个键值")
    print("  GET  /read-all - 读取所有键值")
    print("  POST /add-learner - 添加learner节点")
    print("  POST /change-membership - 改变节点属性")
    print("  GET  /metrics - 查询集群状态")
    print("  GET  /health - 健康检查")
    print("=" * 60)
    print(f"服务器运行在 http://127.0.0.1:21001")
    print("=" * 60)
    
    app.run(debug=True, host='127.0.0.1', port=21001)
