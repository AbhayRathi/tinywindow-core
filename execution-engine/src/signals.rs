use redis::{Client, aio::ConnectionManager, AsyncCommands};
use serde::{Serialize, Deserialize};

use crate::Result;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TradingSignal {
    pub symbol: String,
    pub signal_type: String,
    pub strength: f64,
    pub timestamp: i64,
    pub metadata: serde_json::Value,
}

pub struct SignalManager {
    client: ConnectionManager,
}

impl SignalManager {
    /// Connect to Redis
    pub async fn connect(redis_url: &str) -> Result<Self> {
        let client = Client::open(redis_url)?;
        let client = ConnectionManager::new(client).await?;

        Ok(Self { client })
    }

    /// Publish a trading signal
    pub async fn publish_signal(&mut self, signal: &TradingSignal) -> Result<()> {
        let key = format!("signal:{}", signal.symbol);
        let value = serde_json::to_string(signal)?;

        self.client.set_ex::<_, _, ()>(&key, value, 300).await?; // Expire after 5 minutes
        self.client.publish::<_, _, ()>("trading_signals", &key).await?;

        Ok(())
    }

    /// Get the latest signal for a symbol
    pub async fn get_signal(&mut self, symbol: &str) -> Result<Option<TradingSignal>> {
        let key = format!("signal:{}", symbol);
        let value: Option<String> = self.client.get(&key).await?;

        match value {
            Some(v) => {
                let signal = serde_json::from_str(&v)?;
                Ok(Some(signal))
            }
            None => Ok(None),
        }
    }

    /// Subscribe to trading signals (returns channel for receiving signals)
    pub async fn subscribe(&self) -> Result<redis::aio::PubSub> {
        // Note: PubSub requires a separate connection, not ConnectionManager
        // This is a simplified implementation
        let redis_url = std::env::var("REDIS_URL").unwrap_or_else(|_| "redis://127.0.0.1/".to_string());
        let client = Client::open(redis_url)?;
        let conn = client.get_async_connection().await?;
        let mut pubsub = conn.into_pubsub();
        pubsub.subscribe("trading_signals").await?;
        Ok(pubsub)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_signal_creation() {
        let signal = TradingSignal {
            symbol: "BTC/USD".to_string(),
            signal_type: "buy".to_string(),
            strength: 0.85,
            timestamp: 1234567890,
            metadata: serde_json::json!({"source": "ai_model"}),
        };

        assert_eq!(signal.symbol, "BTC/USD");
        assert_eq!(signal.strength, 0.85);
    }
}
