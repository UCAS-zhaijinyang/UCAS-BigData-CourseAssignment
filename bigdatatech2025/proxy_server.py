from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client as xmlrpclib


class ProxyServer:
    def __init__(self, client_count):
        # 用户名和密码
        self.users = {
            '1': '1',
            '2': '2',
            '3': '3',
        }
        # 初始化代理服务器，设置客户端连接状态和服务器列表
        self.client_ids = [False] * client_count  # 用于标记客户端是否连接的列表
        # 连接到不同的服务器节点，服务器的基地址是20000
        self.servers = [xmlrpclib.ServerProxy(f'http://localhost:{20000 + i}') for i in range(client_count)]

    # 分配客户端ID
    def get_id(self):
        for i, connected in enumerate(self.client_ids):
            if not connected:
                self.client_ids[i] = True
                print(f'客户端 {i} 登录')
                return i
        print('没有可用的 ID')
        return None

    # 处理客户端发来的命令
    def function(self, client_id, clause):
        print(clause)
        clause = clause.lower().strip().split()  # 解析命令
        lens = len(clause)

        if lens < 1:
            return '错误的命令。输入 help 查看帮助信息。'

        command = clause[0]

        # 检查命令类型
        if command in ['put', 'get', 'del', 'list', 'log', 'exit', 'add-learner', 'change-membership', 'metrics']:
            # 将命令转换为方法名
            if command == 'del':
                method_name = 'delete'
            elif command == 'add-learner':
                method_name = 'add_learner'
            elif command == 'change-membership':
                method_name = 'change_membership'
            else:
                method_name = command  # 其他命令直接使用命令名
            # 获取对应的方法
            server_function = getattr(self, method_name)
            return server_function(client_id, clause)
        else:
            return '错误的命令。输入 help 查看帮助信息。'

    # 处理客户端退出命令
    def exit(self, client_id, clause):
        self.client_ids[client_id] = False
        print(f'客户端 {client_id} 退出')
        return f'客户端 {client_id} 退出'

    # 实现PUT方法
    def put(self, client_id, clause):
        if len(clause) != 3:
            return '错误的命令格式。使用方法: PUT key value'

        key, value = clause[1], clause[2]
        # 检查key是否已存在，以区分添加和更新操作
        # get方法返回的是{"Ok": "value"}中的value部分，如果键不存在返回空字符串""
        existing_value = self.servers[client_id].get(key)
        # 判断第二个值（{"Ok": "value"}中的value）是否为空
        if existing_value and existing_value != "":
            action = "更新"
            old_value_info = f"（原值：{existing_value}）"
        else:
            action = "添加"
            old_value_info = ""
        
        if self.servers[client_id].put(key, value, action):
            return f"✓ 成功{action}键值对：{key} = {value} {old_value_info}"
        return f"✗ 无法{action}键值对：{key} = {value}"

    # 实现GET方法
    def get(self, client_id, clause):
        if len(clause) != 2:
            return '错误的命令格式。使用方法: GET key'

        key = clause[1]
        value = self.servers[client_id].get(key)
        # 判断返回的值是否为空（None或空字符串）
        if value is not None and value != "":
            return f"✓ 找到键值对：{key} = {value}"
        else:
            return f"✗ 未找到键：{key}"

    # 实现LIST方法
    def list(self, client_id, clause):
        if len(clause) != 1:
            return '错误的命令格式。使用方法: LIST'

        result = self.servers[client_id].list()
        # 格式化LIST输出
        return self._format_list_output(result)
    
    def _format_list_output(self, data):
        # 格式化LIST命令的输出
        if not data:
            return "数据库为空，没有任何键值对"
        
        # 处理不同的响应格式
        if isinstance(data, dict):
            # 检查是否是 {"OK": [...]} 格式
            if "OK" in data:
                items = data["OK"]
            elif "Ok" in data:
                items = data["Ok"]
            else:
                # 如果不是标准格式，尝试直接使用
                items = data
        elif isinstance(data, list):
            items = data
        else:
            return f"数据格式：{data}"
        
        if not items or (isinstance(items, list) and len(items) == 0):
            return "数据库为空，没有任何键值对"
        
        result_lines = []
        result_lines.append("=" * 60)
        result_lines.append("所有键值对")
        result_lines.append("=" * 60)
        
        # 处理列表格式
        if isinstance(items, list):
            for i, item in enumerate(items, 1):
                if isinstance(item, dict):
                    key = item.get("k", item.get("key", "N/A"))
                    value = item.get("v", item.get("value", "N/A"))
                    result_lines.append(f"{i}. {key} = {value}")
                else:
                    result_lines.append(f"{i}. {item}")
        # 处理字典格式
        elif isinstance(items, dict):
            for i, (key, value) in enumerate(items.items(), 1):
                result_lines.append(f"{i}. {key} = {value}")
        
        result_lines.append("=" * 60)
        result_lines.append(f"总计：{len(items) if isinstance(items, (list, dict)) else 1} 个键值对")
        
        return "\n".join(result_lines)

    # 实现DELETE方法
    def delete(self, client_id, clause):
        if len(clause) != 2:
            return '错误的命令格式。使用方法: DEL key'

        key = clause[1]
        # 先检查键是否存在
        existing_value = self.servers[client_id].get(key)
        if not existing_value or existing_value == "":
            return f"✗ 删除失败：键 {key} 不存在"
        
        # 键存在，执行删除
        if self.servers[client_id].delete(key):
            return f"✓ 成功删除键 {key}（原值：{existing_value}）"
        return f"✗ 删除键 {key} 失败"

    # 实现LOG方法
    def log(self, client_id, clause):
        if len(clause) != 1:
            return '错误的命令格式。使用方法: LOG'

        log_data = self.servers[client_id].get_log()
        # 格式化LOG输出
        return self._format_log_output(log_data)
    
    def _format_log_output(self, log_data):
        # 格式化LOG命令的输出
        if not log_data:
            return "日志为空，暂无操作记录"
        
        if isinstance(log_data, list):
            if len(log_data) == 0:
                return "日志为空，暂无操作记录"
            
            result_lines = []
            result_lines.append("=" * 60)
            result_lines.append("服务器操作日志")
            result_lines.append("=" * 60)
            
            for i, log_entry in enumerate(log_data, 1):
                result_lines.append(f"{i}. {log_entry}")
            
            result_lines.append("=" * 60)
            result_lines.append(f"总计：{len(log_data)} 条日志记录")
            
            return "\n".join(result_lines)
        else:
            return f"日志数据：{log_data}"

    # 实现ADD-LEARNER方法
    def add_learner(self, client_id, clause):
        # 格式: ADD-LEARNER node_id api_addr
        # 例如: ADD-LEARNER 2 "127.0.0.1:21002"
        if len(clause) != 3:
            return '错误的命令格式。使用方法: ADD-LEARNER node_id "api_addr"'
        
        try:
            node_id = int(clause[1])
            api_addr = clause[2].strip('"\'')  # 移除引号
            
            # 调用第一个服务器节点（通常是leader）来添加learner
            result = self.servers[0].add_learner(node_id, api_addr)
            # 检查响应中是否包含 "Ok" 键，如果包含则说明操作成功
            if result is not None and isinstance(result, dict) and "Ok" in result:
                return f"✓ 成功添加learner节点：节点ID={node_id}，地址={api_addr}"
            return f"✗ 无法添加learner节点：节点ID={node_id}，地址={api_addr}"
        except ValueError:
            return f"✗ 错误：node_id必须是整数，收到: {clause[1]}"
        except Exception as e:
            return f"✗ 添加learner节点时出错：{str(e)}"

    # 实现CHANGE-MEMBERSHIP方法
    def change_membership(self, client_id, clause):
        # 格式: CHANGE-MEMBERSHIP node_id1 node_id2 ...
        # 例如: CHANGE-MEMBERSHIP 1 2 3
        if len(clause) < 2:
            return '错误的命令格式。使用方法: CHANGE-MEMBERSHIP node_id1 node_id2 ...'
        
        try:
            node_ids = [int(node_id) for node_id in clause[1:]]
            
            # 调用第一个服务器节点（通常是leader）来改变成员关系
            result = self.servers[0].change_membership(node_ids)
            # 检查响应中是否包含 "Ok" 键，如果包含则说明操作成功
            if result is not None and isinstance(result, dict) and "Ok" in result:
                return f"✓ 成功改变成员关系：新成员节点列表 = {node_ids}"
            return f"✗ 无法改变成员关系：节点列表 = {node_ids}"
        except ValueError:
            return f"✗ 错误：所有node_id必须是整数"
        except Exception as e:
            return f"✗ 改变成员关系时出错：{str(e)}"

    # 实现METRICS方法
    def metrics(self, client_id, clause):
        # 格式: METRICS
        if len(clause) != 1:
            return '错误的命令格式。使用方法: METRICS'
        
        try:
            # 调用第一个服务器节点（通常是leader）来获取metrics
            result = self.servers[0].metrics()
            if result is not None:
                # result 已经是格式化后的字符串（由 node_server.py 的 _format_metrics 方法处理）
                return result
            return "无法获取集群状态"
        except Exception as e:
            return f"获取集群状态时出错: {str(e)}"

    # 登陆验证
    def authenticate(self, username, password):
        if username not in self.users:
            print('不存在该用户名，请重试！')
            return False
        elif self.users[username] != password:
            print('密码错误，请重试！')
            return False
        else:
            return True


if __name__ == '__main__':
    count = int(input('输入客户端数量: '))
    proxy = ProxyServer(client_count=count)
    server = SimpleXMLRPCServer(('localhost', 21000), allow_none=True)
    server.register_instance(proxy)

    print(f"代理服务器正在运行...")
    server.serve_forever()

