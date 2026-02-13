use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, PgPool};
use uuid::Uuid;

use crate::{
    execution::{OrderResult, OrderStatus},
    Result,
};

#[derive(Debug, Clone, Serialize, Deserialize, sqlx::FromRow)]
pub struct OrderRecord {
    pub id: Uuid,
    pub symbol: String,
    pub side: String,
    pub order_type: String,
    pub quantity: f64,
    pub price: Option<f64>,
    pub status: String,
    pub execution_price: Option<f64>,
    pub executed_quantity: Option<f64>,
    pub created_at: DateTime<Utc>,
    pub updated_at: DateTime<Utc>,
}

pub struct Database {
    pool: PgPool,
}

impl Database {
    /// Connect to the database
    pub async fn connect(database_url: &str) -> Result<Self> {
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await?;

        Ok(Self { pool })
    }

    /// Initialize database schema
    pub async fn initialize(&self) -> Result<()> {
        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS orders (
                id UUID PRIMARY KEY,
                symbol VARCHAR(50) NOT NULL,
                side VARCHAR(10) NOT NULL,
                order_type VARCHAR(20) NOT NULL,
                quantity DOUBLE PRECISION NOT NULL,
                price DOUBLE PRECISION,
                status VARCHAR(20) NOT NULL,
                execution_price DOUBLE PRECISION,
                executed_quantity DOUBLE PRECISION,
                signature BYTEA,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
            "#,
        )
        .execute(&self.pool)
        .await?;

        sqlx::query(
            r#"
            CREATE TABLE IF NOT EXISTS decisions (
                id UUID PRIMARY KEY,
                order_id UUID REFERENCES orders(id),
                decision_data JSONB NOT NULL,
                proof_hash BYTEA NOT NULL,
                signature BYTEA NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_decisions_order_id ON decisions(order_id);
            "#,
        )
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Store an order result
    ///
    /// Note: This is a simplified implementation. In production, you would need to either:
    /// 1. Add order details (symbol, side, type, quantity) to OrderResult, or
    /// 2. Pass both the original Order and OrderResult to this function
    pub async fn store_order(&self, result: &OrderResult) -> Result<()> {
        let status_str = match result.status {
            OrderStatus::Pending => "pending",
            OrderStatus::Executed => "executed",
            OrderStatus::Failed => "failed",
            OrderStatus::Cancelled => "cancelled",
        };

        // TODO: Currently using placeholder values for order details
        // In production, pass the complete order information
        sqlx::query(
            r#"
            INSERT INTO orders (id, symbol, side, order_type, quantity, status, execution_price, executed_quantity, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                execution_price = EXCLUDED.execution_price,
                executed_quantity = EXCLUDED.executed_quantity,
                updated_at = EXCLUDED.updated_at
            "#
        )
        .bind(result.order_id)
        .bind("PLACEHOLDER") // symbol - should come from Order
        .bind("PLACEHOLDER") // side - should come from Order
        .bind("PLACEHOLDER") // order_type - should come from Order
        .bind(0.0) // quantity - should come from Order
        .bind(status_str)
        .bind(result.execution_price)
        .bind(result.executed_quantity)
        .bind(result.timestamp)
        .bind(result.timestamp)
        .execute(&self.pool)
        .await?;

        Ok(())
    }

    /// Get order history
    pub async fn get_order_history(&self, limit: i64) -> Result<Vec<OrderRecord>> {
        let records = sqlx::query_as::<_, OrderRecord>(
            r#"
            SELECT id, symbol, side, order_type, quantity, price, status,
                   execution_price, executed_quantity, created_at, updated_at
            FROM orders
            ORDER BY created_at DESC
            LIMIT $1
            "#,
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        Ok(records)
    }
}
