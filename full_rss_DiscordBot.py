import os
import signal
import json
from datetime import datetime, timedelta

import asyncio
import aiohttp
import feedparser
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from bs4 import BeautifulSoup
import logging
import urllib.parse
from dateutil import parser
from dotenv import load_dotenv
import discord
from discord import Embed
from discord.ext import tasks, commands
from googletrans import Translator as GoogleTranslator
from deep_translator import DeeplTranslator
import pytz


DOMAIN_TO_SOURCE_MAPPING = {
    'wsj.com': '华尔街日报',
    'foreignaffairs.com': '外交事务',
    'ft.com': '金融时报',
    'reuters.com': '路透社',
    'theatlantic.com': '大西洋月刊',
    'economist.com': '经济学人',
    'nytimes.com': '纽约时报',
    'bloomberg.com': '彭博社',
    'theconversation.com': '对话',
    'nautil.us': '鹦鹉螺',
    'longreads.com': '长读',
    'eff.org': '电子前哨基金会',
    'cloudflare.com': 'Cloudflare 博客',
}

# 默认RSS源列表
DEFAULT_RSS_FEEDS = [
    'https://feeds.a.dj.com/rss/RSSOpinion.xml',
    'https://feeds.a.dj.com/rss/WSJcomUSBusiness.xml',
    'https://www.foreignaffairs.com/rss.xml',
    'https://www.ft.com/opinion?format=rss',
    'https://www.ft.com/emerging-markets?format=rss',
    'https://www.ft.com/myft/following/83f62cc4-55d5-4efb-94d0-cd2680322216.rss',
    'https://www.reutersagency.com/feed/?best-types=reuters-news-first&post_type=best',
    'https://www.reutersagency.com/feed/?best-types=the-big-picture&post_type=best',
    'https://www.theatlantic.com/feed/all/',
    'https://www.economist.com/leaders/rss.xml',
    'https://www.economist.com/special-report/rss.xml',
    'https://www.economist.com/the-economist-explains/rss.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Lens.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://feeds.bloomberg.com/economics/news.rss',
    'https://feeds.bloomberg.com/bview/news.rss',
    'https://feeds.bloomberg.com/industries/news.rss',
    'https://theconversation.com/global/home-page.atom',
    'https://nautil.us/feed/',
    'https://longreads.com/feed',
    'https://blog.cloudflare.com/rss',
    'https://www.eff.org/rss/updates.xml'
]

scheduler = AsyncIOScheduler()
running = True

def signal_handler():
    global running
    running = False
    print("Received termination signal. Shutting down...")

# 配置日志记录器
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 读取环境变量
GOOGLE_TRANSLATE_API_KEY = os.getenv('GOOGLE_TRANSLATE_API_KEY')
DEEPL_API_KEY = os.getenv('DEEPL_API_KEY')
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not all([GOOGLE_TRANSLATE_API_KEY, DEEPL_API_KEY, DISCORD_TOKEN]):
    raise ValueError("缺少必要的环境变量")

# 配置常量
CONFIG_DIR = 'config'
ENTRY_LIFETIME = timedelta(days=7)
BOT_PREFIX = '!'
FEED_CHECK_INTERVAL = 3600  # 每小时检查一次RSS源

# 创建配置文件夹
if not os.path.exists(CONFIG_DIR):
    os.makedirs(CONFIG_DIR)

# 初始化Discord Bot
bot = commands.Bot(command_prefix=BOT_PREFIX)

# 配置管理
class ConfigHandler:

    # 初始化配置管理器
    def __init__(self):
        self.configs = {}
        self.load_all_configs()

    # 从配置目录加载所有服务器的配置文件，每个配置文件对应一个服务器，以服务器ID命名。
    def load_all_configs(self):
        for filename in os.listdir(CONFIG_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(CONFIG_DIR, filename), 'r') as f:
                    server_id = int(filename[:-5])
                    self.configs[server_id] = json.load(f)

    # 保存指定服务器的配置到对应的JSON文件。
    def save_config(self, guild_id):  
        with open(os.path.join(CONFIG_DIR, f'{guild_id}.json'), 'w') as f:
            json.dump(self.configs[guild_id], f, indent=4)
    # 获取指定服务器的配置,如果配置不存在，创建一个默认配置
    def get_config(self, guild_id):
        if guild_id not in self.configs:
            self.configs[guild_id] = {
                'rss_sources': DEFAULT_RSS_FEEDS.copy(),  # 使用默认RSS源列表
                'channel_id': None,
                'processed_entries': [],
                'target_language': 'zh',
                'interval': 60  # 默认间隔时间为60分钟
            }
            self.save_config(guild_id)
        return self.configs[guild_id]

    def add_rss_source(self, guild_id, rss_url):
        config = self.get_config(guild_id)
        if rss_url not in config['rss_sources']:
            config['rss_sources'].append(rss_url)
            self.save_config(guild_id)
            return True
        return False

    def remove_rss_source(self, guild_id, rss_url):
        config = self.get_config(guild_id)
        if rss_url in config['rss_sources']:
            config['rss_sources'].remove(rss_url)
            self.save_config(guild_id)
            return True
        return False

    def set_channel(self, guild_id, channel_id):
        config = self.get_config(guild_id)
        config['channel_id'] = channel_id
        self.save_config(guild_id)
        return True

    def get_channel(self, guild_id):
        config = self.get_config(guild_id)
        return config.get('channel_id')

    def get_rss_sources(self, guild_id):
        config = self.get_config(guild_id)
        return config.get('rss_sources', [])
    
    def set_target_language(self, guild_id, language):
        config = self.get_config(guild_id)
        config['target_language'] = language
        self.save_config(guild_id)
        return True

    def get_target_language(self, guild_id):
        config = self.get_config(guild_id)
        return config.get('target_language', 'zh')  # 默认翻译到中文
    # 设置指定服务器的RSS处理间隔时间
    def set_interval(self, guild_id, interval):
        config = self.get_config(guild_id)
        config['interval'] = interval
        self.save_config(guild_id)
        return True

    def get_interval(self, guild_id):
        config = self.get_config(guild_id)
        return config.get('interval', 60)  # 默认间隔时间为60分钟

config_handler = ConfigHandler()

# 解析并格式化RSS条目的发布时间，统一转换为UTC时间。
def parse_published_time(entry):
    if 'published_parsed' in entry and entry.published_parsed:
        published_time = datetime(*entry.published_parsed[:6], tzinfo=pytz.UTC)
    elif 'published' in entry:
        try:
            published_time = parser.parse(entry.published).astimezone(pytz.UTC)
        except (ValueError, TypeError):
            published_time = None
    else:
        published_time = None
    
    if published_time:
        return published_time.strftime('%Y-%m-%d %H:%M:%S %Z')
    else:
        return 'No date'


# 翻译类管理
class TranslatorHandler:
    def __init__(self):
        self.google_translator = GoogleTranslator()
        self.deepl_translator = DeeplTranslator(api_key=DEEPL_API_KEY)
        self.use_google = True

    def translate(self, text, target_language):
        if self.use_google:
            try:
                # Google API 语言代码使用小写
                return self.google_translator.translate(text, dest=target_language.lower()).text
            except Exception as e:
                logger.error(f"Google 翻译失败: {e}, 切换到DeepL")
                self.use_google = False

        if not self.use_google:
            try:
                # DeepL API 语言代码使用大写
                return self.deepl_translator.translate(text, target=target_language.upper())
            except Exception as e:
                logger.error(f"DeepL 翻译失败: {e}, 切换回Google")
                self.use_google = True
                return self.google_translator.translate(text, dest=target_language.lower()).text

translator_handler = TranslatorHandler()

# 获取并翻译RSS
def fetch_and_translate_rss(rss_urls, target_language):
    translated_entries = []
    for url in rss_urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            translated_title = translator_handler.translate(entry.title, target_language)
            original_summary, images = clean_html_and_extract_images(entry.summary)
            translated_summary = translator_handler.translate(original_summary, target_language)
            translated_summary = translated_summary if len(translated_summary) <= 1024 else translated_summary[:1021] + '...'
            published_time = parse_published_time(entry)  # 解析发布时间
            
            # 提取并映射域名
            parsed_url = urllib.parse.urlparse(entry.link)
            domain = parsed_url.netloc
            source = DOMAIN_TO_SOURCE_MAPPING.get(domain, 'Unknown source')

            translated_entries.append({
                'title': translated_title,
                'summary': translated_summary,
                'link': entry.link,
                'images': images,
                'source': source,
                'published': published_time
            })
    return translated_entries


# 清理HTML标签并提取图片
def clean_html_and_extract_images(raw_html):
    if not raw_html.strip().startswith('<'):
        return raw_html, []
    
    soup = BeautifulSoup(raw_html, 'html.parser')
    text = soup.get_text()
    images = [img['src'] for img in soup.find_all('img') if 'src' in img.attrs]
    return text, images

# 格式化Discord消息
def format_discord_message(article, translated_title, translated_summary):
    title = article.get('title', 'No title')
    summary = article.get('summary', 'No summary')
    source = article.get('source', 'Unknown source')
    link = article.get('link', 'No link')
    images = article.get('images', [])  # 确保images从article中获取
    published_time = article.get('published', 'No date')

    truncated_summary = summary if len(summary) <= 1024 else summary[:1021] + '...'  # discord 限制单个嵌入消息字段超过1024字符

    embed = discord.Embed(description=f"[{translated_title}]({link})")
    embed.add_field(name="Details", value=f"```fix\n{truncated_summary}\n\nSource: {source}\nPublished: {published_time}\n```", inline=False)

    if images:
        embed.set_image(url=images[0])

    return embed

# 检查并删除超过7天的条目
def clean_old_entries(config):
    now = datetime.utcnow()
    config['processed_entries'] = [
        entry for entry in config['processed_entries'] if now - datetime.fromisoformat(entry['timestamp']) < ENTRY_LIFETIME
    ]

# 处理并发送翻译后的RSS条目
async def process_and_send_rss(guild_id):
    config = config_handler.get_config(guild_id)  # 获取当前服务器的配置
    channel_id = config_handler.get_channel(guild_id)  # 获取指定的频道ID
    if channel_id:
        channel = bot.get_channel(channel_id)  # 获取频道对象
        if channel:
            clean_old_entries(config)  # 清理超过7天的已处理条目
            target_language = config_handler.get_target_language(guild_id)  # 获取目标翻译语言
            rss_entries = fetch_and_translate_rss(config['rss_sources'], target_language)  # 解析并翻译RSS源
            for entry in rss_entries:
                # 检查条目是否已处理过
                if entry['link'] not in [e['link'] for e in config['processed_entries']]:
                    embed = format_discord_message(entry)  # 格式化为Discord消息
                    await channel.send(embed=embed)  # 发送消息到指定频道
                    # 记录已处理的条目
                    config['processed_entries'].append({
                        'link': entry['link'],
                        'timestamp': datetime.utcnow().isoformat()
                    })
            config_handler.save_config(guild_id)  # 保存更新后的配置

# Discord bot命令
@bot.command(name='add_rss')
async def add_rss(ctx, rss_url):
    if config_handler.add_rss_source(ctx.guild.id, rss_url):
        await ctx.send(f'RSS源 {rss_url} 已添加。')
    else:
        await ctx.send('RSS源无效或已存在。')

@bot.command(name='remove_rss')
async def remove_rss(ctx, rss_url):
    if config_handler.remove_rss_source(ctx.guild.id, rss_url):
        await ctx.send(f'RSS源 {rss_url} 已移除。')
    else:
        await ctx.send('RSS源未找到。')

@bot.command(name='set_channel')
async def set_channel(ctx, channel: discord.TextChannel):
    if config_handler.set_channel(ctx.guild.id, channel.id):
        await ctx.send(f'频道设置为 {channel.mention}')
    else:
        await ctx.send('设置频道失败。')

@bot.command(name='list_rss')
async def list_rss(ctx):
    rss_sources = config_handler.get_rss_sources(ctx.guild.id)
    if rss_sources:
        await ctx.send('当前RSS源列表:\n' + '\n'.join(rss_sources))
    else:
        await ctx.send('没有RSS源。')

@bot.command(name='set_language')
async def set_language(ctx, language):
    valid_languages = [
    'bg', 'cs', 'da', 'de', 'el', 'en', 'es', 'et', 'fi', 'fr', 'hu', 'it', 'ja', 'lt', 'lv', 'nl', 
    'pl', 'pt', 'ro', 'ru', 'sk', 'sl', 'sv'] # 可选的目标语言
    if language not in valid_languages:
        await ctx.send(f'无效的语言代码。可选的语言代码有：{", ".join(valid_languages)}')
    else:
        config_handler.set_target_language(ctx.guild.id, language)
        await ctx.send(f'翻译目标语言已更改为 {language}')

@bot.command(name='set_interval')  # 更改RSS处理间隔时间
async def set_interval(ctx, interval: int):
    if interval <= 0:
        await ctx.send('间隔时间必须大于0分钟。')
    else:
        config_handler.set_interval(ctx.guild.id, interval)
        scheduler.reschedule_job(f'process_rss_{ctx.guild.id}', trigger='interval', minutes=interval)
        await ctx.send(f'RSS处理间隔时间已更改为 {interval} 分钟。')

def setup_scheduler():
    for guild in bot.guilds:
        interval = config_handler.get_interval(guild.id)
        scheduler.add_job(process_and_send_rss, 'interval', minutes=interval, args=[guild.id], id=f'process_rss_{guild.id}')
    scheduler.start()

# 启动bot并开始处理RSS
def run_bot():
    setup_scheduler()  # 启动调度器
    bot.loop.create_task(bot.start(DISCORD_TOKEN))
    bot.loop.run_forever()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    run_bot()
