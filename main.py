from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import akshare as ak
import pandas as pd
from datetime import datetime
import os

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_index():
    return FileResponse("static/index.html")

@app.get("/analyze")
def analyze(stock_code: str):
    try:
        name_df = ak.stock_info_a_code_name()
        stock_name = name_df[name_df["code"] == stock_code]["name"].values[0]

        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", start_date="20230101", adjust="qfq")
        df = df.rename(columns={
            "日期": "date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume",
        })
        df["date"] = pd.to_datetime(df["date"])
        df.set_index("date", inplace=True)

        if len(df) < 70:
            raise ValueError("数据不足")

        df['MA20'] = df['Close'].rolling(20).mean()
        df['Volume_MA5'] = df['Volume'].rolling(5).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        ema_fast = df['Close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['High30'] = df['Close'].rolling(30).max()
        df['Low30'] = df['Close'].rolling(30).min()
        df['Fib_38.2'] = df['High30'] - (df['High30'] - df['Low30']) * 0.382
        df.dropna(inplace=True)
        latest = df.iloc[-1]

        signal = {
            "股票代码": stock_code,
            "股票名称": stock_name,
            "收盘价": round(latest['Close'], 2),
            "38.2%回撤位": round(latest['Fib_38.2'], 2),
            "收盘大于38.2": float(latest['Close']) > float(latest['Fib_38.2']),
            "收盘大于MA20": float(latest['Close']) > float(latest['MA20']),
            "放量上涨": float(latest['Volume']) > 1.2 * float(latest['Volume_MA5']),
            "K线形态": "",
            "RSI值": round(float(latest['RSI']), 2),
            "MACD金叉": float(latest['MACD']) > float(latest['MACD_signal']),
        }

        satisfied = sum([
            signal["收盘大于38.2"],
            signal["收盘大于MA20"],
            signal["放量上涨"],
            signal["K线形态"] != "",
            signal["RSI值"] > 30,
            signal["MACD金叉"]
        ])

        signal["建议买入"] = satisfied >= 5
        return signal

    except Exception as e:
        return {"错误": str(e)}
