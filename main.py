import discord
import openai
import nest_asyncio
import yfinance as yf
import matplotlib.pyplot as plt
import os
import asyncio
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta

# 啟用 asyncio 支援
nest_asyncio.apply()

# Flask keep_alive server
app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Discord & OpenAI 設定
DISCORD_TOKEN = os.environ['DISCORD_TOKEN']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']
openai.api_key = OPENAI_API_KEY

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Bot 登入成功：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('股票超人 '):
        stock_code = message.content.split(' ')[1].strip()
        yf_code = f"{stock_code}.TW"

        try:
            stock = yf.Ticker(yf_code)
            hist = stock.history(period="1mo")

            if hist.empty:
                await message.channel.send(f"❌ 查無此股票代碼：{stock_code}")
                return

            info = stock.info
            company_name = info.get('longName', '未知公司')

            latest = hist.iloc[-1]
            prev_close = info.get("previousClose", None)
            if prev_close:
                change = latest["Close"] - prev_close
                percent = (change / prev_close) * 100
                change_str = f"{change:+.2f} 元 ({percent:+.2f}%)"
            else:
                change_str = "無資料"

            # 繪製折線圖
            plt.figure(figsize=(10, 4))
            plt.plot(hist.index, hist['Close'], marker='o')
            plt.title(f'{company_name} ({stock_code}) 近一月股價走勢', fontsize=14)
            plt.xlabel('日期')
            plt.ylabel('收盤價 (元)')
            plt.grid(True)
            plt.tight_layout()
            plt.savefig('linechart.png')
            plt.close()

            # ChatGPT 分析
            prompt = (
                f"請你以專業投資分析師身分，分析台股代碼 {stock_code}（{company_name}）最近一個月的股價走勢，"
                f"提供具體的投資建議（例如：是否買入、賣出或觀望，以及原因）。"
                f"\n\n以下是最新的股票資訊：\n"
                f"開盤價：{latest['Open']:.2f} 元\n"
                f"收盤價：{latest['Close']:.2f} 元\n"
                f"最高價：{latest['High']:.2f} 元\n"
                f"最低價：{latest['Low']:.2f} 元\n"
                f"成交量：{latest['Volume']:.0f} 張\n"
                f"昨收：{prev_close if prev_close else '無資料'} 元\n"
                f"漲跌幅：{change_str}\n"
                f"\n請用中文回覆，格式分段清晰。"
            )

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}]
            )
            answer = response.choices[0].message.content.strip()

            reply = (
                f"📊 **{company_name} ({stock_code}) 台股資訊**\n"
                f"開盤：{latest['Open']:.2f} 元\n"
                f"收盤：{latest['Close']:.2f} 元\n"
                f"最高：{latest['High']:.2f} 元\n"
                f"最低：{latest['Low']:.2f} 元\n"
                f"成交量：{latest['Volume']:.0f} 張\n"
                f"昨收：{prev_close if prev_close else '無資料'} 元\n"
                f"漲跌幅：{change_str}\n\n"
                f"📈 **GPT 分析建議：**\n{answer}"
            )

            await message.channel.send(reply)

            with open('linechart.png', 'rb') as f:
                await message.channel.send(file=discord.File(f, 'linechart.png'))

            os.remove('linechart.png')

        except Exception as e:
            await message.channel.send(f"⚠️ 查詢時發生錯誤：{str(e)}")

# 開啟 keep_alive 並啟動 Discord Bot
keep_alive()
client.run(DISCORD_TOKEN)
