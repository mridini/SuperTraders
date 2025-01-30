from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest

trading_client = TradingClient('PKG09W74VWH85PH4DUZQ', 'kbWzDirlf8UFoGXh82aS26L4YsCr0nZraqKtTd0f', paper=True)

# Get our account information.
account = trading_client.get_account()

# Check if our account is restricted from trading.
if account.trading_blocked:
    print('Account is currently restricted from trading.')

# Check how much money we can use to open new positions. 
print('${} is available as portfolio power.'.format(account.portfolio_value))
print('${} is available as portfolio power.'.format(account.buying_power))
# https://alpaca.markets/sdks/python/api_reference/trading/models.html#alpaca.trading.models.TradeAccount