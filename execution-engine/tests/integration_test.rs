//! Integration tests for execution engine

use execution_engine::{ExecutionEngine, Order, OrderSide, OrderType, SigningKey};

#[tokio::test]
async fn test_full_execution_flow() {
    // Generate signing key
    let key = SigningKey::generate();
    
    // Create execution engine
    let engine = ExecutionEngine::new(key.clone());
    
    // Create order
    let mut order = Order::new(
        "BTC/USD".to_string(),
        OrderSide::Buy,
        OrderType::Market,
        0.1,
    );
    
    // Validate order
    assert!(engine.validate_order(&order).is_ok());
    
    // Sign order
    assert!(order.sign(&key).is_ok());
    assert!(order.signature.is_some());
    
    // Execute order
    let result = engine.execute_order(order).await;
    assert!(result.is_ok());
}

#[tokio::test]
async fn test_order_validation() {
    let key = SigningKey::generate();
    let engine = ExecutionEngine::new(key);
    
    // Test invalid quantity
    let order = Order::new(
        "BTC/USD".to_string(),
        OrderSide::Buy,
        OrderType::Market,
        -0.1, // Invalid
    );
    assert!(engine.validate_order(&order).is_err());
    
    // Test empty symbol
    let order = Order::new(
        "".to_string(),
        OrderSide::Buy,
        OrderType::Market,
        0.1,
    );
    assert!(engine.validate_order(&order).is_err());
    
    // Test invalid limit price
    let order = Order::new(
        "BTC/USD".to_string(),
        OrderSide::Buy,
        OrderType::Limit { price: -50000.0 },
        0.1,
    );
    assert!(engine.validate_order(&order).is_err());
}

#[tokio::test]
async fn test_signature_verification() {
    let key = SigningKey::generate();
    let verification_key = key.verification_key();
    
    // Create and sign order
    let mut order = Order::new(
        "ETH/USD".to_string(),
        OrderSide::Sell,
        OrderType::Market,
        1.0,
    );
    
    order.sign(&key).unwrap();
    
    // Verify signature
    let data = order.canonical_bytes().unwrap();
    let signature = order.signature.as_ref().unwrap();
    assert!(verification_key.verify(&data, signature).is_ok());
}
