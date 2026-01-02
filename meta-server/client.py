import xmlrpc.client as xmlrpclib


class Client(object):
    def __init__(self):
        self.id = None  # 客户端ID
        self.proxy = None  # XML-RPC代理
        self.port = None  # 连接端口

    def connect(self, username, password):
        self.port = '21000'
        self.proxy = xmlrpclib.ServerProxy('http://localhost:' + self.port)
        # 登录
        # 在此处进行验证 调用代理服务器的验证功能
        if self.proxy.authenticate(username, password):
            self.id = self.proxy.get_id()  # 从代理服务器获取客户端ID
            return self.id
        # 验证成功的处理逻辑
        else:
            print('登录失败，请检查用户名和密码。')
            return None

    def handle_user_command(self):
        try:
            while True:
                command = input(f"客户端 {self.id} 输入命令>> ").upper()
                if command == 'HELP':
                    self.print_help()  # 打印命令帮助
                else:
                    self.send_command_to_server(command)  # 向服务器发送命令
                    if command == 'EXIT':
                        break
        except KeyboardInterrupt:
            pass

    def print_help(self):
        # 打印命令帮助信息
        print(
            '-------------------------------------------\n'
            '命令帮助:\n'
            'PUT key value —— 添加 (key, value)\n'
            'GET key —— 获取指定 key 的值\n'
            'DEL key —— 删除指定 key 的值\n'
            'LIST —— 显示所有 (key, value)\n'
            'LOG —— 获取日志\n'
            'ADD-LEARNER node_id "api_addr" —— 添加raft节点作为learner\n'
            'CHANGE-MEMBERSHIP node_id1 node_id2 ... —— 改变节点关系\n'
            'METRICS —— 查询当前的raft集群状态\n'
            'EXIT —— 退出客户端\n'
            '-------------------------------------------'
        )

    def send_command_to_server(self, command):
        msg = getattr(self.proxy, 'function')(self.id, command)  # 向服务器发送命令并获取返回信息
        if msg is not None:
            print(msg)  # 打印服务器返回信息


if __name__ == '__main__':

    print("尝试登录...")
    username = input('输入用户名: ')
    password = input('输入密码: ')

    client = Client()
    # 验证用户名和密码是否匹配
    client_id = client.connect(username, password)  # 连接到服务器并获取客户端ID
    if client_id is None:
        print('连接失败，没有多余的用户ID可以分配。')
    else:
        # 登录成功，显示欢迎消息和客户端ID
        print('-------------------------------------------')
        print("登录成功。")
        print('欢迎使用分布式键值系统！')
        print(f'您的客户端ID是 {client_id}')
        print('输入 <help> 获取命令列表。')
        print('-------------------------------------------')
    client.handle_user_command()  # 处理用户命令

