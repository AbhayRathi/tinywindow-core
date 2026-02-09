pub mod crypto;
pub mod execution;
pub mod storage;
pub mod signals;

pub use crypto::{SigningKey, VerificationKey, Signature};
pub use execution::{ExecutionEngine, Order, OrderResult};
pub use storage::Database;
pub use signals::SignalManager;

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
