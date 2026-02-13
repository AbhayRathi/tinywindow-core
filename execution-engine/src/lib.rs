pub mod crypto;
pub mod execution;
pub mod signals;
pub mod storage;

pub use crypto::{Signature, SigningKey, VerificationKey};
pub use execution::{ExecutionEngine, Order, OrderResult};
pub use signals::SignalManager;
pub use storage::Database;

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("Cryptographic error: {0}")]
    Crypto(String),

    #[error("Database error: {0}")]
    Database(#[from] sqlx::Error),

    #[error("Redis error: {0}")]
    Redis(#[from] redis::RedisError),

    #[error("Execution error: {0}")]
    Execution(String),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, Error>;
