use std::error::Error;
use std::fmt::Debug;
use std::io;
use std::marker::PhantomData;
use std::ops::RangeBounds;
use std::sync::Arc;

use byteorder::BigEndian;
use byteorder::ReadBytesExt;
use byteorder::WriteBytesExt;

use meta::StoreMeta;

use openraft::LogState;
use openraft::OptionalSend;
use openraft::RaftLogReader;
use openraft::RaftTypeConfig;
use openraft::TokioRuntime;
use openraft::alias::EntryOf;
use openraft::alias::LogIdOf;
use openraft::alias::VoteOf;
use openraft::entry::RaftEntry;
use openraft::storage::IOFlushed;
use openraft::storage::RaftLogStorage;

// rocksdb
use rocksdb::ColumnFamily;
use rocksdb::DB;
use rocksdb::Direction;

use tokio::task::spawn_blocking;

#[derive(Debug, Clone)]
pub struct RocksLogStore<C>
where
  C: RaftTypeConfig,
{
  db: Arc<DB>,
  _p: PhantomData<C>,
}

impl<C> RocksLogStore<C>
where
  C: RaftTypeConfig,
{
  pub fn new(db: Arc<DB>) -> Self {
    // 确保 RocksDB column family：`meta` 用于存储元数据，`logs` 用于存储日志条目
    db.cf_handle("meta")
      .expect("column family `meta` not found");
    db.cf_handle("logs")
      .expect("column family `logs` not found");

    Self {
      db,
      _p: Default::default(),
    }
  }

  fn cf_meta(&self) -> &ColumnFamily {
    self.db.cf_handle("meta").unwrap()
  }

  fn cf_logs(&self) -> &ColumnFamily {
    self.db.cf_handle("logs").unwrap()
  }

  fn get_meta<M: StoreMeta<C>>(&self) -> Result<Option<M::Value>, io::Error> {
    // 从 RocksDB 的 `meta` column family 读取元数据
    let bytes = self
      .db
      .get_cf(self.cf_meta(), M::KEY)
      .map_err(|e| io::Error::other(e.to_string()))?;

    // key 不存在时返回 None
    let Some(bytes) = bytes else {
      return Ok(None);
    };

    let t =
      serde_json::from_slice(&bytes).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

    Ok(Some(t))
  }

  fn put_meta<M: StoreMeta<C>>(&self, value: &M::Value) -> Result<(), io::Error> {
    // 将元数据序列化，并写入元数据 meta
    let json_value =
      serde_json::to_vec(value).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?;

    self
      .db
      .put_cf(self.cf_meta(), M::KEY, json_value)
      .map_err(|e| io::Error::other(e.to_string()))?;

    Ok(())
  }
}

impl<C> RaftLogReader<C> for RocksLogStore<C>
where
  C: RaftTypeConfig,
{
  async fn try_get_log_entries<RB: RangeBounds<u64> + Clone + Debug + OptionalSend>(
    &mut self,
    range: RB,
  ) -> Result<Vec<C::Entry>, io::Error> {
    let start = match range.start_bound() {
      std::ops::Bound::Included(x) => id_to_bin(*x),
      std::ops::Bound::Excluded(x) => id_to_bin(*x + 1),
      std::ops::Bound::Unbounded => id_to_bin(0),
    };

    let mut res = Vec::new();

    // 从 `logs` column family，从 start 向前迭代，按字典序获取日志条目
    let it = self.db.iterator_cf(
      self.cf_logs(),
      rocksdb::IteratorMode::From(&start, Direction::Forward),
    );
    for item_res in it {
      let (id, val) = item_res.map_err(read_logs_err)?;

      let id = bin_to_id(&id);
      if !range.contains(&id) {
        break;
      }

      let entry: EntryOf<C> = serde_json::from_slice(&val).map_err(read_logs_err)?;

      // assert_eq!(id, entry.index());
      res.push(entry);
    }
    Ok(res)
  }

  async fn read_vote(&mut self) -> Result<Option<VoteOf<C>>, io::Error> {
    self.get_meta::<meta::Vote>()
  }
}

impl<C> RaftLogStorage<C> for RocksLogStore<C>
where
  C: RaftTypeConfig<AsyncRuntime = TokioRuntime>,
{
  type LogReader = Self;

  async fn get_log_state(&mut self) -> Result<LogState<C>, io::Error> {
    // 获取数据库中最后一个日志条目以确定 last_log_id
    let last = self
      .db
      .iterator_cf(self.cf_logs(), rocksdb::IteratorMode::End)
      .next();

    let last_log_id = match last {
      None => None,
      Some(res) => {
        let (_log_index, entry_bytes) = res.map_err(read_logs_err)?;
        let ent = serde_json::from_slice::<EntryOf<C>>(&entry_bytes).map_err(read_logs_err)?;
        Some(ent.log_id())
      }
    };

    // last_purged_log_id 存储在 meta 中，表示已经被清理（purge）的最大 log id
    let last_purged_log_id = self.get_meta::<meta::LastPurged>()?;

    // 如果没有日志文件（last_log_id 为 None），则使用 last_purged_log_id 作为 last_log_id
    let last_log_id = match last_log_id {
      None => last_purged_log_id.clone(),
      Some(x) => Some(x),
    };

    Ok(LogState {
      last_purged_log_id,
      last_log_id,
    })
  }

  async fn get_log_reader(&mut self) -> Self::LogReader {
    self.clone()
  }

  async fn save_vote(&mut self, vote: &VoteOf<C>) -> Result<(), io::Error> {
    // 将投票写入
    self.put_meta::<meta::Vote>(vote)?;

    // 在返回前把 vote 持久化到磁盘
    let db = self.db.clone();
    spawn_blocking(move || db.flush_wal(true))
      .await
      .map_err(|e| io::Error::other(e.to_string()))?
      .map_err(|e| io::Error::other(e.to_string()))?;

    Ok(())
  }

  async fn append<I>(&mut self, entries: I, callback: IOFlushed<C>) -> Result<(), io::Error>
  where
    I: IntoIterator<Item = EntryOf<C>> + Send,
  {
    // 将传入的每个 entry 写入 `logs` 列族
    for entry in entries {
      let id = id_to_bin(entry.index());
      self
        .db
        .put_cf(
          self.cf_logs(),
          id,
          serde_json::to_vec(&entry).map_err(|e| io::Error::new(io::ErrorKind::InvalidData, e))?,
        )
        .map_err(|e| io::Error::other(e.to_string()))?;
    }

    let db = self.db.clone();
    let handle = spawn_blocking(move || {
      let res = db.flush_wal(true).map_err(io::Error::other);
      callback.io_completed(res);
    });
    drop(handle);

    Ok(())
  }

  async fn truncate(&mut self, log_id: LogIdOf<C>) -> Result<(), io::Error> {
    tracing::debug!("truncate: [{:?}, +oo)", log_id);
    let from = id_to_bin(log_id.index());
    let to = id_to_bin(u64::MAX);
    self
      .db
      .delete_range_cf(self.cf_logs(), &from, &to)
      .map_err(|e| io::Error::other(e.to_string()))?;

    Ok(())
  }

  async fn purge(&mut self, log_id: LogIdOf<C>) -> Result<(), io::Error> {
    tracing::debug!("delete_log: [0, {:?}]", log_id);
    // 在物理删除日志前，先写入 meta 中的 last_purged_log_id
    self.put_meta::<meta::LastPurged>(&log_id)?;

    // 删除 [0, log_id] 日志数据
    let from = id_to_bin(0);
    let to = id_to_bin(log_id.index() + 1);
    self
      .db
      .delete_range_cf(self.cf_logs(), &from, &to)
      .map_err(|e| io::Error::other(e.to_string()))?;

    Ok(())
  }
}

/// raft store 的元数据
mod meta {
  use openraft::RaftTypeConfig;
  use openraft::alias::LogIdOf;
  use openraft::alias::VoteOf;

  /// 在 raft 里，除了 log 和状态机需要保存，raft store 自身的元数据也需要管理
  pub(crate) trait StoreMeta<C>
  where
    C: RaftTypeConfig,
  {
    const KEY: &'static str;

    type Value: serde::Serialize + serde::de::DeserializeOwned;
  }

  pub(crate) struct LastPurged {}
  pub(crate) struct Vote {}

  impl<C> StoreMeta<C> for LastPurged
  where
    C: RaftTypeConfig,
  {
    // 已经被 store 清理掉的最后一条日志的 ID
    const KEY: &'static str = "last_purged_log_id";
    type Value = LogIdOf<C>;
  }
  impl<C> StoreMeta<C> for Vote
  where
    C: RaftTypeConfig,
  {
    // 当前的 term 和投票给的候选人的 ID
    const KEY: &'static str = "vote";
    type Value = VoteOf<C>;
  }
}

fn id_to_bin(id: u64) -> Vec<u8> {
  let mut buf = Vec::with_capacity(8);
  buf.write_u64::<BigEndian>(id).unwrap();
  buf
}

fn bin_to_id(buf: &[u8]) -> u64 {
  (&buf[0..8]).read_u64::<BigEndian>().unwrap()
}

fn read_logs_err(e: impl Error + 'static) -> io::Error {
  io::Error::other(e.to_string())
}
