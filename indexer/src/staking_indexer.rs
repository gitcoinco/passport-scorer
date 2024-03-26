use crate::{
    postgres::PostgresClient,
    utils::{create_rpc_connection, StakeAmountOperation, StakeEventType},
};
use ethers::{
    contract::{abigen, LogMeta},
    core::types::Address,
    providers::{Middleware, StreamExt},
};
use eyre::Result;
use futures::try_join;
use std::{
    cmp::{max, min},
    sync::Arc,
};

abigen!(IdentityStaking, "./src/IdentityStaking.json",);

pub struct StakingIndexer<'a> {
    postgres_client: PostgresClient,
    rpc_url: &'a String,
    chain_id: u32,
    start_block: u64,
    contract_address: &'a Address,
}

async fn get_chain_id(rpc_url: &String) -> Result<u32> {
    let client = create_rpc_connection(rpc_url).await;
    let chain_id = client.get_chainid().await?;
    Ok(chain_id.as_u32())
}

impl<'a> StakingIndexer<'a> {
    pub async fn new(
        postgres_client: PostgresClient,
        rpc_url: &'a String,
        start_block: u64,
        contract_address: &'a Address,
    ) -> Result<Self> {
        let chain_id = get_chain_id(rpc_url).await.unwrap();
        Ok(Self {
            postgres_client,
            rpc_url,
            chain_id,
            start_block,
            contract_address,
        })
    }

    pub async fn listen_with_timeout_reset(&self) -> Result<()> {
        loop {
            let start_block = self.postgres_client.get_latest_block(self.chain_id, self.start_block).await?;
            println!(
                "Debug - Starting indexer for chain {} at block {} at {}",
                self.chain_id, start_block, chrono::Utc::now()
            );

            match try_join!(
                self.throw_when_no_events_logged(&start_block),
                self.listen_for_stake_events(&start_block),
            ) {
                Ok(_) => {
                    eprintln!(
                        "Warning - indexer timeout join ended without error for chain {}",
                        self.chain_id
                    );
                }
                Err(err) => {
                    if err
                        .to_string()
                        .contains("No events logged in the last 15 minutes")
                    {
                        eprintln!("Warning - resetting indexer due to no events logged in the last 15 minutes for chain {}", self.chain_id);
                    } else {
                        eprintln!(
                            "Warning - indexer timeout join ended with error for chain {}, {:?}",
                            self.chain_id, err
                        );
                    }
                }
            }
        }
    }

    async fn throw_when_no_events_logged(&self, starting_event_block: &u64) -> Result<()> {
        let mut timer_begin_block = *starting_event_block;
        loop {
            // sleep for 15 minutes
            tokio::time::sleep(tokio::time::Duration::from_secs(900)).await;

            let latest_logged_block = self.postgres_client.get_latest_block(self.chain_id, self.start_block).await?;

            if latest_logged_block == timer_begin_block {
                return Err(eyre::eyre!(
                    "No events logged in the last 15 minutes for chain {}",
                    self.chain_id
                ));
            }

            timer_begin_block = latest_logged_block;
        }
    }

    async fn get_current_block(&self) -> Result<u64> {
        // Recreating client here because when this fails (with local hardhat node)
        // it ruins the client and we need to recreate it
        let client = create_rpc_connection(&self.rpc_url).await;
        let block_number = client.get_block_number().await?;
        Ok(block_number.as_u64())
    }

    async fn listen_for_stake_events(&self, query_start_block: &u64) -> Result<()> {
        let mut current_block: u64 = 2;
        if let Ok(block_number) = self.get_current_block().await {
            current_block = block_number;
        } else {
            eprintln!(
                "Warning - Failed to fetch current block number for chain {}",
                self.chain_id
            );
        }

        let client = Arc::new(create_rpc_connection(&self.rpc_url).await);

        let id_staking_contract = IdentityStaking::new(*self.contract_address, client.clone());

        let mut last_queried_block: u64 = *query_start_block;

        // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
        while last_queried_block < current_block - 1 {
            let query_end_block = min(last_queried_block + 2000, current_block - 1);
            let previous_events_query = id_staking_contract
                .events()
                .from_block(last_queried_block + 1)
                .to_block(query_end_block)
                .query_with_meta()
                .await;

            match previous_events_query {
                Ok(previous_events) => {
                    for (event, meta) in previous_events.iter() {
                        self.process_staking_event(&event, &meta, &client).await?;
                    }
                }
                Err(err) => {
                    eprintln!(
                        "Error - Failed to query events: {}, {}, {:?}",
                        last_queried_block, query_end_block, err
                    );
                }
            }
            last_queried_block = query_end_block;
        }

        eprintln!(
            "Debug - Finished querying past events for chain {}",
            self.chain_id
        );

        let future_events = id_staking_contract
            .events()
            .from_block(max(last_queried_block + 1, current_block));

        let mut stream = future_events.stream().await?.with_meta();

        eprintln!(
            "Debug - Listening for future events for chain {}",
            self.chain_id
        );

        while let Some(event_with_meta) = stream.next().await {
            let (event, meta) = match event_with_meta {
                Err(err) => {
                    eprintln!(
                        "Error - Failed to fetch IdentityStaking events for chain {}: {:?}",
                        self.chain_id, err
                    );
                    break;
                }
                Ok(event_with_meta) => event_with_meta,
            };

            self.process_staking_event(&event, &meta, &client).await?;
        }

        Ok(())
    }

    async fn process_staking_event(
        &self,
        event: &IdentityStakingEvents,
        meta: &LogMeta,
        client: &Arc<ethers::providers::Provider<ethers::providers::Ws>>,
    ) -> Result<()> {
        let block_number = meta.block_number.as_u64();
        let tx_hash = format!("{:?}", meta.transaction_hash);
        let block_timestamp = self.get_timestamp_for_block_number(block_number, client).await?;

        match event {
            IdentityStakingEvents::SelfStakeFilter(event) => {
                self.process_self_stake_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            IdentityStakingEvents::CommunityStakeFilter(event) => {
                self.process_community_stake_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            IdentityStakingEvents::SelfStakeWithdrawnFilter(event) => {
                self.process_self_stake_withdrawn_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            IdentityStakingEvents::CommunityStakeWithdrawnFilter(event) => {
                self.process_community_stake_withdrawn_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            IdentityStakingEvents::SlashFilter(event) => {
                self.process_slash_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            IdentityStakingEvents::ReleaseFilter(event) => {
                self.process_release_event(&event, block_number, &tx_hash, block_timestamp)
                    .await
            }
            _ => {
                eprintln!(
                    "Debug - Unhandled event in tx {} for chain {}",
                    tx_hash, self.chain_id
                );
                Ok(())
            }
        }
    }

    // Could cache this somehow to avoid checking timestamp multiple times
    // if there are multiple stake events in the same block
    async fn get_timestamp_for_block_number(
        &self,
        block_number: u64,
        client: &Arc<ethers::providers::Provider<ethers::providers::Ws>>,
    ) -> Result<u64> {
        if let Ok(Some(block)) = client.get_block(block_number).await {
            return Ok(block.timestamp.as_u64())
        }
        Err(eyre::eyre!(
            "Failed to fetch block timestamp for block {}",
            block_number
        ))
    }

    async fn process_self_stake_event(
        &self,
        event: &SelfStakeFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .add_or_extend_stake(
                &StakeEventType::SelfStake,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                &event.unlock_time,
                &block_timestamp,
                &block_number,
                tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process self stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_community_stake_event(
        &self,
        event: &CommunityStakeFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .add_or_extend_stake(
                &StakeEventType::CommunityStake,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                &event.unlock_time,
                &block_timestamp,
                &block_number,
                tx_hash,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process community stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_self_stake_withdrawn_event(
        &self,
        event: &SelfStakeWithdrawnFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::SelfStakeWithdraw,
                self.chain_id,
                &event.staker,
                &event.staker,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                tx_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process self stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_community_stake_withdrawn_event(
        &self,
        event: &CommunityStakeWithdrawnFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::CommunityStakeWithdraw,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                tx_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process community stake event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_slash_event(
        &self,
        event: &SlashFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::Slash,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                StakeAmountOperation::Subtract,
                &block_number,
                tx_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process slash event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }

    async fn process_release_event(
        &self,
        event: &ReleaseFilter,
        block_number: u64,
        tx_hash: &String,
        block_timestamp: u64,
    ) -> Result<()> {
        if let Err(err) = self
            .postgres_client
            .update_stake_amount(
                &StakeEventType::Release,
                self.chain_id,
                &event.staker,
                &event.stakee,
                &event.amount,
                StakeAmountOperation::Add,
                &block_number,
                tx_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!(
                "Error - Failed to process release event for chain {}: {:?}",
                self.chain_id, err
            );
        }
        Ok(())
    }
}
