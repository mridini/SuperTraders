from flask import Flask, request, jsonify
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.models import Position

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import pytz
from flask_cors import CORS

app = Flask(__name__)
CORS(app) 

# Initialize Alpaca trading client
trading_client = TradingClient('PKG09W74VWH85PH4DUZQ', 'kbWzDirlf8UFoGXh82aS26L4YsCr0nZraqKtTd0f', paper=True)

# PostgreSQL connection configuration
DB_HOST = "localhost"
DB_NAME = "trading_db"
DB_USER = "trading_user"
DB_PASSWORD = "password"

# Database connection function
def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )

# Flask route to handle TradingView webhook
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data:
        return jsonify({"error": "No data received"}), 400

    # Extract necessary data from the webhook
    symbol = data.get("symbol")
    strategy = data.get("strategy", "default")
    side = data.get("side", "buy").upper()
    qty = float(data.get("quantity", 1))
    time_received = data.get("time", datetime.now(pytz.timezone('America/Chicago')).isoformat())

    if not symbol or not side:
        return jsonify({"error": "Missing required fields"}), 400

    # Insert data into PostgreSQL
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO alerts (symbol, strategy, side, quantity, time_received, status)
            VALUES (%s, %s, %s, %s, %s, %s) RETURNING id;
            """,
            (symbol, strategy, side, qty, time_received, 'received'),
        )
        alert_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500

    # Place an order using Alpaca API
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide[side],
        time_in_force=TimeInForce.DAY,
    )
    try:
        alpaca_order = trading_client.submit_order(order_data)
        # Cast the order_id to string
        alpaca_order_id = str(alpaca_order.id)

        # Update database with order status
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE alerts
            SET status = %s, alpaca_order_id = %s
            WHERE id = %s;
            """,
            ('submitted', alpaca_order_id, alert_id),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Update database with error status
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE alerts
            SET status = %s
            WHERE id = %s;
            """,
            ('error', alert_id),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"error": f"Alpaca API error: {str(e)}"}), 500

    return jsonify({"message": "Webhook processed and trade submitted", "order_id": alpaca_order_id}), 200

@app.route('/alerts', methods=['GET'])
def get_alerts():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM alerts ORDER BY time_received DESC;")
        alerts = cur.fetchall()
        cur.close()
        conn.close()
        return jsonify(alerts)
    except Exception as e:
        return jsonify({"error": f"Database error: {str(e)}"}), 500
    
@app.route('/account', methods=['GET'])
def get_account():
    try:
        # Get account information using Alpaca API
        account = trading_client.get_account()

        # Prepare account info to be sent as a response
        account_info = {
            "portfolio_value": account.portfolio_value,
            "buying_power": account.buying_power
        }

        return jsonify(account_info)
    except Exception as e:
        return jsonify({"error": f"Alpaca API error: {str(e)}"}), 500
    
@app.route('/positions', methods=['GET'])
def get_positions():
    try:
        # Fetch all open positions from Alpaca
        positions = trading_client.get_all_positions()

        # Prepare the list of positions to be sent as a response
        positions_info = [
            {
                "asset": position.symbol,
                "price": position.avg_entry_price,
                "qty": position.qty,
                "market_value": position.market_value,
                "cost_basis": position.cost_basis,
                "total_pl_percent": position.unrealized_plpc,
                "total_pl_dollars": position.unrealized_pl,
            }
            for position in positions
        ]

        return jsonify(positions_info)
    except Exception as e:
        return jsonify({"error": f"Alpaca API error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80)
