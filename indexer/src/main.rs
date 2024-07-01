mod legacy_staking_indexer;
mod postgres;
mod staking_indexer;
mod utils;

use dotenv::dotenv;
use ethers::core::types::Address;
use eyre::Result;
use futures::try_join;
use legacy_staking_indexer::LegacyStakingIndexer;
use postgres::PostgresClient;
use staking_indexer::StakingIndexer;
use utils::get_env;

pub const LEGACY_CONTRACT_START_BLOCK: i32 = 16403024;
pub const LEGACY_CONTRACT_ADDRESS: &str = "0x0E3efD5BE54CC0f4C64e0D186b0af4b7F2A0e95F";

#[tokio::main]
async fn main() -> Result<()> {
    dotenv().ok();

    loop {
        let postgres_client = PostgresClient::new().await?;
        let contract_address_eth_mainnet = get_env("STAKING_CONTRACT_ADDRESS_ETH_MAINNET")
            .parse::<Address>()
            .unwrap();
        let contract_address_op_mainnet = get_env("STAKING_CONTRACT_ADDRESS_OP_MAINNET")
            .parse::<Address>()
            .unwrap();

        let contract_address_op_sepolia = get_env("STAKING_CONTRACT_ADDRESS_OP_SEPOLIA")
            .parse::<Address>()
            .unwrap();
        let contract_address_arbitrum_mainnet = get_env("STAKING_CONTRACT_ADDRESS_ARBITRUM_MAINNET")
            .parse::<Address>()
            .unwrap();

        match try_join!(
            run_legacy_indexer(postgres_client.clone()),
            run_ethereum_indexer(postgres_client.clone(), &contract_address_eth_mainnet),
            run_optimism_indexer(postgres_client.clone(), &contract_address_op_mainnet),
            run_optimism_sepolia_indexer(postgres_client.clone(), &contract_address_op_sepolia),
            run_arbitrum_indexer(postgres_client.clone(), &contract_address_arbitrum_mainnet)
        ) {
            Ok(_) => {
                eprintln!("Warning - top-level join ended without error");
            }
            Err(err) => {
                eprintln!("Warning - top-level join ended with error, {}", err);
            }
        }
        // Loop facilitates starting over and recreating all connections if anything fails
        // (aka if the above try_join ever completes)
    }
}

async fn run_legacy_indexer(postgres_client: PostgresClient) -> Result<()> {
    if get_env("INDEXER_LEGACY_ENABLED") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("INDEXER_ETHEREUM_RPC_URL");
    let legacy_staking_indexer = LegacyStakingIndexer::new(postgres_client, &ethereum_rpc_url);
    legacy_staking_indexer.listen_with_timeout_reset().await
}

async fn run_ethereum_indexer(
    postgres_client: PostgresClient,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_ETHEREUM_ENABLED") != "true" {
        return Ok(());
    }

    let ethereum_rpc_url = get_env("INDEXER_ETHEREUM_RPC_URL");
    let ethereum_start_block = get_env("INDEXER_ETHEREUM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    let ethereum_staking_indexer = StakingIndexer::new(
        postgres_client,
        &ethereum_rpc_url,
        ethereum_start_block,
        contract_address,
    )
    .await?;
    ethereum_staking_indexer.index_events().await
}

async fn run_optimism_indexer(
    postgres_client: PostgresClient,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_OPTIMISM_ENABLED") != "true" {
        return Ok(());
    }

    let optimism_rpc_url = get_env("INDEXER_OPTIMISM_RPC_URL");
    let optimism_start_block = get_env("INDEXER_OPTIMISM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    let optimism_staking_indexer = StakingIndexer::new(
        postgres_client,
        &optimism_rpc_url,
        optimism_start_block,
        contract_address,
    )
    .await?;
    optimism_staking_indexer.index_events().await
}

async fn run_arbitrum_indexer(
    postgres_client: PostgresClient,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_ARBITRUM_ENABLED") != "true" {
        return Ok(());
    }

    let arbitrum_rpc_url = get_env("INDEXER_ARBITRUM_RPC_URL");
    let arbitrum_start_block = get_env("INDEXER_ARBITRUM_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    let arbitrum_staking_indexer = StakingIndexer::new(
        postgres_client,
        &arbitrum_rpc_url,
        arbitrum_start_block,
        contract_address,
    )
    .await?;
    arbitrum_staking_indexer.index_events().await
}


async fn run_optimism_sepolia_indexer(
    postgres_client: PostgresClient,
    contract_address: &Address,
) -> Result<()> {
    if get_env("INDEXER_OPTIMISM_SEPOLIA_ENABLED") != "true" {
        return Ok(());
    }

    let op_sepolia_rpc_url = get_env("INDEXER_OPTIMISM_SEPOLIA_RPC_URL");
    let op_sepolia_start_block = get_env("INDEXER_OPTIMISM_SEPOLIA_START_BLOCK")
        .parse::<u64>()
        .unwrap();
    let op_sepolia_staking_indexer = StakingIndexer::new(
        postgres_client,
        &op_sepolia_rpc_url,
        op_sepolia_start_block,
        contract_address,
    )
    .await?;
    op_sepolia_staking_indexer.index_events().await
}
