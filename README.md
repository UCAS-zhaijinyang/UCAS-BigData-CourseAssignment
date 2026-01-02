# UCAS 大数据课程作业项目

本项目是一个基于 Raft 共识算法的分布式键值存储系统，包含两个主要组件：`kv-store`（Rust 实现的 Raft 集群）和 `meta-server`（Python 实现的元数据服务器和客户端）。

## 项目代码结构

### 1. kv-store/ - Raft 分布式键值存储

基于 Rust 和 openraft 实现的分布式键值存储系统，使用 Raft 共识算法保证数据一致性。

#### 目录结构

```
kv-store/
├── Cargo.toml              # Rust 项目配置文件
├── Cargo.lock              # 依赖锁定文件
├── start.sh                # 启动脚本（启动3个节点）
├── test.sh                 # 测试脚本（完整的Raft集群测试）
└── src/
    ├── lib.rs              # 库入口，定义 Raft 类型和启动函数
    ├── app.rs              # App 结构体，包含节点信息和 Raft 实例
    ├── typ.rs              # 类型别名定义
    ├── bin/
    │   └── main.rs         # 可执行文件入口，解析命令行参数
    ├── network/             # 网络层实现
    │   ├── mod.rs          # 模块声明
    │   ├── api.rs          # 应用层 API（读写操作）
    │   ├── management.rs   # 集群管理 API（初始化、添加节点、改变成员关系等）
    │   └── raft.rs         # Raft 内部 RPC 通信（投票、追加日志、快照）
    ├── openraft_network/   # openraft 网络层实现
    │   └── mod.rs          # Raft 节点间通信的网络实现
    └── store/              # 存储层实现
        ├── mod.rs          # 存储模块，包含状态机和请求/响应定义
        └── log_store.rs    # 基于 RocksDB 的日志存储实现
```

#### 核心模块说明

- **lib.rs**: 定义了 `start_raft_node` 函数，用于启动一个 Raft 节点，配置 HTTP 服务器，注册各种 API 端点
- **app.rs**: `App` 结构体包含节点 ID、地址、Raft 实例、键值对存储和配置信息
- **network/api.rs**: 提供数据操作 API
  - `POST /write`: 写入操作（Put/Del）
  - `POST /read`: 读取单个键值
  - `GET /read-all`: 读取所有键值
- **network/management.rs**: 提供集群管理 API
  - `POST /init`: 初始化集群
  - `POST /add-learner`: 添加 learner 节点
  - `POST /change-membership`: 改变成员关系
  - `GET /metrics`: 查询集群状态
- **network/raft.rs**: Raft 内部 RPC 通信端点
  - `POST /append`: 追加日志条目
  - `POST /snapshot`: 安装快照
  - `POST /vote`: 投票请求
- **store/mod.rs**: 实现状态机存储，包括快照构建、日志应用等功能
- **store/log_store.rs**: 基于 RocksDB 的日志存储实现

### 2. meta-server/ - 元数据服务器和客户端

基于 Python 实现的元数据服务器系统，使用 XML-RPC 协议进行通信，提供对 kv-store 集群的访问接口。

#### 目录结构

```
meta-server/
├── requirements.txt        # Python 依赖包列表
├── api.md                  # API 文档
├── node_server.py          # 节点服务器实现
├── proxy_server.py         # 代理服务器实现
├── client.py               # 客户端实现
└── test_flask.py           # Flask 测试服务器（模拟 kv-store）
```

#### 核心文件说明

- **node_server.py**: 节点服务器实现
  - `Server` 类：提供键值操作（put、get、delete、list）
  - `add_learner`: 添加 Raft learner 节点
  - `change_membership`: 改变 Raft 集群成员关系
  - `metrics`: 查询 Raft 集群状态（格式化输出）
  - `get_log`: 获取操作日志
  - 使用 XML-RPC 服务器，每个节点运行在不同端口（20000+server_id）

- **proxy_server.py**: 代理服务器实现
  - `ProxyServer` 类：管理多个客户端连接
  - `get_id`: 分配客户端 ID
  - `function`: 解析并转发客户端命令
  - 支持的命令：PUT、GET、DEL、LIST、LOG、ADD-LEARNER、CHANGE-MEMBERSHIP、METRICS、EXIT
  - 提供用户认证功能
  - 运行在端口 21000

- **client.py**: 客户端实现
  - `Client` 类：客户端连接和命令处理
  - `connect`: 连接到代理服务器并认证
  - `handle_user_command`: 处理用户输入的命令
  - `send_command_to_server`: 向服务器发送命令

- **test_flask.py**: Flask 测试服务器
  - 模拟 kv-store 的 HTTP API
  - 用于测试 meta-server 功能
  - 运行在端口 21001

### 3. UCAS_beamer/ - 演示文稿

LaTeX Beamer 演示文稿相关文件（项目文档/报告）。

## 项目使用方法

### 前置要求

#### kv-store 部分

1. **安装 Rust 工具链**
   ```bash
   # 如果未安装 Rust，请访问 https://rustup.rs/ 安装
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
   ```

2. **添加 openraft 依赖**
   
   **重要**：在编译 kv-store 之前，需要先在 `kv-store` 文件夹下添加 openraft 项目。
   
   ```bash
   cd kv-store
   
   # 克隆 openraft 仓库到 kv-store 目录下
   git clone https://github.com/datafuselabs/openraft.git
   
   # 或者如果已有 openraft 项目，将其复制到 kv-store 目录下
   # 确保 openraft 目录结构为: kv-store/openraft/openraft/
   ```
   
   注意：`Cargo.toml` 中配置的依赖路径为 `./openraft/openraft`，因此需要确保 openraft 项目位于 `kv-store/openraft/` 目录下，且其主 crate 位于 `kv-store/openraft/openraft/`。

3. **安装系统依赖**
   - macOS: 可能需要安装 RocksDB 相关依赖
   - Linux: 可能需要安装 `librocksdb-dev` 等包

#### meta-server 部分

1. **安装 Python 3.7+**
   ```bash
   python3 --version  # 检查 Python 版本
   ```

2. **安装 Python 依赖**
   ```bash
   cd meta-server
   pip install -r requirements.txt
   # 或者使用 pip3
   pip3 install -r requirements.txt
   ```

### 使用步骤

#### 1. 启动 kv-store Raft 集群

**方式一：使用启动脚本（推荐）**

```bash
cd kv-store

# 确保已添加 openraft 依赖（见前置要求）

# 编译项目
cargo build

# 启动 3 个节点的 Raft 集群
chmod +x start.sh
./start.sh
```

`start.sh` 脚本会：
- 编译项目
- 清理旧的数据库文件和进程
- 启动 3 个 kv-store 节点（端口 21001、21002、21003）
- 初始化节点 1 作为单节点集群
- 显示节点 1 的日志

**运行测试脚本**

```bash
cd kv-store

# 运行完整的测试脚本（包括集群初始化、数据读写、故障恢复等）
chmod +x test.sh
./test.sh
```

#### 2. 启动 meta-server 系统

**启动节点服务器**

```bash
cd meta-server

# 运行节点服务器，输入服务器数量（例如：3）
python3 node_server.py
# 输入: 3
```

节点服务器会启动在端口 20000、20001、20002（对应 3 个服务器）。

**启动代理服务器**

在另一个终端：

```bash
cd meta-server

# 运行代理服务器，输入客户端数量（例如：3）
python3 proxy_server.py
# 输入: 3
```

代理服务器会运行在端口 21000。

**启动客户端**

在另一个终端：

```bash
cd meta-server

# 运行客户端
python3 client.py

# 输入用户名和密码（例如：用户名 1，密码 1）
# 输入命令进行操作
```

**支持的命令：**
- `PUT key value` - 添加/更新键值对
- `GET key` - 获取指定键的值
- `DEL key` - 删除指定键
- `LIST` - 显示所有键值对
- `LOG` - 获取操作日志
- `ADD-LEARNER node_id "api_addr"` - 添加 Raft learner 节点
- `CHANGE-MEMBERSHIP node_id1 node_id2 ...` - 改变 Raft 集群成员关系
- `METRICS` - 查询 Raft 集群状态
- `EXIT` - 退出客户端
- `HELP` - 显示帮助信息

#### 4. 使用测试服务器（可选）

如果需要测试 meta-server 而不启动完整的 kv-store 集群，可以使用 Flask 测试服务器：

```bash
cd meta-server

# 启动 Flask 测试服务器（模拟 kv-store API）
python3 test_flask.py
```

测试服务器会运行在 `http://127.0.0.1:21001`，提供与 kv-store 相同的 API 接口。

### 完整使用示例

1. **启动 kv-store 集群**
   ```bash
   cd kv-store
   cargo build
   ./start.sh
   ```

2. **在另一个终端启动 meta-server 节点服务器**
   ```bash
   cd meta-server
   python3 node_server.py
   # 输入: 3
   ```

3. **在另一个终端启动代理服务器**
   ```bash
   cd meta-server
   python3 proxy_server.py
   # 输入: 3
   ```

4. **在另一个终端启动客户端并操作**
   ```bash
   cd meta-server
   python3 client.py
   # 输入用户名: 1
   # 输入密码: 1
   # 输入命令: PUT hello world
   # 输入命令: GET hello
   # 输入命令: LIST
   # 输入命令: METRICS
   ```

### 注意事项

1. **kv-store 编译前必须添加 openraft 依赖**：在 `kv-store` 目录下需要存在 `openraft/openraft/` 目录结构，否则编译会失败。

2. **端口占用**：确保以下端口未被占用：
   - 21001, 21002, 21003: kv-store 节点
   - 21000: meta-server 代理服务器
   - 20000+: meta-server 节点服务器

3. **数据库文件**：kv-store 会在当前目录下创建数据库文件（格式：`127.0.0.1:端口.db`），停止服务后可以手动删除这些文件。

4. **日志输出**：kv-store 使用 `RUST_LOG` 环境变量控制日志级别，可以设置：
   ```bash
   export RUST_LOG=info  # 或 trace, debug, warn, error
   ```

5. **集群初始化**：首次启动 kv-store 集群时，需要先初始化一个节点作为单节点集群，然后逐步添加其他节点。

## 技术栈

- **kv-store**: Rust, openraft, RocksDB, Actix-web, Tokio
- **meta-server**: Python, XML-RPC, Flask, Requests

