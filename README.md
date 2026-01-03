# UCAS [大数据技术](https://jwcg.ucas.ac.cn/public/courseOutlines?courseId=294920)大作业 2025 fall

本项目是一个基于 Raft 共识算法的分布式键值存储系统，包含两个组件：`kv-store`（Rust 实现的 Raft 集群）和 `meta-server`（Python 实现的元数据服务器和客户端）。

## 项目代码结构

### 1. kv-store/

#### 目录结构

```
kv-store/
├── Cargo.toml              # Rust 项目配置文件
├── Cargo.lock              # 依赖锁定文件
├── start.sh                # 启动脚本（启动3个节点）
├── test.sh                 # 测试脚本（完整的Raft集群测试）
├── clean.sh                # 清除临时文件
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

### 2. meta-server/

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

### 3. ppt/

使用 latex 写的 ppt，产物格式为 `.pdf`.

## 项目使用方法

### 使用步骤

#### 1. 启动 kv-store Raft 集群

```bash
cd kv-store

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

#### 2. 启动 meta-server 系统

```bash
cd meta-server
pip install -r requirements.txt

# 运行节点服务器，输入服务器数量（例如：3）
#节点服务器会启动在端口 20000、20001、20002（对应 3 个服务器）。
python3 node_server.py
# 输入: 3

# 新建终端
# 运行代理服务器，输入客户端数量（例如：3）
# 代理服务器会运行在端口 21000。
python3 proxy_server.py

# 新建终端
# 运行客户端
cd meta-server
python3 client.py
# 输入用户名和密码（例如：用户名 1，密码 1）
# 输入命令进行操作
```

#### 3. 测试

##### kv-store

```bash
cd kv-store

# 运行完整的测试脚本（包括集群初始化、数据读写、故障恢复等）
chmod +x test.sh
./test.sh
```

##### meta-server

```bash
cd meta-server

# 启动 Flask 测试服务器（模拟 kv-store API）
python3 test_flask.py
```

测试服务器会运行在 `http://127.0.0.1:21001`，提供与 kv-store 相同的 API 接口。

### 注意事项

1. **端口占用**：确保以下端口未被占用：
   - 21001, 21002, 21003: kv-store 节点
   - 21000: meta-server 代理服务器
   - 20000+: meta-server 节点服务器

2. **临时文件**：kv-store 会在当前目录下创建数据库文件（格式：`127.0.0.1:端口.db`），停止服务后可以手动删除这些文件。日志文件为 `n*.log`。

3. **日志输出**：kv-store 使用 `RUST_LOG` 环境变量控制日志级别，可以设置：
   ```bash
   export RUST_LOG=info  # start.sh:  trace, debug, warn, error
   ```

## 技术栈与参考

- **kv-store**: Rust, openraft, RocksDB, Actix-web, Tokio
- **meta-server**: Python, XML-RPC, Flask, Requests

[openraft](https://github.com/databendlabs/openraft)
[csdn](https://blog.csdn.net/m0_60947585/article/details/135314293)
