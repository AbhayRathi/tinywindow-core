use execution_engine::execution::{Order, OrderSide, OrderType};
use execution_engine::{ExecutionEngine, SigningKey};

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt::init();

    tracing::info!("Starting TinyWindow Execution Engine");

    // Generate signing key (in production, load from secure storage)
    let signing_key = SigningKey::generate();
    tracing::info!("Generated signing key");

    // Initialize execution engine
    let engine = ExecutionEngine::new(signing_key);
    tracing::info!("Execution engine initialized");

    // Example: Create and execute an order
    let order = Order::new(
        "BTC/USD".to_string(),
        OrderSide::Buy,
        OrderType::Market,
        0.1,
    );

    tracing::info!("Created order: {:?}", order);

    match engine.execute_order(order).await {
        Ok(result) => {
            tracing::info!("Order executed successfully: {:?}", result);
        }
        Err(e) => {
            tracing::error!("Failed to execute order: {}", e);
        }
    }

    // Database and Redis connections would be initialized here in production
    // with proper configuration from environment variables

    tracing::info!("TinyWindow Execution Engine running");

    Ok(())
}
