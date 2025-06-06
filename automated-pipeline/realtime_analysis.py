import requests
import pandas as pd
from datetime import datetime, timedelta
from dash import Dash, dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go

# Your Moralis config
PAIR_ADDRESS = "0x5A95e8a95706b2687321D7289161A6013b36c0fC"
CHAIN = "eth"
TIMEFRAME = "1min"
CURRENCY = "usd"
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJub25jZSI6ImNkNzA1ZTM3LWNmMmYtNDRiMS1iNzdmLTIxYWM1Yjc5YzFjNiIsIm9yZ0lkIjoiNDUxMzAwIiwidXNlcklkIjoiNDY0MzUyIiwidHlwZUlkIjoiMGMwOTFmZWUtYTlmNC00ZGQxLWIzMjYtMDdlNGY5NDkwZjgxIiwidHlwZSI6IlBST0pFQ1QiLCJpYXQiOjE3NDkxOTY4MDIsImV4cCI6NDkwNDk1NjgwMn0.dHTGY1zpZF-OpKkv5tiqYZqQ6NO0ALjypuTG9PgCDNM"
headers = {
    "Accept": "application/json",
    "X-API-Key": API_KEY
}

def fetch_ohlcv(from_dt, to_dt, limit=100):
    url = (
        f"https://deep-index.moralis.io/api/v2.2/pairs/{PAIR_ADDRESS}/ohlcv?"
        f"chain={CHAIN}&timeframe={TIMEFRAME}&currency={CURRENCY}"
        f"&fromDate={from_dt.isoformat()}&toDate={to_dt.isoformat()}&limit={limit}"
    )
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print(f"Error fetching data: {resp.status_code} {resp.text}")
        return []
    data = resp.json()
    return data.get("result", [])

# Initialize app
app = Dash(__name__)
app.layout = html.Div([
    html.H1("Real-Time Crypto OHLCV (1-min candles)"),
    dcc.Graph(id='live-candlestick'),
    dcc.Graph(id='cumulative-return-chart'),
    dcc.Graph(id='drawdown-chart'),
    dcc.Graph(id='volume-chart'),
    dcc.Interval(
        id='interval-component',
        interval=1*1000,  # 1 second in milliseconds
        n_intervals=0
    )
])

# Keep data globally for session (basic demo)
global_df = pd.DataFrame()

@app.callback(
    [
        Output('live-candlestick', 'figure'),
        Output('cumulative-return-chart', 'figure'),
        Output('drawdown-chart', 'figure'),
        Output('volume-chart', 'figure'),
    ],
    Input('interval-component', 'n_intervals')
)
def update_chart(n):
    global global_df
    now = datetime.utcnow()

    # On first run or empty df, fetch last 100 candles
    if global_df.empty:
        from_dt = now - timedelta(minutes=100)
        to_dt = now
        ohlcv_data = fetch_ohlcv(from_dt, to_dt)
        if not ohlcv_data:
            # Return empty figures if no data
            empty_fig = go.Figure()
            return empty_fig, empty_fig, empty_fig, empty_fig
        df = pd.DataFrame(ohlcv_data)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)
        global_df = df
    else:
        # Fetch the latest candle for the last 1 min
        from_dt = now - timedelta(minutes=1)
        to_dt = now
        latest_data = fetch_ohlcv(from_dt, to_dt, limit=1)
        if latest_data:
            latest_df = pd.DataFrame(latest_data)
            latest_df["timestamp"] = pd.to_datetime(latest_df["timestamp"])
            latest_df.set_index("timestamp", inplace=True)

            last_timestamp = global_df.index[-1]
            new_timestamp = latest_df.index[0]

            if new_timestamp > last_timestamp:
                global_df = pd.concat([global_df, latest_df])
                # Keep only last 100 rows to limit memory
                global_df = global_df.tail(100)

    df = global_df.copy()

    # Calculate returns for cumulative return and drawdown
    df['return'] = df['close'].pct_change()
    df['cumulative_return'] = (1 + df['return']).cumprod() - 1
    df['cum_max'] = df['close'].cummax()
    df['drawdown'] = df['close'] / df['cum_max'] - 1

    # --- Candlestick Chart ---
    candlestick_fig = go.Figure(data=[go.Candlestick(
        x=df.index,
        open=df['open'],
        high=df['high'],
        low=df['low'],
        close=df['close'],
        increasing_line_color='green',
        decreasing_line_color='red'
    )])
    candlestick_fig.update_layout(
        title="Real-Time Candlestick Chart",
        xaxis_title="Time (UTC)",
        yaxis_title="Price (USD)",
        xaxis_rangeslider_visible=False
    )

    # --- Cumulative Return Chart ---
    cumret_fig = go.Figure(data=go.Scatter(
        x=df.index,
        y=df['cumulative_return'],
        mode='lines',
        name='Cumulative Return',
        line=dict(color='blue')
    ))
    cumret_fig.update_layout(
        title="Cumulative Return Over Time",
        xaxis_title="Time (UTC)",
        yaxis_title="Cumulative Return"
    )

    # --- Drawdown Chart ---
    drawdown_fig = go.Figure(data=go.Scatter(
        x=df.index,
        y=df['drawdown'],
        mode='lines',
        name='Drawdown',
        line=dict(color='red')
    ))
    drawdown_fig.update_layout(
        title="Drawdown Over Time",
        xaxis_title="Time (UTC)",
        yaxis_title="Drawdown"
    )

    # --- Volume Chart ---
    volume_fig = go.Figure(data=go.Bar(
        x=df.index,
        y=df['volume'].astype(float),
        name='Volume',
        marker_color='purple'
    ))
    volume_fig.update_layout(
        title="Volume Over Time",
        xaxis_title="Time (UTC)",
        yaxis_title="Volume"
    )

    return candlestick_fig, cumret_fig, drawdown_fig, volume_fig

if __name__ == '__main__':
    app.run(debug=True)