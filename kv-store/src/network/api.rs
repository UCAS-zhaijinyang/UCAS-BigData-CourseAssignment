use actix_web::Responder;
use actix_web::get;
use actix_web::post;
use actix_web::web;
use actix_web::web::Data;
use openraft::error::Infallible;
use openraft::error::decompose::DecomposeResult;
use web::Json;

use crate::app::App;
use crate::store::Request;

#[post("/write")]
pub async fn write(app: Data<App>, req: Json<Request>) -> actix_web::Result<impl Responder> {
  // let _response = app.raft.client_write(req.0).await.decompose().unwrap();
  let response = app.raft.client_write(req.0).await.decompose().unwrap();
  match response {
      Ok(_) => Ok(Json("Ok")),
      Err(_) => Ok(Json("Err")),
  }
}

#[post("/read")]
pub async fn read(app: Data<App>, req: Json<String>) -> actix_web::Result<impl Responder> {
  let key = req.0;
  let kvs = app.key_values.read().await;
  let value = kvs.get(&key);

  let res: Result<String, Infallible> = Ok(value.cloned().unwrap_or_default());
  Ok(Json(res))
}

#[get("/read-all")]
pub async fn read_all(app: Data<App>) -> actix_web::Result<impl Responder> {
  let kvs = app.key_values.read().await;
  Ok(Json(kvs.clone()))
}
