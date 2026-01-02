use std::io::Cursor;

use actix_web::Responder;
use actix_web::post;
use actix_web::web::Data;
use actix_web::web::Json;
use openraft::error::decompose::DecomposeResult;
use openraft::raft::SnapshotResponse;

use crate::app::App;
use crate::typ::*;
use crate::TypeConfig;

// --- Raft 内部 RPC 通信

#[post("/vote")]
pub async fn vote(app: Data<App>, req: Json<VoteRequest>) -> actix_web::Result<impl Responder> {
  let res = app.raft.vote(req.0).await.decompose().unwrap();
  Ok(Json(res))
}

#[post("/append")]
pub async fn append(
  app: Data<App>,
  req: Json<AppendEntriesRequest>,
) -> actix_web::Result<impl Responder> {
  let res = app.raft.append_entries(req.0).await.decompose().unwrap();
  Ok(Json(res))
}

#[post("/snapshot")]
pub async fn snapshot(
  app: Data<App>,
  req: Json<(Vote, SnapshotMeta, Vec<u8>)>,
) -> actix_web::Result<impl Responder> {
  let (vote_req, snapshot_meta, snapshot_data) = req.0;
  let snapshot = Snapshot {
    meta: snapshot_meta,
    snapshot: Cursor::new(snapshot_data),
  };
  let res: Result<SnapshotResponse<TypeConfig>, openraft::error::Fatal<TypeConfig>> = app
    .raft
    .install_full_snapshot(vote_req, snapshot)
    .await;
  Ok(Json(res))
}
