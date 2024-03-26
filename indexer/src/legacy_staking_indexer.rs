// For the old staking contract
// This can eventually be deleted, once we are ready to disable
// un-staking from the old contract in the new UI

use crate::{postgres::PostgresClient, utils::create_rpc_connection, LEGACY_CONTRACT_ADDRESS};
use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Middleware, StreamExt},
};
use eyre::Result;
use futures::try_join;
use std::sync::Arc;

abigen!(
    IDStaking,
    r#"[
        event selfStake(uint256 roundId,address staker,uint256 amount,bool staked)
        event xStake(uint256 roundId,address staker,address user,uint256 amount,bool staked)
        event tokenMigrated(address staker,uint256 amount,uint256 fromRound,uint256 toRound)
        event roundCreated(uint256 id)
        event RoleAdminChanged(bytes32 indexed role, bytes32 indexed previousAdminRole, bytes32 indexed newAdminRole)
        event RoleGranted(bytes32 indexed role, address indexed account, address indexed sender)
        event RoleRevoked(bytes32 indexed role, address indexed account, address indexed sender)
    ]"#,
);

pub struct LegacyStakingIndexer<'a> {
    postgres_client: PostgresClient,
    rpc_url: &'a String,
}

impl<'a> LegacyStakingIndexer<'a> {
    pub fn new(postgres_client: PostgresClient, rpc_url: &'a String) -> Self {
        Self {
            postgres_client,
            rpc_url,
        }
    }

    pub async fn listen_with_timeout_reset(&self) -> Result<()> {
        loop {
            let start_block = self.postgres_client.get_latest_block_legacy().await?;

            match try_join!(
                self.throw_when_no_events_logged(&start_block),
                self.listen_for_stake_events(&start_block),
            ) {
                Ok(_) => {
                    eprintln!("Warning - legacy indexer timeout join ended without error");
                }
                Err(err) => {
                    if err
                        .to_string()
                        .contains("No events logged in the last 15 minutes")
                    {
                        eprintln!("Warning - resetting legacy indexer due to no events logged in the last 15 minutes");
                    } else {
                        eprintln!(
                            "Warning - legacy indexer timeout join ended with error, {}",
                            err
                        );
                    }
                }
            }
        }
    }

    async fn throw_when_no_events_logged(&self, starting_event_block: &i32) -> Result<()> {
        let mut start_block = *starting_event_block;
        loop {
            // sleep for 15 minutes
            tokio::time::sleep(tokio::time::Duration::from_secs(900)).await;

            let latest_logged_block = self.postgres_client.get_latest_block_legacy().await?;

            if latest_logged_block == start_block {
                return Err(eyre::eyre!("No events logged in the last 15 minutes"));
            }

            start_block = latest_logged_block;
        }
    }

    async fn get_timestamp_for_block_number(
        &self,
        block_number: u64,
        client: &Arc<ethers::providers::Provider<ethers::providers::Ws>>,
    ) -> Result<u64> {
        if let Ok(Some(block)) = client.get_block(block_number).await {
            return Ok(block.timestamp.as_u64());
        }
        Err(eyre::eyre!(
            "Failed to fetch block timestamp for block {}",
            block_number
        ))
    }

    async fn listen_for_stake_events(&self, query_start_block: &i32) -> Result<()> {
        let client = Arc::new(create_rpc_connection(&self.rpc_url).await);

        let id_staking_address = LEGACY_CONTRACT_ADDRESS.parse::<Address>().unwrap();

        let id_staking_contract = IDStaking::new(id_staking_address, client.clone());

        let current_block = client.get_block_number().await?;

        let mut last_queried_block: u32 = (*query_start_block)
            .try_into()
            .expect("Block number out of range");

        // Increment the last queried block by 1 to avoid querying the same block twice
        last_queried_block = last_queried_block + 1;

        // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
        while last_queried_block < current_block.as_u32() {
            let next_block_range = last_queried_block.clone() + 2000;
            let previous_events_query = id_staking_contract
                .events()
                .from_block(last_queried_block)
                .to_block(next_block_range)
                .query_with_meta()
                .await;

            match previous_events_query {
                Ok(previous_events) => {
                    for (event, meta) in previous_events.iter() {
                        match event {
                            IDStakingEvents::SelfStakeFilter(event) => {
                                let block_number = meta.block_number.as_u32();
                                let tx_hash = format!("{:?}", meta.transaction_hash);
                                let block_timestamp = self
                                    .get_timestamp_for_block_number(block_number as u64, &client)
                                    .await?;

                                self.format_and_save_self_stake_event(
                                    &event,
                                    block_number,
                                    tx_hash,
                                    block_timestamp,
                                )
                                .await?;
                            }
                            IDStakingEvents::XstakeFilter(event) => {
                                let block_number = meta.block_number.as_u32();
                                let tx_hash = format!("{:?}", meta.transaction_hash);
                                let block_timestamp = self
                                    .get_timestamp_for_block_number(block_number as u64, &client)
                                    .await?;
                                self.format_and_save_x_stake_event(
                                    &event,
                                    block_number,
                                    tx_hash,
                                    block_timestamp,
                                )
                                .await?;
                            }
                            _ => {
                                // Catch all for unhandled events
                            }
                        }
                    }
                }
                Err(err) => {
                    eprintln!(
                        "Error - Failed to query legacy events: {}, {}, {}",
                        err, last_queried_block, next_block_range
                    );
                }
            }
            last_queried_block = next_block_range;
        }

        eprintln!("Debug - Finished querying past legacy events");

        let future_events = id_staking_contract.events().from_block(current_block);

        let mut stream = future_events.stream().await?.with_meta();

        eprintln!("Debug - Listening for future legacy events");

        while let Some(event) = stream.next().await {
            let (event_value, meta) = match event {
                Err(err) => {
                    eprintln!("Error - Failed to fetch legacy IDStaking events: {}", err);
                    break;
                }
                Ok(event) => event,
            };

            let block_number = meta.block_number.as_u32();
            let tx_hash = format!("{:?}", meta.transaction_hash);
            let block_timestamp = self
                .get_timestamp_for_block_number(block_number as u64, &client)
                .await?;

            match event_value {
                IDStakingEvents::SelfStakeFilter(event_value) => {
                    self.format_and_save_self_stake_event(&event_value, block_number, tx_hash, block_timestamp)
                        .await?
                }
                IDStakingEvents::XstakeFilter(event_value) => {
                    self.format_and_save_x_stake_event(&event_value, block_number, tx_hash, block_timestamp)
                        .await?
                }
                _ => {
                    eprintln!("Debug - Unhandled event in legacy tx {}", tx_hash);
                }
            }
        }

        Ok(())
    }

    pub async fn format_and_save_self_stake_event(
        &self,
        event: &SelfStakeFilter,
        block_number: u32,
        transaction_hash: String,
        block_timestamp: u64,
    ) -> Result<()> {
        let round_id = event.round_id.as_u32();

        // Convert H160 and U256 to String
        let staker_str = format!("{:?}", event.staker);

        let amount_str = format!("{}", event.amount);

        let staked = event.staked;
        if let Err(err) = self
            .postgres_client
            .insert_into_combined_stake_filter_self_stake_legacy(
                round_id.try_into().unwrap(),
                &staker_str,
                &amount_str,
                staked,
                block_number.try_into().unwrap(),
                &transaction_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!("Error - Failed to insert legacy SelfStakeFilter: {}", err);
        }
        Ok(())
    }

    async fn format_and_save_x_stake_event(
        &self,
        event: &XstakeFilter,
        block_number: u32,
        transaction_hash: String,
        block_timestamp: u64,
    ) -> Result<()> {
        // Convert U256 to i32 for round_id
        // Be cautious about overflow, and implement a proper check if necessary
        let round_id_i32 = event.round_id.low_u32() as i32;

        // Convert H160 to String for staker and user
        let staker_str = format!("{:?}", event.staker);
        let user_str = format!("{:?}", event.user);
        // Convert U256 to String for amount
        let amount_str = format!("{}", event.amount);

        // Dereference the bool (if needed)
        let staked = event.staked;

        if let Err(err) = self
            .postgres_client
            .insert_into_combined_stake_filter_xstake_legacy(
                round_id_i32,
                &staker_str,
                &user_str,
                &amount_str,
                staked,
                block_number.try_into().unwrap(),
                &transaction_hash,
                block_timestamp,
            )
            .await
        {
            eprintln!("Error - Failed to insert legacy XstakeFilter: {}", err);
        }
        Ok(())
    }
}
