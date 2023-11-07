mod postgres;

use dotenv::dotenv;
use ethers::{
    contract::abigen,
    core::types::Address,
    providers::{Middleware, Provider, StreamExt, Ws},
};
use eyre::Result;
use futures::try_join;
use postgres::PostgresClient;
use std::{env, sync::Arc};

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

pub const CONTRACT_START_BLOCK: i32 = 16403024;

async fn format_and_save_self_stake_event(
    event: &SelfStakeFilter,
    block_number: u32,
    transaction_hash: String,
    postgres_client: &PostgresClient,
) -> Result<()> {
    let round_id = event.round_id.as_u32();

    // Convert H160 and U256 to String
    let staker_str = format!("{:?}", event.staker);

    let amount_str = format!("{}", event.amount);

    let staked = event.staked;
    if let Err(err) = postgres_client
        .insert_into_combined_stake_filter_self_stake(
            round_id.try_into().unwrap(),
            &staker_str,
            &amount_str,
            staked,
            block_number.try_into().unwrap(),
            &transaction_hash,
        )
        .await
    {
        eprintln!("Error - Failed to insert SelfStakeFilter: {}", err);
    }
    Ok(())
}

async fn format_and_save_x_stake_event(
    event: &XstakeFilter,
    block_number: u32,
    transaction_hash: String,
    postgres_client: &PostgresClient,
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

    if let Err(err) = postgres_client
        .insert_into_combined_stake_filter_xstake(
            round_id_i32,
            &staker_str,
            &user_str,
            &amount_str,
            staked,
            block_number.try_into().unwrap(),
            &transaction_hash,
        )
        .await
    {
        eprintln!("Error - Failed to insert XstakeFilter: {}", err);
    }
    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    let get_env = |var| {
        env::var(var).map_err(|_| panic!("Required environment variable \"{}\" not set", var))
    };

    let rpc_url = get_env("RPC_URL").unwrap();

    let database_url = get_env("DATABASE_URL").unwrap();

    let postgres_client = PostgresClient::new(&database_url).await?;

    try_join!(f1, f2)?;

    Ok(())
}

async fn listen_for_blocks(rpc_url: &str) -> Result<()> {
    let provider = Provider::<Ws>::connect(rpc_url).await?;

    let mut stream = provider.subscribe_blocks().await?;

    while let Some(block) = stream.next().await {
        println!(
            "New Block - timestamp: {:?}, number: {}, hash: {:?}",
            block.timestamp,
            block.number.unwrap(),
            block.hash.unwrap()
        );
    }

    return Ok(());
}

async fn listen_for_stake_events(rpc_url: &str, database_url: &str) -> Result<()> {
    let provider = Provider::<Ws>::connect(rpc_url).await?;

    let id_staking_address = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F".parse::<Address>()?;
    let client = Arc::new(provider);

    let id_staking = IDStaking::new(id_staking_address, client.clone());

    let current_block = client.get_block_number().await?;

    let postgres_client = PostgresClient::new(&database_url).await?;
    postgres_client.create_table().await?;

    // This is the block number from which we want to start querying events. Either the contract initiation or the last block we queried.
    let query_start_block = postgres_client.get_latest_block().await?;

    let mut last_queried_block: u32 = query_start_block.try_into().unwrap();

    // You can make eth_getLogs requests with up to a 2K block range and no limit on the response size
    while last_queried_block < current_block.as_u32() {
        let next_block_range = last_queried_block.clone() + 2000;
        let previous_events_query = id_staking
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

                            format_and_save_self_stake_event(
                                &event,
                                block_number,
                                tx_hash,
                                &postgres_client,
                            )
                            .await?;
                        }
                        IDStakingEvents::XstakeFilter(event) => {
                            let block_number = meta.block_number.as_u32();
                            let tx_hash = format!("{:?}", meta.transaction_hash);
                            format_and_save_x_stake_event(
                                &event,
                                block_number,
                                tx_hash,
                                &postgres_client,
                            )
                            .await?
                        }
                        _ => {
                            // Catch all for unhandled events
                        }
                    }
                }
            }
            Err(err) => {
                eprintln!(
                    "Error - Failed to query events: {}, {}, {}",
                    err, last_queried_block, next_block_range
                );
            }
        }
        last_queried_block = next_block_range;
    }

    let future_events = id_staking.events().from_block(current_block);

    let mut stream = future_events.stream().await?.with_meta();

    while let Some(Ok((event, meta))) = stream.next().await {
        match event {
            IDStakingEvents::SelfStakeFilter(event) => {
                let block_number = meta.block_number.as_u32();
                let tx_hash = format!("{:?}", meta.transaction_hash);

                format_and_save_self_stake_event(&event, block_number, tx_hash, &postgres_client)
                    .await?;
            }
            IDStakingEvents::XstakeFilter(event) => {
                let block_number = meta.block_number.as_u32();
                let tx_hash = format!("{:?}", meta.transaction_hash);
                format_and_save_x_stake_event(&event, block_number, tx_hash, &postgres_client)
                    .await?
            }
            _ => {
                // Catch all for unhandled events
            }
        }
    }

    return Ok(());
}
