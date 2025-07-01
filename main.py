import os
import nest_asyncio
import discord
import openai
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from keep_alive import keep_alive

keep_alive()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("❌ 請設定環境變數 DISCORD_TOKEN 與 OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

nest_asyncio.apply()
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'✅ Bot 上線：{client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!股票超人 '):
        stock_code = message.content.split(' ')[1].strip()
        yf_code = f"{stock_code}.TW"

        try:
            stock = yf.Ticker(yf_code)
            hist = stock.history(start="2025-01-01", end=datetime.today().strftime('%Y-%m-%d'))

            if hist.empty:
                await message.channel.send(f"❌ 找不到股票或資料不足：{stock_code}")
                return

            info = stock.fast_info if hasattr(stock, 'fast_info') else stock.info
            company_name = info.get('longName') or info.get('shortName') or '未知公司'

            latest = hist.iloc[-1]
            previous_close = hist.iloc[-2]['Close']
            price_change = latest['Close'] - previous_close
            price_change_percent = (price_change / previous_close) * 100

            plt.figure(figsize=(16, 6))
            plt.plot(hist.index, hist['Close'], marker='o', color='blue')
            plt.title(f'{company_name}（{stock_code}）上半年股價走勢', fontsize=16)
            plt.xlabel('日期', fontsize=12)
            plt.ylabel('收盤價（元）', fontsize=12)
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.tight_layout()
            chart_path = f"{stock_code}_chart.png"
            plt.savefig(chart_path)
            plt.close()

            prompt = (
                f"你是一位專業台股技術分析師，請根據股票 {stock_code}（{company_name}）"
                f"從 2025 年上半年以來的股價走勢圖，分析：\n"
                f"1. 趨勢是多頭、空頭或盤整？\n"
                f"2. 近期支撐/阻力與技術訊號？\n"
                f"3. 有無風險因素？\n"
                f"4. 建議操作策略（買進/持有/賣出）？\n\n"
                f"最新資料：開 {latest['Open']:.2f}、收 {latest['Close']:.2f}、高 {latest['High']:.2f}、低 {latest['Low']:.2f}、量 {latest['Volume']:.0f}"
            )

            response = openai.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6
            )

            analysis = response.choices[0].message.content.strip()

            reply = (
                f"📈 **{company_name} ({stock_code})**\n"
                f"昨收：{previous_close:.2f} 元\n"
                f"開盤：{latest['Open']:.2f} 元\n"
                f"收盤：{latest['Close']:.2f} 元\n"
                f"最高：{latest['High']:.2f} 元\n"
                f"最低：{latest['Low']:.2f} 元\n"
                f"漲跌：{price_change:+.2f} 元 ({price_change_percent:+.2f}%)\n"
                f"成交量：{latest['Volume']:.0f} 張\n\n"
                f"💬 **GPT 分析建議**\n{analysis}"
            )

            await message.channel.send(reply)
            await message.channel.send(file=discord.File(chart_path))
            os.remove(chart_path)

        except Exception as e:
            await message.channel.send(f"⚠️ 查詢錯誤：{e}")
            print("❌ 發生錯誤：", e)

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)
