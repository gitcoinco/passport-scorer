extern crate chrono;

use chrono::prelude::{DateTime, Utc};
use deadpool_postgres::{Manager, ManagerConfig, Pool, RecyclingMethod};
use ethers::types::H160;
use rust_decimal::prelude::*;
use rust_decimal::Decimal;
use std::str::FromStr;
use tokio_postgres::{Error, NoTls};

use crate::{
    utils::{get_code_for_stake_event_type, get_env, StakeAmountOperation, StakeEventType},
    LEGACY_CONTRACT_START_BLOCK,
};

#[derive(Debug, Clone)]
pub struct PostgresClient {
    pool: Pool,
}

pub struct ManualIndexRequest {
    pub id: i32,
    pub block_number: u64,
    pub tx_hash: String,
}

impl PostgresClient {
    pub async fn new() -> Result<Self, Error> {
        let mut pg_config = tokio_postgres::Config::new();

        pg_config
            .user(&get_env("DB_USER"))
            .password(get_env("DB_PASSWORD"))
            .dbname(&get_env("DB_NAME"))
            .host(&get_env("DB_HOST"))
            .port(get_env("DB_PORT").parse::<u16>().unwrap());

        let mgr_config = ManagerConfig {
            recycling_method: RecyclingMethod::Fast,
        };
        let mgr = Manager::from_config(pg_config, NoTls, mgr_config);

        let pool = Pool::builder(mgr).max_size(16).build().unwrap();

        Ok(Self {
            pool,
        })
    }

    // This function is for legacy staking contract events
    pub async fn insert_into_combined_stake_filter_self_stake_legacy(
        &self,
        round_id: i32,
        staker: &str,
        amount: &str,
        staked: bool,
        block_number: i32,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let mut decimal_amount = Decimal::from_str(amount).unwrap();
        let _ = decimal_amount.set_scale(18).unwrap();
        let client = self.pool.get().await.unwrap();
        client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7)",&[&"SelfStake", &round_id, &staker, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into registry_gtcstakeevent with type SelfStake for block {} for legacy contract!",
            block_number
        );
        Ok(())
    }

    // This function is for legacy staking contract events
    pub async fn insert_into_combined_stake_filter_xstake_legacy(
        &self,
        round_id: i32,
        staker: &str,
        user: &str,
        amount: &str,
        staked: bool,
        block_number: i32,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let mut decimal_amount = Decimal::from_str(amount).unwrap();
        let _ = decimal_amount.set_scale(18).unwrap();
        let client = self.pool.get().await.unwrap();
        client.execute("INSERT INTO registry_gtcstakeevent (event_type, round_id, staker, address, amount, staked, block_number, tx_hash) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)", &[&"Xstake", &round_id, &staker, &user, &decimal_amount, &staked, &block_number, &tx_hash]).await?;
        println!(
            "Row inserted into registry_gtcstakeevent with type Xstake for block {} for legacy contract!",
            block_number
        );
        Ok(())
    }

    fn unix_time_to_datetime(&self, unix_time: &u64) -> DateTime<Utc> {
        DateTime::from_timestamp(*unix_time as i64, 0).unwrap()
    }

    pub async fn get_pending_manual_index_requests(&self, chain_id: u32) -> Result<Vec<ManualIndexRequest>, Error> {
        let client = self.pool.get().await.unwrap();
        let raw_rows = client
            .query("SELECT id, block_number, tx_hash FROM stake_manualindexrequest WHERE status = 'pending' AND chain_id = $1", &[&(chain_id as i32)])
            .await?;

        let mut rows = Vec::new();

        for row in raw_rows {
            let id: i32 = row.get("id");
            let decimal_block_number: Decimal = row.get("block_number");
            let block_number: u64 = decimal_block_number.to_u64().unwrap();
            let tx_hash: String = row.get("tx_hash");

            rows.push(ManualIndexRequest {
                id,
                block_number,
                tx_hash,
            });
        }

        Ok(rows)
    }

    pub async fn update_manual_index_request_status(&self, id: i32, status: &str) -> Result<(), Error> {
        let client = self.pool.get().await.unwrap();
        client.execute("UPDATE stake_manualindexrequest SET status = $1 WHERE id = $2", &[&status, &id]).await?;
        Ok(())
    }

    pub async fn add_or_extend_stake(
        &self,
        event_type: &StakeEventType,
        chain_id: u32,
        staker: &H160,
        stakee: &H160,
        increase_amount: &u128,
        unlock_time: &u64,
        block_timestamp: &u64,
        block_number: &u64,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let chain_id: i32 = chain_id as i32;
        let staker = format!("{:#x}", staker);
        let stakee = format!("{:#x}", stakee);
        let mut increase_amount = Decimal::from_u128(*increase_amount).unwrap();
        increase_amount.set_scale(18).unwrap();
        let unlock_time = self.unix_time_to_datetime(unlock_time);
        let lock_time = self.unix_time_to_datetime(block_timestamp);
        let block_number = Decimal::from_u64(*block_number).unwrap();

        let client = self.pool.get().await.unwrap();

        // Log current stake state
        client.execute(
            concat!(
                "INSERT INTO stake_stake as stake (chain, staker, stakee, unlock_time, lock_time, last_updated_in_block, current_amount)",
                " VALUES ($1, $2, $3, $4, $5, $6, $7) ON CONFLICT (chain, staker, stakee) DO UPDATE",
                " SET unlock_time = EXCLUDED.unlock_time,",
                "     lock_time = EXCLUDED.lock_time,",
                "     last_updated_in_block = EXCLUDED.last_updated_in_block,",
                "     current_amount = stake.current_amount + EXCLUDED.current_amount",
                " WHERE EXCLUDED.last_updated_in_block >= stake.last_updated_in_block"
            ),
            &[&chain_id, &staker, &stakee, &unlock_time, &lock_time, &block_number, &increase_amount]
        ).await?;

        // Log raw event
        client.execute(
            concat!(
                "INSERT INTO stake_stakeevent (event_type, chain, staker, stakee, amount, unlock_time, block_number, tx_hash)",
                " VALUES ($1, $2, $3, $4, $5, $6, $7, $8)"
            ),
            &[&get_code_for_stake_event_type(event_type), &chain_id, &staker, &stakee, &increase_amount, &unlock_time, &block_number, &tx_hash]
        ).await?;

        println!(
            "Added or extended stake in block {} on chain {}!",
            block_number, chain_id
        );

        Ok(())
    }

    pub async fn update_stake_amount(
        &self,
        event_type: &StakeEventType,
        chain_id: u32,
        staker: &H160,
        stakee: &H160,
        change_amount: &u128,
        operation: StakeAmountOperation,
        block_number: &u64,
        tx_hash: &str,
    ) -> Result<(), Error> {
        let chain_id: i32 = chain_id as i32;
        let staker = format!("{:#x}", staker);
        let stakee = format!("{:#x}", stakee);
        let mut change_amount = Decimal::from_u128(*change_amount).unwrap();
        change_amount.set_scale(18).unwrap();
        let amount = match operation {
            StakeAmountOperation::Add => change_amount,
            StakeAmountOperation::Subtract => -change_amount,
        };
        let block_number = Decimal::from_u64(*block_number).unwrap();

        let client = self.pool.get().await.unwrap();

        // Log current stake state
        client
            .execute(
                concat!(
                    "UPDATE stake_stake",
                    " SET current_amount = current_amount + $1",
                    " WHERE chain = $2 AND staker = $3 AND stakee = $4",
                    " AND last_updated_in_block <= $5"
                ),
                &[&amount, &chain_id, &staker, &stakee, &block_number],
            )
            .await?;

        // Log raw event
        client
            .execute(
                concat!(
                    "INSERT INTO stake_stakeevent (event_type, chain, staker, stakee, amount, block_number, tx_hash)",
                    " VALUES ($1, $2, $3, $4, $5, $6, $7)"
                ),
                &[&get_code_for_stake_event_type(event_type), &chain_id, &staker, &stakee, &amount, &block_number, &tx_hash],
            )
            .await?;

        println!(
            "Modified stake amount in block {} on chain {}!",
            block_number, chain_id
        );

        Ok(())
    }

    pub async fn get_latest_block(&self, chain_id: u32, fallback_start_block: u64) -> Result<u64, Error> {
        let chain_id: i32 = chain_id as i32;
        let client = self.pool.get().await.unwrap();
        let latest_block_rows = client
            .query(
                "SELECT last_updated_in_block FROM stake_stake WHERE chain = $1 ORDER BY last_updated_in_block DESC LIMIT 1;",
                &[&chain_id],
            )
            .await?;

        if let Some(row) = latest_block_rows.get(0) {
            // Extract and return the block number
            let latest_block: Decimal = row.get("last_updated_in_block");
            Ok(latest_block.to_u64().unwrap())
        } else {
            // return contract start block
            Ok(fallback_start_block)
        }
    }

    pub async fn get_latest_block_legacy(&self) -> Result<i32, Error> {
        let client = self.pool.get().await.unwrap();
        let latest_block_rows = client
            .query(
                "SELECT block_number FROM registry_gtcstakeevent ORDER BY id DESC LIMIT 1;",
                &[],
            )
            .await?;

        if let Some(row) = latest_block_rows.get(0) {
            // Extract and return the block number
            let latest_block: i32 = row.get("block_number");
            Ok(latest_block)
        } else {
            // return contract start block
            Ok(LEGACY_CONTRACT_START_BLOCK)
        }
    }
}
