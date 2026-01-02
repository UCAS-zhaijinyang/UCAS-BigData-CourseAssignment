use std::fmt::Display;

use openraft::BasicNode;
use openraft::ErrorSubject;
use openraft::ErrorVerb;
use openraft::OptionalSend;
use openraft::RaftTypeConfig;
use openraft::StorageError;
use openraft::error::Infallible;
use openraft::error::NetworkError;
use openraft::error::RPCError;
use openraft::error::ReplicationClosed;
use openraft::error::StreamingError;
use openraft::error::Unreachable;
use openraft::network::RPCOption;
use openraft::network::RaftNetworkFactory;
use openraft::network::v2::RaftNetworkV2;
use openraft::raft::AppendEntriesRequest;
use openraft::raft::AppendEntriesResponse;
use openraft::raft::SnapshotResponse;
use openraft::raft::VoteRequest;
use openraft::raft::VoteResponse;
use openraft::storage::Snapshot;
use openraft::type_config::alias::VoteOf;
use reqwest::Client;
use serde::Serialize;
use serde::de::DeserializeOwned;
use std::future::Future;
use tokio::io::AsyncRead;
use tokio::io::AsyncSeek;
use tokio::io::AsyncWrite;

pub struct NetworkFactory {}

impl<C> RaftNetworkFactory<C> for NetworkFactory
where
    C: RaftTypeConfig<Node = BasicNode>,
    <C as RaftTypeConfig>::SnapshotData: AsyncRead + AsyncWrite + AsyncSeek + Unpin,
{
    type Network = Network<C>;

    #[tracing::instrument(level = "debug", skip_all)]
    async fn new_client(&mut self, target: C::NodeId, node: &BasicNode) -> Self::Network {
        let addr = node.addr.clone();

        let client = Client::builder().no_proxy().build().unwrap();

        Network {
            addr,
            client,
            target,
        }
    }
}

pub struct Network<C>
where
    C: RaftTypeConfig,
{
    addr: String,
    client: Client,
    #[allow(dead_code)]
    target: C::NodeId,
}

impl<C> Network<C>
where
    C: RaftTypeConfig,
{
    async fn request<Req, Resp, Err>(
        &mut self,
        uri: impl Display,
        req: Req,
    ) -> Result<Result<Resp, Err>, RPCError<C>>
    where
        Req: Serialize + 'static,
        Resp: Serialize + DeserializeOwned,
        Err: std::error::Error + Serialize + DeserializeOwned,
    {
        let url = format!("http://{}/{}", self.addr, uri);
        // println!(
        //     ">>> network send request to {}: {}",
        //     url,
        //     serde_json::to_string_pretty(&req).unwrap()
        // );

        let resp = self
            .client
            .post(url.clone())
            .json(&req)
            .send()
            .await
            .map_err(|e| {
                if e.is_connect() {
                    // `Unreachable` informs the caller to backoff for a short while to avoid error log flush.
                    RPCError::Unreachable(Unreachable::new(&e))
                } else {
                    RPCError::Network(NetworkError::new(&e))
                }
            })?;

        let res: Result<Resp, Err> = resp.json().await.map_err(|e| NetworkError::new(&e))?;
        // println!(
        //     "<<< network recv reply from {}: {}",
        //     url,
        //     serde_json::to_string_pretty(&res).unwrap()
        // );

        Ok(res)
    }
}

#[allow(clippy::blocks_in_conditions)]
impl<C> RaftNetworkV2<C> for Network<C>
where
    C: RaftTypeConfig,
    <C as RaftTypeConfig>::SnapshotData: AsyncRead + AsyncWrite + AsyncSeek + Unpin,
{
    #[tracing::instrument(level = "debug", skip_all, err(Debug))]
    async fn append_entries(
        &mut self,
        req: AppendEntriesRequest<C>,
        _option: RPCOption,
    ) -> Result<AppendEntriesResponse<C>, RPCError<C>> {
        let res = self.request::<_, _, Infallible>("append", req).await?;
        Ok(res.unwrap())
    }

    #[tracing::instrument(level = "debug", skip_all, err(Debug))]
    async fn full_snapshot(
        &mut self,
        vote: VoteOf<C>,
        snapshot: Snapshot<C>,
        _cancel: impl Future<Output = ReplicationClosed> + OptionalSend + 'static,
        _option: RPCOption,
    ) -> Result<SnapshotResponse<C>, StreamingError<C>> {
        // Extract snapshot data for serialization
        // SnapshotData should be Cursor<Vec<u8>>, so we read it
        use tokio::io::AsyncReadExt;
        let mut snapshot_data = Vec::new();
        let mut reader = snapshot.snapshot;
        reader.read_to_end(&mut snapshot_data).await.map_err(|e| {
            StreamingError::StorageError(StorageError::from_io_error(
                ErrorSubject::Snapshot(None),
                ErrorVerb::Read,
                e,
            ))
        })?;

        let req = (vote, snapshot.meta, snapshot_data);
        let res = self
            .request::<_, _, Infallible>("snapshot", req)
            .await
            .map_err(|e| StreamingError::from(e))?;
        Ok(res.unwrap())
    }

    #[tracing::instrument(level = "debug", skip_all, err(Debug))]
    async fn vote(
        &mut self,
        req: VoteRequest<C>,
        _option: RPCOption,
    ) -> Result<VoteResponse<C>, RPCError<C>> {
        let res = self.request::<_, _, Infallible>("vote", req).await?;
        Ok(res.unwrap())
    }
}
