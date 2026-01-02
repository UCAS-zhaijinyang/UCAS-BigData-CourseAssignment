use std::collections::BTreeMap;
use std::sync::Arc;

use openraft::Config;
use tokio::sync::RwLock;

use crate::NodeId;
use crate::typ::Raft;

pub struct App {
  pub id: NodeId,
  pub addr: String,
  pub raft: Raft,
  pub key_values: Arc<RwLock<BTreeMap<String, String>>>,
  pub config: Arc<Config>,
}
