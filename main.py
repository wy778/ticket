import os
import asyncio
import nest_asyncio
import discord
import openai
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta

# ── 讀取環境變數 ───────────────────────────────────
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not (DISCORD_TOKEN and OPENAI_API_KEY):
    raise RuntimeError("❌ 請先在 Railway 或本地 .env 設定 DISCORD_TOKEN 與 OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

# ── Discord bot 基本設定 ───────────────────────────
nest_asyncio.apply()
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 若你有 keep_alive.py，可取消下一行註解
# from keep_alive import keep_alive
# keep_alive()

# ── Bot 上線時 ─────────────────────────────────────
@client.event
async def on_ready():
    print(f'✅ Bot 已上線：{client.user}')

# ── 監聽訊息 ──────────────────────────────────────
@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    if message.content.startswith('!股票超人 '):
        stock_code = message.content.split(' ')[1].strip()
        yf_code = f"{stock_code}.TW"

        try:
            # 取最近 1 個月資料（yfinance 最小以日為單位）
            stock = yf.Ticker(yf_code)
            hist = stock.history(start=(datetime.today() - timedelta(days=31)).strftime('%Y-%m-%d'),
                                 end=datetime.today().strftime('%Y-%m-%d'))

            if hist.empty:
                await message.channel.send(f"❌ 找不到股票或資料不足：{stock_code}")
                return

            info = stock.fast_info  # fast_info 較快，找不到再 fallback
            if not info:
                info = stock.info
            company_name = info.get('longName', info.get('shortName', '未知公司'))

            # 計算漲跌
            latest = hist.iloc[-1]
            previous_close = hist.iloc[-2]['Close']
            price_change = latest['Close'] - previous_close
            price_change_percent = (price_change / previous_close) * 100

            # ── 中文折線圖 ──────────────────────────
            plt.figure(figsize=(16, 6))
            plt.plot(hist.index, hist['Close'], marker='o')
            plt.title(f'{company_name}（{stock_code}）近一月股價走勢', fontsize=16)
            plt.xlabel('日期', fontsize=12)
            plt.ylabel('收盤價（元）', fontsize=12)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.tight_layout()
            chart_path = f'{stock_code}_chart.png'
            plt.savefig(chart_path)
            plt.close()

            # ── GPT 產生分析 ────────────────────────
            prompt = (
                f"你是一位專業台股技術分析師，請根據股票 {stock_code}（{company_name}）近一月走勢，"
                f"進行以下分析並用繁體中文列點說明：\n"
                f"1. 股價趨勢（多頭/空頭/盤整）及理由。\n"
                f"2. 重要技術指標與支撐/阻力。\n"
                f"3. 風險因素。\n"
                f"4. 具體操作建議（買進/持有/賣出/觀望）。\n\n"
                f"最新數據：開 {latest['Open']:.2f}、收 {latest['Close']:.2f}、高 {latest['High']:.2f}、低 {latest['Low']:.2f}、量 {latest['Volume']:.0f}"
            )

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            analysis = response.choices[0].message.content.strip()

            # ── 組裝訊息 ────────────────────────────
            reply = (
                f"📈 **{company_name} ({stock_code})**\n"
                f"昨收：{previous_close:.2f} 元\n"
                f"開盤：{latest['Open']:.2f} 元\n"
                f"收盤：{latest['Close']:.2f} 元\n"
                f"最高：{latest['High']:.2f} 元\n"
                f"最低：{latest['Low']:.2f} 元\n"
                f"漲跌：{price_change:+.2f} 元 ({price_change_percent:+.2f}%)\n"
                f"成交量：{latest['Volume']:.0f} 張\n\n"
                f"💬 **GPT 分析**\n{analysis}"
            )

            await message.channel.send(reply)
            await message.channel.send(file=discord.File(chart_path))
            os.remove(chart_path)

        except Exception as e:
            print("查詢錯誤：", e)
            await message.channel.send(f"⚠️ 查詢錯誤：{e}")

# ── 啟動 Bot ─────────────────────────────────────
if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
