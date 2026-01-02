import threading
import json
import requests
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

# 服务器日志
log = []
log_lock = threading.Lock()

# 数据库服务配置
DB_BASE_URL = "http://127.0.0.1:21001"


class Server:
    def __init__(self, server_id):
        self.server_id = server_id
        self.cache = {}  # 每个服务器实例的缓存字典
        self.db_urls = [DB_BASE_URL, "http://127.0.0.1:21002", "http://127.0.0.1:21003"]  # 数据库服务URL列表
        self.current_ids = [1,] # 当前集群中的voter及以上的节点
        
    def put(self, key, value, action):
        # JSON请求体格式留空占位
        json_data = {
            "Put":{ "key":key, "value":value }
        }
        
        response = self._http_request('/write', json_data=json_data)
        if response == "Ok":
            #self.cache[key] = value  # 添加/更新缓存
            msg = f"{action}key：{key}，value：{value}"
            self.write_log(msg)
            return True
        return False

    def get(self, key):
        # 先检查缓存，如果存在于缓存中则直接返回
        # if key in self.cache:
        #     return self.cache[key]

        # 如果不在缓存中，则从数据库中获取，并更新缓存
        # JSON请求体格式：字符串key（根据test-cluster.sh，read使用POST方法）
        json_data = key  # 直接发送字符串key
        
        response = self._http_request('/read', json_data=json_data, method='POST')
        if response is not None:
            # 响应格式：{"OK": "value"}，其中第二个值（value）可能是实际值或空字符串
            if isinstance(response, dict):
                # 尝试获取 "OK" 键（不区分大小写）
                if "Ok" in response:
                    second_value = response["Ok"]
                else:
                    # 如果字典中没有OK键，返回空字符串
                    return ""
                
                # 提取第二个值：{"OK": "value"} 中的 "value" 部分
                # 注意：即使值为空字符串，也要返回（表示键存在但值为空）
                # 如果第二个值不为空，更新缓存
                if second_value and second_value != "":
                    self.cache[key] = second_value
                # 返回第二个值（可能是实际值或空字符串）
                # 这里返回的是 {"OK": "value"} 中的 value 部分
                return second_value
            # 如果响应格式不对，尝试直接返回响应（可能是字符串格式）
            elif isinstance(response, str):
                return response
            # 如果响应格式不对，返回空字符串表示键不存在
            return ""
        # 如果请求失败，返回空字符串
        return ""

    def delete(self, key):
        # 从数据库中删除键值对，并从缓存中删除
        # 在删除前先检查键是否存在
        existing_value = self.get(key)
        if not existing_value or existing_value == "":
            # 键不存在，返回False表示无法删除
            return False
        
        # 键存在，执行删除操作
        json_data = {
            "Del":{ "key":key }
        }
        
        response = self._http_request('/write', json_data=json_data)
        if response == "Ok":
            #if key in self.cache:
            #    del self.cache[key]  # 从缓存中删除
            msg = f"删除key：{key}"
            self.write_log(msg)
            return True
        return False

    def list(self):
        # 返回整个数据库
        # 端点路径和JSON格式留空占位
        json_data = None  # TODO: 填充JSON格式
        
        response = self._http_request('/read-all', json_data=json_data, method='GET')
        if response is not None:
            return response  # 根据实际响应格式调整
        return {}

    def add_learner(self, node_id, api_addr):
        # 添加raft节点作为learner
        # 格式: [node_id, "api_addr"] 例如: [2, "127.0.0.1:21002"]
        json_data = [node_id, api_addr]
        
        response = self._http_request('/add-learner', json_data=json_data)
        # 检查响应中是否包含 "Ok" 键，如果包含则说明操作成功
        if response is not None and isinstance(response, dict) and "Ok" in response:
            msg = f"添加learner节点: node_id={node_id}, address={api_addr}"
            self.write_log(msg)
            return response
        return None

    def change_membership(self, node_ids):
        # 改变节点关系
        # 格式: [node_id1, node_id2, ...] 例如: [1, 2, 3]
        # node_ids可以是列表或集合
        if isinstance(node_ids, (set, tuple)):
            json_data = list(node_ids)
        else:
            json_data = node_ids
        
        response = self._http_request('/change-membership', json_data=json_data)
        # 检查响应中是否包含 "Ok" 键，如果包含则说明操作成功
        if response is not None and isinstance(response, dict) and "Ok" in response:
            msg = f"改变成员关系: {json_data}"
            self.write_log(msg)
            self.current_ids = node_ids
            return response
        return None

    def metrics(self):
        # 查询当前的raft集群状态
        # GET请求，无参数
        response = self._http_request('/metrics', json_data=None, method='GET')
        if response is not None:
            # 解析并格式化 metrics 响应
            formatted_result = self._format_metrics(response)
            return formatted_result
        return None
    
    def _format_metrics(self, metrics_data):
        """
        格式化 metrics 数据，使其输出直观且内容详尽
        基于 openraft RaftMetrics 结构，详细展示 Raft 集群状态信息
        """
        if not isinstance(metrics_data, dict):
            return metrics_data
        
        result_lines = []
        result_lines.append("=" * 60)
        result_lines.append("Raft 集群状态信息 (基于 openraft RaftMetrics)")
        result_lines.append("=" * 60)
        
        # 提取 Ok 部分的主要信息
        if "Ok" in metrics_data and isinstance(metrics_data["Ok"], dict):
            ok_data = metrics_data["Ok"]
            
            # 节点基本信息
            result_lines.append("\n【节点基本信息】")
            if "id" in ok_data:
                result_lines.append(f"  节点ID (id): {ok_data['id']}")
                result_lines.append(f"    └─ Raft 节点的唯一标识符")
            
            if "current_term" in ok_data:
                result_lines.append(f"  当前任期 (current_term): {ok_data['current_term']}")
                result_lines.append(f"    └─ Raft 节点的当前任期号，用于选举和日志一致性")
            
            if "state" in ok_data:
                state = ok_data["state"]
                result_lines.append(f"  节点状态 (state): {state}")
                result_lines.append(f"    └─ 可能值: Leader(领导者), Follower(跟随者), Candidate(候选者)")
            
            if "current_leader" in ok_data:
                leader = ok_data["current_leader"]
                if leader is not None:
                    result_lines.append(f"  当前Leader (current_leader): {leader}")
                else:
                    result_lines.append(f"  当前Leader (current_leader): 无 (集群可能正在选举)")
                result_lines.append(f"    └─ 当前集群的 Leader 节点ID，None 表示无 Leader")
            
            # 运行状态
            if "running_state" in ok_data:
                running_state = ok_data["running_state"]
                if isinstance(running_state, dict):
                    if "Ok" in running_state:
                        result_lines.append(f"  运行状态 (running_state): 正常")
                        result_lines.append(f"    └─ Result<(), Fatal<NID>>: Ok 表示节点正常运行")
                    elif "Err" in running_state:
                        result_lines.append(f"  运行状态 (running_state): 错误 - {running_state['Err']}")
                        result_lines.append(f"    └─ 节点遇到致命错误，需要关注")
                    else:
                        result_lines.append(f"  运行状态 (running_state): {running_state}")
                else:
                    result_lines.append(f"  运行状态 (running_state): {running_state}")
            
            # 投票信息
            if "vote" in ok_data and isinstance(ok_data["vote"], dict):
                vote = ok_data["vote"]
                result_lines.append("\n【投票信息 (vote)】")
                result_lines.append(f"    └─ Vote<NID>: 最后接受的投票")
                if "leader_id" in vote:
                    leader_id = vote["leader_id"]
                    if isinstance(leader_id, dict):
                        node_id = leader_id.get('node_id', 'N/A')
                        term = leader_id.get('term', 'N/A')
                        result_lines.append(f"  投票给Leader: 节点 {node_id} (任期 {term})")
                if "committed" in vote:
                    committed = vote["committed"]
                    result_lines.append(f"  投票已提交 (committed): {committed}")
                    result_lines.append(f"    └─ True: 投票已提交，Leader 已获得法定人数确认")
            
            # 日志信息
            result_lines.append("\n【日志信息】")
            
            if "last_log_index" in ok_data:
                last_log_index = ok_data["last_log_index"]
                if last_log_index is not None:
                    result_lines.append(f"  最后日志索引 (last_log_index): {last_log_index}")
                    result_lines.append(f"    └─ Option<u64>: 最后追加到此节点日志的索引")
                else:
                    result_lines.append(f"  最后日志索引 (last_log_index): 无 (日志为空)")
            
            if "last_applied" in ok_data:
                last_applied = ok_data["last_applied"]
                if isinstance(last_applied, dict):
                    result_lines.append(f"  最后应用索引 (last_applied):")
                    result_lines.append(f"    └─ Option<LogId<NID>>: 最后应用到此节点状态机的日志索引")
                    if "index" in last_applied:
                        result_lines.append(f"      索引: {last_applied['index']}")
                    if "leader_id" in last_applied and isinstance(last_applied["leader_id"], dict):
                        leader_id = last_applied["leader_id"]
                        node_id = leader_id.get('node_id', 'N/A')
                        term = leader_id.get('term', 'N/A')
                        result_lines.append(f"      创建Leader: 节点 {node_id} (任期 {term})")
                elif last_applied is None:
                    result_lines.append(f"  最后应用索引 (last_applied): 无")
            
            # 快照信息
            if "snapshot" in ok_data:
                snapshot = ok_data["snapshot"]
                result_lines.append(f"  快照 (snapshot):")
                result_lines.append(f"    └─ Option<LogId<NID>>: 快照中包含的最后日志ID")
                if snapshot is not None and isinstance(snapshot, dict):
                    if "index" in snapshot:
                        result_lines.append(f"      快照日志索引: {snapshot['index']}")
                    if "leader_id" in snapshot and isinstance(snapshot["leader_id"], dict):
                        leader_id = snapshot["leader_id"]
                        node_id = leader_id.get('node_id', 'N/A')
                        term = leader_id.get('term', 'N/A')
                        result_lines.append(f"      快照Leader: 节点 {node_id} (任期 {term})")
                else:
                    result_lines.append(f"      无快照 (如果没有快照，则为 (0,0))")
            
            # 清理信息
            if "purged" in ok_data:
                purged = ok_data["purged"]
                result_lines.append(f"  已清理日志 (purged):")
                result_lines.append(f"    └─ Option<LogId<NID>>: 从存储中清理的最后日志ID（包含）")
                result_lines.append(f"    └─ 注意: purged 也是 Openraft 知道的第一条日志ID")
                if purged is not None and isinstance(purged, dict):
                    if "index" in purged:
                        result_lines.append(f"      已清理到索引: {purged['index']}")
                    if "leader_id" in purged and isinstance(purged["leader_id"], dict):
                        leader_id = purged["leader_id"]
                        node_id = leader_id.get('node_id', 'N/A')
                        term = leader_id.get('term', 'N/A')
                        result_lines.append(f"      清理Leader: 节点 {node_id} (任期 {term})")
                else:
                    result_lines.append(f"      无清理记录")
            
            # Leader 相关信息
            if "millis_since_quorum_ack" in ok_data:
                millis = ok_data["millis_since_quorum_ack"]
                result_lines.append(f"  距离上次法定人数确认 (millis_since_quorum_ack):")
                result_lines.append(f"    └─ Option<u64>: 对于 Leader，是自最近一次被法定人数确认以来的毫秒数")
                if millis is not None:
                    result_lines.append(f"      时间: {millis} 毫秒")
                    if millis > 1000:
                        result_lines.append(f"      ⚠️  警告: 超过1秒未收到确认，Leader 可能与集群失去同步")
                else:
                    result_lines.append(f"      None: 节点不是 Leader 或 Leader 尚未被法定人数确认")
                    result_lines.append(f"      注意: 用于评估 Leader 是否与集群失去同步的可能性")
            
            if "last_quorum_acked" in ok_data:
                last_quorum_acked = ok_data["last_quorum_acked"]
                if last_quorum_acked is not None:
                    result_lines.append(f"  最后法定人数确认时间戳 (last_quorum_acked): {last_quorum_acked}")
                    result_lines.append(f"    └─ 纳秒时间戳")
            
            # 成员配置信息
            if "membership_config" in ok_data and isinstance(ok_data["membership_config"], dict):
                membership_config = ok_data["membership_config"]
                result_lines.append("\n【成员配置 (membership_config)】")
                result_lines.append(f"    └─ Arc<StoredMembership<NID, N>>: 当前集群的成员配置")
                
                if "log_id" in membership_config and isinstance(membership_config["log_id"], dict):
                    log_id = membership_config["log_id"]
                    result_lines.append(f"  配置日志ID (log_id):")
                    if "index" in log_id:
                        result_lines.append(f"    索引: {log_id['index']}")
                    if "leader_id" in log_id and isinstance(log_id["leader_id"], dict):
                        leader_id = log_id["leader_id"]
                        node_id = leader_id.get('node_id', 'N/A')
                        term = leader_id.get('term', 'N/A')
                        result_lines.append(f"    创建配置的Leader: 节点 {node_id} (任期 {term})")
                
                if "membership" in membership_config and isinstance(membership_config["membership"], dict):
                    membership = membership_config["membership"]
                    if "configs" in membership:
                        configs = membership["configs"]
                        result_lines.append(f"  配置组 (configs): {configs}")
                        result_lines.append(f"    └─ 当前生效的配置组，支持联合共识 (Joint Consensus)")
                        if isinstance(configs, list) and len(configs) > 0:
                            for i, config in enumerate(configs):
                                if isinstance(config, list):
                                    result_lines.append(f"      配置组 {i+1}: {config} (投票成员)")
                    
                    if "nodes" in membership and isinstance(membership["nodes"], dict):
                        result_lines.append(f"  节点列表 (nodes):")
                        result_lines.append(f"    └─ 所有已知节点（包括 voting members 和 learners）")
                        for node_id, node_info in membership["nodes"].items():
                            if isinstance(node_info, dict) and "addr" in node_info:
                                result_lines.append(f"      节点 {node_id}: {node_info['addr']}")
        
        # 心跳信息（非 RaftMetrics 标准字段，可能是扩展信息）
        if "heartbeat" in metrics_data and isinstance(metrics_data["heartbeat"], dict):
            result_lines.append("\n【心跳信息 (heartbeat)】")
            result_lines.append(f"    └─ 各节点最后一次心跳的纳秒时间戳（扩展信息）")
            for node_id, timestamp in metrics_data["heartbeat"].items():
                result_lines.append(f"  节点 {node_id}: {timestamp}")
        
        # 复制信息
        if "replication" in metrics_data and isinstance(metrics_data["replication"], dict):
            result_lines.append("\n【复制状态 (replication)】")
            result_lines.append(f"    └─ Option<BTreeMap<NID, Option<LogId<NID>>>>: 复制状态")
            result_lines.append(f"    └─ 注意: 只有当节点是 Leader 时才为 Some()")
            replication = metrics_data["replication"]
            if replication:
                for node_id, repl_info in replication.items():
                    if isinstance(repl_info, dict):
                        result_lines.append(f"  节点 {node_id}:")
                        if "index" in repl_info:
                            result_lines.append(f"    已复制日志索引: {repl_info['index']}")
                        if "leader_id" in repl_info and isinstance(repl_info["leader_id"], dict):
                            leader_id = repl_info["leader_id"]
                            node_id_val = leader_id.get('node_id', 'N/A')
                            term = leader_id.get('term', 'N/A')
                            result_lines.append(f"    复制Leader: 节点 {node_id_val} (任期 {term})")
                    elif repl_info is None:
                        result_lines.append(f"  节点 {node_id}: 无复制信息")
            else:
                result_lines.append(f"  无复制信息 (当前节点不是 Leader)")
        
        result_lines.append("\n" + "=" * 60)
        
        return "\n".join(result_lines)

    def get_log(self):
        # 返回服务器日志
        with log_lock:
            return log

    def write_log(self, msg):
        # 记录服务器操作相关的日志
        with log_lock:
            log.append(f"服务器 {self.server_id}：{msg}")
        return True

    def _http_request(self, endpoint, json_data=None, method='POST'):
        # HTTP请求辅助方法，处理JSON序列化和错误处理
        # 遍历3个URL，如果所有响应都是"Err"，返回"Err"；否则返回第一个非"Err"响应的json()
        headers = {'Content-Type': 'application/json'}
        responses = []
        
        for id in self.current_ids:
            url = f"{self.db_urls[id - 1]}{endpoint}"
            try:
                if method == 'POST':
                    response = requests.post(url, json=json_data, headers=headers)
                elif method == 'GET':
                    response = requests.get(url, headers=headers)
                else:
                    continue
                
                response.raise_for_status()
                # 检查响应内容
                if response.content:
                    try:
                        response_data = response.json()
                        responses.append(response_data)
                    except ValueError:
                        # 如果不是JSON格式，返回原始文本
                        response_text = response.text
                        responses.append(response_text)
                else:
                    responses.append(None)
            except requests.exceptions.RequestException as e:
                print(f"HTTP请求错误 (URL: {url}): {e}")
                responses.append("Err")

        # 检查所有响应是否都是"Err"
        if all(resp == "Err" for resp in responses):
            return "Err"
        
        # 返回第一个非"Err"的响应
        for resp in responses:
            if resp != "Err" and resp is not None:
                return resp
        
        return None


def run_server(server_id):
    # 启动和运行 XML-RPC 服务器
    server = SimpleXMLRPCServer(("localhost", 20000 + server_id), requestHandler=SimpleXMLRPCRequestHandler, allow_none=True)
    server.register_instance(Server(server_id))
    print(f"服务器 {server_id} 正在运行在端口 {20000 + server_id}\n")
    server.serve_forever()


if __name__ == "__main__":
    # 输入服务器数量并启动相应数量的线程
    count = int(input('输入服务器数量：'))
    threads = []

    for i in range(count):
        server_thread = threading.Thread(target=run_server, args=(i,))
        threads.append(server_thread)
        server_thread.start()

