use super::result::BacktestResult;
use super::tracker::TradeTracker;
use super::types::{ClosedTrade, TradePnL};
use crate::model::{OrderSide, Trade};
use rust_decimal::Decimal;
use std::collections::HashMap;

fn create_trade(
    symbol: &str,
    side: OrderSide,
    quantity: Decimal,
    price: Decimal,
    commission: Decimal,
) -> Trade {
    Trade {
        id: "trade_id".to_string(),
        order_id: "order_id".to_string(),
        symbol: symbol.to_string(),
        side,
        quantity,
        price,
        commission,
        timestamp: 0,
        bar_index: 0,
        owner_strategy_id: None,
    }
}

fn analyze_trades(
    trades: Vec<Trade>,
    current_prices: Option<HashMap<String, Decimal>>,
) -> (TradePnL, Vec<ClosedTrade>) {
    let mut tracker = TradeTracker::new();
    for trade in trades {
        tracker.process_trade(&trade, None, None, Decimal::ZERO);
    }
    (
        tracker.calculate_pnl(current_prices),
        tracker.closed_trades.to_vec(),
    )
}

#[test]
fn test_trade_analyzer_long_profit() {
    // Buy 100 @ 10, Sell 100 @ 12
    let t1 = create_trade(
        "AAPL",
        OrderSide::Buy,
        Decimal::from(100),
        Decimal::from(10),
        Decimal::ZERO,
    );
    let t2 = create_trade(
        "AAPL",
        OrderSide::Sell,
        Decimal::from(100),
        Decimal::from(12),
        Decimal::ZERO,
    );

    let (pnl, _) = analyze_trades(vec![t1, t2], None);

    assert_eq!(pnl.total_closed_trades, 1);
    assert_eq!(pnl.won_count, 1);
    assert_eq!(pnl.gross_pnl, 200.0); // (12-10)*100
    assert_eq!(pnl.win_rate, 100.0);
}

#[test]
fn test_trade_analyzer_short_loss() {
    // Sell 100 @ 10, Buy 100 @ 12
    let t1 = create_trade(
        "AAPL",
        OrderSide::Sell,
        Decimal::from(100),
        Decimal::from(10),
        Decimal::ZERO,
    );
    let t2 = create_trade(
        "AAPL",
        OrderSide::Buy,
        Decimal::from(100),
        Decimal::from(12),
        Decimal::ZERO,
    );

    let (pnl, _) = analyze_trades(vec![t1, t2], None);

    assert_eq!(pnl.total_closed_trades, 1);
    assert_eq!(pnl.lost_count, 1);
    assert_eq!(pnl.gross_pnl, -200.0); // (10-12)*100
    assert_eq!(pnl.loss_rate, 100.0);
}

#[test]
fn test_trade_analyzer_fifo() {
    // Buy 100 @ 10
    // Buy 100 @ 12
    // Sell 150 @ 11
    let t1 = create_trade(
        "AAPL",
        OrderSide::Buy,
        Decimal::from(100),
        Decimal::from(10),
        Decimal::ZERO,
    );
    let t2 = create_trade(
        "AAPL",
        OrderSide::Buy,
        Decimal::from(100),
        Decimal::from(12),
        Decimal::ZERO,
    );
    let t3 = create_trade(
        "AAPL",
        OrderSide::Sell,
        Decimal::from(150),
        Decimal::from(11),
        Decimal::ZERO,
    );

    let (pnl, _) = analyze_trades(vec![t1, t2, t3], None);

    assert_eq!(pnl.gross_pnl, 50.0);
    assert_eq!(pnl.total_closed_trades, 2);
}

#[test]
fn test_unrealized_pnl() {
    // Buy 100 @ 10
    let t1 = create_trade(
        "AAPL",
        OrderSide::Buy,
        Decimal::from(100),
        Decimal::from(10),
        Decimal::ZERO,
    );

    let mut prices = HashMap::new();
    prices.insert("AAPL".to_string(), Decimal::from(15));

    let (pnl, _) = analyze_trades(vec![t1], Some(prices));

    assert_eq!(pnl.total_closed_trades, 0);
    assert_eq!(pnl.unrealized_pnl, 500.0); // (15-10)*100
}

#[test]
fn test_max_drawdown_logic() {
    let empty_pnl = TradeTracker::new().calculate_pnl(None);

    // Case 1: Standard Drawdown
    // 100 -> 120 -> 90 -> 110
    let equity_curve = vec![
        (1, Decimal::from(100)),
        (2, Decimal::from(120)), // Peak
        (3, Decimal::from(90)),  // Drawdown: (120-90)/120 = 0.25
        (4, Decimal::from(110)),
    ];

    let result = BacktestResult::calculate(crate::analysis::CalculatorInput {
        equity_curve_decimal: equity_curve,
        cash_curve_decimal: vec![],
        snapshots: vec![],
        trade_pnl: empty_pnl.clone(),
        trades: vec![],
        initial_cash: Decimal::from(100),
        orders: vec![],
        executions: vec![],
    });
    assert_eq!(result.metrics.max_drawdown, 0.25);

    // Case 2: No Drawdown (Monotonic Increase)
    // 100 -> 110 -> 120
    let equity_curve_2 = vec![
        (1, Decimal::from(100)),
        (2, Decimal::from(110)),
        (3, Decimal::from(120)),
    ];
    let result_2 = BacktestResult::calculate(crate::analysis::CalculatorInput {
        equity_curve_decimal: equity_curve_2,
        cash_curve_decimal: vec![],
        snapshots: vec![],
        trade_pnl: empty_pnl.clone(),
        trades: vec![],
        initial_cash: Decimal::from(100),
        orders: vec![],
        executions: vec![],
    });
    assert_eq!(result_2.metrics.max_drawdown, 0.0);

    // Case 3: Immediate Drawdown
    // 100 -> 80 -> 90
    let equity_curve_3 = vec![
        (1, Decimal::from(100)), // Peak
        (2, Decimal::from(80)),  // Drawdown: (100-80)/100 = 0.2
        (3, Decimal::from(90)),
    ];
    let result_3 = BacktestResult::calculate(crate::analysis::CalculatorInput {
        equity_curve_decimal: equity_curve_3,
        cash_curve_decimal: vec![],
        snapshots: vec![],
        trade_pnl: empty_pnl.clone(),
        trades: vec![],
        initial_cash: Decimal::from(100),
        orders: vec![],
        executions: vec![],
    });
    assert_eq!(result_3.metrics.max_drawdown, 0.2);

    // Case 4: Multiple Peaks
    // 100 -> 90 (0.1) -> 100 -> 110 -> 55 (0.5) -> 110
    let equity_curve_4 = vec![
        (1, Decimal::from(100)),
        (2, Decimal::from(90)), // DD 0.1
        (3, Decimal::from(100)),
        (4, Decimal::from(110)), // New Peak
        (5, Decimal::from(55)),  // DD (110-55)/110 = 0.5
        (6, Decimal::from(110)),
    ];
    let result_4 = BacktestResult::calculate(crate::analysis::CalculatorInput {
        equity_curve_decimal: equity_curve_4,
        cash_curve_decimal: vec![],
        snapshots: vec![],
        trade_pnl: empty_pnl.clone(),
        trades: vec![],
        initial_cash: Decimal::from(100),
        orders: vec![],
        executions: vec![],
    });
    assert_eq!(result_4.metrics.max_drawdown, 0.5);
}

#[test]
fn test_ulcer_index_logic() {
    let empty_pnl = TradeTracker::new().calculate_pnl(None);

    // Equity Curve: [100, 100, 90, 90, 100]
    // DDs: [0, 0, 0.1, 0.1, 0]
    // Squares: [0, 0, 0.01, 0.01, 0]
    // Sum = 0.02
    // Mean = 0.02 / 5 = 0.004
    // UI = sqrt(0.004) = 0.0632455532

    let equity_curve = vec![
        (1, Decimal::from(100)),
        (2, Decimal::from(100)),
        (3, Decimal::from(90)),
        (4, Decimal::from(90)),
        (5, Decimal::from(100)),
    ];

    let result = BacktestResult::calculate(crate::analysis::CalculatorInput {
        equity_curve_decimal: equity_curve,
        cash_curve_decimal: vec![],
        snapshots: vec![],
        trade_pnl: empty_pnl.clone(),
        trades: vec![],
        initial_cash: Decimal::from(100),
        orders: vec![],
        executions: vec![],
    });
    let expected_ui = 0.004f64.sqrt();
    assert!((result.metrics.ulcer_index - expected_ui).abs() < 1e-9);
}
