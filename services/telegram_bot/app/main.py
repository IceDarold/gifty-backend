import asyncio
import json
import logging
import aio_pika
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, URLInputFile
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest

class EditSpider(StatesGroup):
    waiting_for_url = State()
    waiting_for_interval = State()
from services.telegram_bot.app.strings import STRINGS

from app.config import get_settings
from services.telegram_bot.app.client import TelegramInternalClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TelegramBot")

settings = get_settings()
bot = Bot(token=settings.telegram_bot_token)
dp = Dispatcher()
client = TelegramInternalClient(
    settings.api_base, 
    settings.internal_api_token, 
    settings.analytics_api_token
)

def get_lang(user_data: dict) -> str:
    return user_data.get("language", "ru") if user_data else "ru"

def has_permission(user_data: dict, permission: str) -> bool:
    if not user_data:
        return False
    perms = user_data.get("permissions", [])
    # Support for simple namespaced permissions
    return permission in perms or "all" in perms or f"{permission.split(':')[0]}:*" in perms

def t(key: str, lang: str):
    return STRINGS.get(lang, STRINGS["ru"]).get(key, key)

def get_main_keyboard(lang: str):
    keyboard = [
        [KeyboardButton(text=t("btn_stats", lang)), KeyboardButton(text=t("btn_health", lang))],
        [KeyboardButton(text=t("btn_scraping", lang)), KeyboardButton(text=t("btn_subs", lang))],
        [KeyboardButton(text=t("btn_help", lang)), KeyboardButton(text=t("lang_btn", lang))]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_stats_panel(lang: str):
    inline_kb = [
        [InlineKeyboardButton(text=t("stats_btn_summary", lang), callback_data="stats:summary")],
        [InlineKeyboardButton(text="📊 DAU (7d)", callback_data="stats:dau"),
         InlineKeyboardButton(text="📈 MAU (12m)", callback_data="stats:mau")],
        [InlineKeyboardButton(text=t("stats_btn_technical", lang), callback_data="stats:tech")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_lang_keyboard():
    inline_kb = [
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
         InlineKeyboardButton(text="🇺🇸 English", callback_data="lang:en")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

TOPICS = {
    "investors": "Investors",
    "partners": "Partners",
    "newsletter": "Newsletter",
    "system": "Monitoring",
    "scraping": "Scraping Status"
}

def get_subscription_keyboard(current_subs: list, lang: str):
    rows = []
    # Grid: 2 topics per row
    topic_keys = list(TOPICS.keys())
    for i in range(0, len(topic_keys), 2):
        row = []
        for j in range(2):
            if i + j < len(topic_keys):
                topic = topic_keys[i + j]
                label = TOPICS[topic]
                is_subbed = topic in current_subs
                status = "✅" if is_subbed else "❌"
                callback = f"sub_toggle:{topic}"
                row.append(InlineKeyboardButton(text=f"{status} {label}", callback_data=callback))
        rows.append(row)
    
    # Master toggles
    is_all = "all" in current_subs
    rows.append([
        InlineKeyboardButton(text=f"{'✅' if is_all else '❌'} 📢 Global Notifications (All)", callback_data="sub_toggle:all")
    ])
    
    # Quick actions
    rows.append([
        InlineKeyboardButton(text="🔔 Subscribe All", callback_data="sub_action:all_on"),
        InlineKeyboardButton(text="🔕 Unsubscribe All", callback_data="sub_action:all_off")
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=rows)

# --- Bot Handlers ---

@dp.message(Command("start"))
async def cmd_start(message: Message, command: CommandObject):
    subscriber = await client.get_subscriber(message.chat.id)
    lang = get_lang(subscriber)

    if not subscriber:
        if not command.args:
            await message.answer(t("provide_secret", "ru"), parse_mode="Markdown")
            return

        if command.args != settings.telegram_admin_secret:
            await message.answer(t("invalid_secret", "ru"))
            return

        subscriber = await client.create_subscriber(
            chat_id=message.chat.id,
            name=message.from_user.full_name,
            slug=message.from_user.username
        )
        if subscriber:
            await message.answer(t("welcome_new", lang), reply_markup=get_main_keyboard(lang))
            await message.answer(t("onboarding", lang), parse_mode="Markdown")
            
            # Notify existing admins about new registration
            reg_msg = (
                f"👤 *New Admin Registered*\n\n"
                f"Name: {message.from_user.full_name}\n"
                f"Username: @{message.from_user.username or 'N/A'}\n"
                f"Chat ID: `{message.chat.id}`"
            )
            # Find people subscribed to 'system' or just all
            system_subs = await client.get_topic_subscribers("system")
            for admin_sub in system_subs:
                if admin_sub["chat_id"] != message.chat.id:
                    try:
                        await bot.send_message(admin_sub["chat_id"], reg_msg, parse_mode="Markdown")
                    except: pass
        else:
            await message.answer("❌ Error during registration.")
    else:
        # User already registered, show onboarding
        await message.answer(t("welcome_back", lang), reply_markup=get_main_keyboard(lang))
        await message.answer(t("onboarding", lang), parse_mode="Markdown")

@dp.message(F.text.in_(["📊 Stats", "📊 Статистика"]))
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "analytics:view"):
        await message.answer(t("no_permission", lang))
        return

    await message.answer(
        t("stats_title", lang),
        reply_markup=get_stats_panel(lang),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("stats:"))
async def process_stats_callback(callback_query: CallbackQuery):
    action = callback_query.data.split(":")[1]
    sub = await client.get_subscriber(callback_query.message.chat.id)
    lang = get_lang(sub)

    if action == "summary":
        stats = await client.get_stats()
        if stats:
            text = (
                f"{t('stats_title', lang)}\n\n"
                f"👥 *DAU (24h):* {stats.get('dau', 0)}\n"
                f"📝 *Quiz Completion:* {stats.get('quiz_completion_rate', 0)}%\n"
                f"🖱 *Gift CTR:* {stats.get('gift_ctr', 0)}%\n"
                f"🚀 *Total Sessions:* {stats.get('total_sessions', 0)}\n"
            )
            await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=get_stats_panel(lang))
        else:
            await callback_query.answer("Error fetching stats")

    elif action in ["dau", "mau"]:
        is_mau = action == "mau"
        days = 30 if is_mau else 7
        trends = await client.get_trends(days=days)
        
        if not trends or not trends.get("dau_trend"):
            await callback_query.answer("No trend data available from PostHog")
            return

        labels = trends.get("dates", [])
        data = trends.get("dau_trend", [])
        
        # If MAU, we group by month if we had more data, but for now we show 30 days of DAU as a proxy or 7 days
        # The API gives us day-by-day.
        
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "DAU (PostHog Real-time)" if not is_mau else "MAU Proxy (30d)",
                    "data": data,
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "fill": True,
                    "tension": 0.4
                }]
            },
            "options": {
                "title": {"display": True, "text": f"{'30-Day' if is_mau else '7-Day'} PostHog Activity"}
            }
        }
        chart_url = f"https://quickchart.io/chart?c={json.dumps(chart_config)}&width=600&height=400&bkg=white"
        
        await callback_query.message.answer_photo(
            photo=URLInputFile(chart_url),
            caption=t("stats_mau_title" if is_mau else "stats_dau_title", lang),
            parse_mode="Markdown"
        )
        await callback_query.answer()

    elif action == "tech":
        health = await client.get_technical_health()
        if health:
            text = (
                f"{t('health_title', lang)}\n\n"
                f"⏱ *{t('health_latency', lang)}:* {health.get('api_latency_ms', 'N/A')}ms\n"
                f"🔥 *{t('health_errors', lang)}:* {health.get('error_rate_5xx', 0)}%\n"
                f"💾 *{t('health_memory', lang)}:* {health.get('redis_memory_mb', 0)}MB\n"
            )
            await callback_query.message.edit_text(text, parse_mode="Markdown", reply_markup=get_stats_panel(lang))
        else:
            await callback_query.answer("Error fetching health stats")

@dp.message(F.text.in_(["🚀 Health", "🚀 Состояние"]))
@dp.message(Command("health"))
async def cmd_health(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "system:health"):
        await message.answer(t("no_permission", lang))
        return

    health = await client.get_technical_health()
    if not health:
        await message.answer("❌ Error")
        return

    text = (
        f"{t('health_title', lang)}\n\n"
        f"⏱ *{t('health_latency', lang)}:* {health.get('api_latency_ms', 'N/A')}ms\n"
        f"🔥 *{t('health_errors', lang)}:* {health.get('error_rate_5xx', 0)}%\n"
        f"💾 *{t('health_memory', lang)}:* {health.get('redis_memory_mb', 0)}MB\n"
        f"💿 *{t('health_disk', lang)}:* {health.get('disk_usage_percent', 0)}%\n"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text.in_(["🕷 Scraping", "🕷 Парсинг"]))
@dp.message(Command("scraping"))
async def cmd_scraping(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "parsing:manage"):
        await message.answer(t("no_permission", lang))
        return

    mon = await client.get_scraping_monitoring()
    sources = await client.get_sources()

    if not mon or not sources:
        await message.answer("❌ Error fetching data")
        return

    text = (
        f"{t('scraping_title', lang)}\n\n"
        f"✅ *{t('scraping_active', lang)}:* {mon.get('active_sources', 0)}\n"
        f"🧩 *{t('scraping_unmapped', lang)}:* {mon.get('unmapped_categories', 0)}\n"
        f"📦 *{t('scraping_items', lang)}:* {mon.get('items_scraped_24h', 0)}\n\n"
        f"*👇 Connected Spiders:*"
    )
    
    # Group by site_key and pick the best representative
    site_groups = {}
    for s in sources:
        key = s.get("site_key")
        stype = s.get("type", "list")
        
        if key not in site_groups:
            site_groups[key] = s
        else:
            current_best = site_groups[key].get("type", "list")
            if stype == "hub":
                site_groups[key] = s
            elif stype == "sitemap" and current_best == "list":
                site_groups[key] = s
    
    sorted_sites = sorted(site_groups.values(), key=lambda x: x.get("site_key"))

    text = (
        f"{t('scraping_title', lang)}\n\n"
        f"✅ *{t('scraping_active', lang)}:* {mon.get('active_sources', 0)}\n"
        f"🧩 *{t('scraping_unmapped', lang)}:* {mon.get('unmapped_categories', 0)}\n"
        f"📦 *{t('scraping_items', lang)}:* {mon.get('items_scraped_24h', 0)}\n\n"
        f"*👇 Sites Connected ({len(sorted_sites)}):*"
    )
    
    buttons = []
    row = []
    for s in sorted_sites:
        key = s.get("site_key")
        is_active = s.get("is_active")
        status = s.get("status", "waiting")
        
        status_icon = "🟢" if is_active else "🔴"
        if status == "running": 
            status_icon = "🔄"
        elif status == "broken" or s.get("config", {}).get("fix_required"):
             status_icon = "🛠"
             
        row.append(InlineKeyboardButton(text=f"{status_icon} {key}", callback_data=f"spider:view:{s['id']}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

async def _show_spider_view(callback_query: CallbackQuery, source_id: int, lang: str):
    source = await client.get_source_details(source_id)
    if not source:
        await callback_query.answer("❌ Source not found", show_alert=True)
        return

    is_active = source.get("is_active")
    status = source.get("status", "waiting")
    
    status_txt = "🟢 Waiting" if is_active else "🔴 Disabled"
    if status == "running":
        status_txt = "🔄 Running"
    elif status == "broken" or source.get("config", {}).get("fix_required"):
        status_txt = "🛠 Need to Fix"

    last_run = source.get("last_synced_at")
    last_run_str = last_run.replace("T", " ")[:16] if last_run else "Never"
    next_run = source.get("next_sync_at")
    next_run_str = next_run.replace("T", " ")[:16] if next_run else "Pending"
    
    # Extended Stats
    created_at = source.get("created_at")
    added_str = created_at [:10] if created_at else "?"
    total_items = source.get("total_items", 0)
    new_items = source.get("last_run_new", 0)

    err_msg = ""
    if source.get("config", {}).get("last_error"):
        err_msg = f"\n⚠️ *Last Error:*\n`{source['config']['last_error']}`\n"
        
    text = (
        f"🕸 *Spider: {source['site_key']}*\n"
        f"🔗 `{source['url']}`\n"
        f"Status: *{status_txt}*\n"
        f"📅 Added: `{added_str}`\n"
        f"🕒 Interval: `{source['refresh_interval_hours']}h`\n\n"
        f"📦 Total Items: `{total_items}`\n"
        f"🆕 New Last Run: `{new_items}`\n\n"
        f"⏳ Last: `{last_run_str}`\n"
        f"🔜 Next: `{next_run_str}`\n"
        f"{err_msg}"
    )

    source_type = source.get("type", "list")
    site_key = source.get("site_key")

    btns = []
    
    # Row 1: Run Actions
    if source_type == "hub":
        btns.append([
            InlineKeyboardButton(text="🔍 Discovery", callback_data=f"spider:run:{source_id}:discovery"),
            InlineKeyboardButton(text="🚀 Run Deep", callback_data=f"spider:run:{source_id}:deep")
        ])
    else:
        btns.append([
            InlineKeyboardButton(text="▶️ Force Run", callback_data=f"spider:run:{source_id}"),
            InlineKeyboardButton(text="🛑 Disable" if is_active else "🟢 Enable", callback_data=f"spider:toggle:{source_id}")
        ])

    # Row 2: Management
    if source_type == "hub":
        btns.append([
            InlineKeyboardButton(text="📁 Categories", callback_data=f"spider:cats:{site_key}:0"),
            InlineKeyboardButton(text="🛑 Disable" if is_active else "🟢 Enable", callback_data=f"spider:toggle:{source_id}")
        ])
    else:
        btns.append([
            InlineKeyboardButton(text="🔗 Edit URL", callback_data=f"spider:edit_url:{source_id}"),
            InlineKeyboardButton(text="🕒 Edit Time", callback_data=f"spider:edit_int:{source_id}")
        ])

    # Row 3: Stats & Logs
    btns.append([
        InlineKeyboardButton(text="📈 Growth Graph", callback_data=f"spider:graph:{source_id}"),
        InlineKeyboardButton(text="📝 Last Logs", callback_data=f"spider:logs:{source_id}")
    ])

    # Row 4: Navigation
    if source_type == "list":
        # Find the hub for this site to go back to
        btns.append([InlineKeyboardButton(text="🔙 Back to Site", callback_data=f"spider:back_hub:{site_key}")])
    else:
        btns.append([InlineKeyboardButton(text="🔙 Back to List", callback_data="spider:list:0")])
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), parse_mode="Markdown")
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise

@dp.callback_query(F.data.startswith("spider:"))
async def process_spider_action(callback_query: CallbackQuery, state: FSMContext):
    parts = callback_query.data.split(":")
    action = parts[1]
    
    sub = await client.get_subscriber(callback_query.message.chat.id)
    lang = get_lang(sub)
    if not has_permission(sub, "parsing:manage"):
        await callback_query.answer(t("no_permission", lang), show_alert=True)
        return

    if action == "view":
        source_id = int(parts[2])
        await _show_spider_view(callback_query, source_id, lang)

    elif action == "list":
        mon = await client.get_scraping_monitoring()
        all_sources = await client.get_sources()
        
        # Group by site_key and pick the best representative
        # Priority: hub > sitemap > list
        site_groups = {}
        for s in all_sources:
            key = s.get("site_key")
            stype = s.get("type", "list")
            
            if key not in site_groups:
                site_groups[key] = s
            else:
                current_best = site_groups[key].get("type", "list")
                # Hub is better than anything
                if stype == "hub":
                    site_groups[key] = s
                # Sitemap is better than list
                elif stype == "sitemap" and current_best == "list":
                    site_groups[key] = s
        
        sources = sorted(site_groups.values(), key=lambda x: x.get("site_key"))
            
        text = (
            f"*🕷 Scraping Monitoring*\n\n"
            f"✅ Active: {mon.get('active_sources', 0)}\n"
            f"*👇 Sites Connected ({len(sources)}):*"
        )
        buttons = []
        row = []
        for s in sources:
            is_active = s.get("is_active")
            status = s.get("status", "waiting")
            status_icon = "🟢" if is_active else "🔴"
            if status == "running": status_icon = "🔄"
            elif status == "broken" or s.get("config", {}).get("fix_required"): status_icon = "🛠"
            
            row.append(InlineKeyboardButton(text=f"{status_icon} {s['site_key']}", callback_data=f"spider:view:{s['id']}"))
            if len(row) == 2:
                buttons.append(row)
                row = []
        if row: buttons.append(row)
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

    elif action == "cats":
        site_key = parts[2]
        page = int(parts[3])
        all_sources = await client.get_sources()
        # Find all sources for this site that are NOT hubs
        all_cats = [s for s in all_sources if s.get("site_key") == site_key and s.get("type") != "hub"]
        
        page_size = 10
        start = page * page_size
        end = start + page_size
        current_cats = all_cats[start:end]
        
        text = f"📁 *Categories: {site_key}* (Page {page + 1}/{max(1, (len(all_cats)+page_size-1)//page_size)})\nTotal: {len(all_cats)}"
        buttons = []
        for c in current_cats:
            # Allow wrapping by using 1 item per row and longer limit
            full_name = c.get("config", {}).get("discovery_name") or c.get("url").split("/")[-1]
            # Limit to ~200 chars as requested
            name = (full_name[:200] + '...') if len(full_name) > 200 else full_name
            
            status_icon = "🟢" if c.get("is_active") else "🔴"
            if c.get("status") == "running": status_icon = "🔄"
            
            buttons.append([InlineKeyboardButton(text=f"{status_icon} {name}", callback_data=f"spider:view:{c['id']}")])
            
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"spider:cats:{site_key}:{page-1}"))
        if end < len(all_cats):
            nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"spider:cats:{site_key}:{page+1}"))
        if nav_row:
            buttons.append(nav_row)
            
        # Back to the Hub source
        hub = next((s for s in all_sources if s.get("site_key") == site_key and s.get("type") == "hub"), None)
        if hub:
            buttons.append([InlineKeyboardButton(text="🔙 Back to Site", callback_data=f"spider:view:{hub['id']}")])
        else:
            buttons.append([InlineKeyboardButton(text="🔙 Back to List", callback_data="spider:list:0")])
            
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="Markdown")

    elif action == "back_hub":
        site_key = parts[2]
        sources = await client.get_sources()
        hub = next((s for s in sources if s.get("site_key") == site_key and s.get("type") == "hub"), None)
        if hub:
            await _show_spider_view(callback_query, hub["id"], lang)
        else:
            await callback_query.answer("Hub not found")

    elif action == "toggle":
        source_id = int(parts[2])
        source = await client.get_source_details(source_id)
        new_state = not source.get("is_active")
        await client.toggle_source(source_id, new_state)
        
        # Re-fetch and refresh UI
        await asyncio.sleep(0.3)
        await _show_spider_view(callback_query, source_id, lang)
        await callback_query.answer()
        return

    elif action == "run":
        source_id = int(parts[2])
        strategy = parts[3] if len(parts) > 3 else None
        success = await client.force_run_source(source_id, strategy=strategy)
        
        if success:
            # Re-fetch and refresh UI
            await asyncio.sleep(0.3)
            await _show_spider_view(callback_query, source_id, lang)
            
            msg = "🚀 Task scheduled!"
            if strategy == "discovery": msg = "🔍 Discovery started!"
            elif strategy == "deep": msg = "🦖 Deep crawling started!"
            
            await callback_query.answer(msg, show_alert=True)
        else:
            await callback_query.answer("❌ Failed to schedule task", show_alert=True)
        return

    elif action == "edit_url":
        source_id = int(parts[2])
        await state.update_data(source_id=source_id)
        await state.set_state(EditSpider.waiting_for_url)
        await callback_query.message.answer(t("edit_url", lang))
        await callback_query.answer()

    elif action == "edit_int":
        source_id = int(parts[2])
        await state.update_data(source_id=source_id)
        await state.set_state(EditSpider.waiting_for_interval)
        await callback_query.message.answer(t("edit_interval", lang))
        await callback_query.answer()

    elif action == "graph":
        source_id = int(parts[2])
        source = await client.get_source_details(source_id)
        
        if not source or not source.get("history"):
            await callback_query.answer("No history available", show_alert=True)
            return
            
        history = source["history"]
        # Prepare data for graph
        dates = [h["date"][:10] for h in history][::-1]
        counts = [h["items_new"] for h in history][::-1]
        
        # Simple QuickChart URL
        chart_config = {
            "type": "line",
            "data": {
                "labels": dates,
                "datasets": [{
                    "label": "New Items",
                    "data": counts,
                    "fill": False,
                    "borderColor": "blue",
                    "tension": 0.1
                }]
            }
        }
        import json
        from urllib.parse import quote
        chart_url = f"https://quickchart.io/chart?c={quote(json.dumps(chart_config))}"
        
        await callback_query.message.answer_photo(
            photo=chart_url,
            caption=f"📈 New items growth for {source['site_key']}"
        )
        await callback_query.answer()

    elif action == "logs":
        source_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
        source = await client.get_source_details(source_id)
        
        if not source:
            await callback_query.answer("❌ Source not found", show_alert=True)
            return

        logs = source.get("config", {}).get("last_logs", "No logs available yet.")
        
        # Split logs into pages of ~2000 chars (monospaced lines take more space in markup)
        chunk_size = 2000
        log_pages = [logs[i:i+chunk_size] for i in range(0, len(logs), chunk_size)]
        if not log_pages: log_pages = ["No logs."]
        
        if page >= len(log_pages): page = len(log_pages) - 1
        
        # Wrapping is achieved by using regular text or inline code instead of code blocks
        # We'll use a simple approach: just text, so it wraps perfectly on mobile
        content = log_pages[page].replace("`", "'") # escape backticks
        
        text = (
            f"📋 *Last Logs: {source['site_key']}* (Page {page + 1}/{len(log_pages)})\n\n"
            f"{content}"
        )
        
        btns = []
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"spider:logs:{source_id}:{page-1}"))
        if page < len(log_pages) - 1:
            nav_row.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"spider:logs:{source_id}:{page+1}"))
        
        if nav_row:
            btns.append(nav_row)
            
        btns.append([
            InlineKeyboardButton(text="🔄 Refresh", callback_data=f"spider:logs:{source_id}:0"),
            InlineKeyboardButton(text="🔙 Back", callback_data=f"spider:view:{source_id}")
        ])
        
        try:
            await callback_query.message.edit_text(
                text, 
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns), 
                parse_mode="Markdown"
            )
        except Exception as e:
            # Final fallback if still too long
            await callback_query.message.edit_text(
                f"📋 *Logs (Error displays)*\nError: {str(e)}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=btns)
            )
        await callback_query.answer()

@dp.message(EditSpider.waiting_for_url)
async def process_url_update(message: Message, state: FSMContext):
    data = await state.get_data()
    source_id = data['source_id']
    new_url = message.text.strip()
    
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not new_url.startswith("http"):
        await message.answer(t("invalid_input", lang))
        return
        
    success = await client.update_source(source_id, {"url": new_url})
    if success:
        await message.answer(t("update_success", lang))
    else:
        await message.answer("❌ API Error")
    
    await state.clear()
    # Return to management - we use cmd_scraping as a starting point
    await cmd_scraping(message)

@dp.message(EditSpider.waiting_for_interval)
async def process_interval_update(message: Message, state: FSMContext):
    data = await state.get_data()
    source_id = data['source_id']
    
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    try:
        new_interval = int(message.text.strip())
        if new_interval <= 0: raise ValueError()
    except ValueError:
        await message.answer(t("invalid_input", lang))
        return
        
    success = await client.update_source(source_id, {"refresh_interval_hours": new_interval})
    if success:
        await message.answer(t("update_success", lang))
    else:
        await message.answer("❌ API Error")
    
    await state.clear()
    await cmd_scraping(message)

@dp.message(F.text.in_(["ℹ️ Help", "ℹ️ Помощь"]))
@dp.message(Command("help"))
async def cmd_help(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    await message.answer(f"{t('help_title', lang)}\n\n{t('help_text', lang)}", parse_mode="Markdown")

@dp.message(F.text.in_(["🌐 Language / Язык", "🌐 Язык / Language"]))
async def cmd_lang(message: Message):
    await message.answer("Select your language / Выберите язык:", reply_markup=get_lang_keyboard())

@dp.callback_query(F.data.startswith("lang:"))
async def process_lang_callback(callback_query: CallbackQuery):
    lang = callback_query.data.split(":")[1]
    success = await client.set_language(callback_query.message.chat.id, lang)
    if success:
        await callback_query.answer(t("lang_switched", lang))
        await callback_query.message.answer(
            t("lang_switched", lang),
            reply_markup=get_main_keyboard(lang)
        )
    else:
        await callback_query.answer("Error updating language")

@dp.message(Command("subscribe"))
async def cmd_subscribe(message: Message, command: CommandObject):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if not sub:
        await message.answer(t("onboarding", lang))
        return

    if not command.args:
        await message.answer(
            f"🔔 *{t('btn_subs', lang)}*", 
            reply_markup=get_subscription_keyboard(sub.get("subscriptions", []), lang),
            parse_mode="Markdown"
        )
        return

    topic = command.args.strip().lower()
    success = await client.subscribe(message.chat.id, topic)
    if success:
        await message.answer(f"🔔 Subscribed to topic: *{topic}*", parse_mode="Markdown")
    else:
        await message.answer("❌ Failed to subscribe.")

@dp.message(Command("info"))
async def cmd_info(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    text = (
        f"🏷 *Chat ID:* `{message.chat.id}`\n"
        f"🌍 *Language:* {get_lang(sub)}\n"
        f"🔔 *Subscriptions:* {', '.join(sub.get('subscriptions', [])) if sub else 'None'}"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("sub_toggle:"))
async def process_sub_toggle(callback_query: CallbackQuery):
    topic = callback_query.data.split(":")[1]
    chat_id = callback_query.message.chat.id
    
    sub = await client.get_subscriber(chat_id)
    if not sub:
        await callback_query.answer("Not registered")
        return
    
    current_subs = sub.get("subscriptions", [])
    if topic in current_subs:
        await client.unsubscribe(chat_id, topic)
        await callback_query.answer(f"🔕 Unsubscribed: {topic}")
    else:
        await client.subscribe(chat_id, topic)
        await callback_query.answer(f"🔔 Subscribed: {topic}")
    
    # Refresh the keyboard
    new_sub = await client.get_subscriber(chat_id)
    lang = get_lang(new_sub)
    try:
        await callback_query.message.edit_reply_markup(
            reply_markup=get_subscription_keyboard(new_sub.get("subscriptions", []), lang)
        )
    except:
        pass # Ignore "message is not modified"

@dp.callback_query(F.data.startswith("sub_action:"))
async def process_sub_action(callback_query: CallbackQuery):
    action = callback_query.data.split(":")[1]
    chat_id = callback_query.message.chat.id
    
    if action == "all_on":
        for topic in ["investors", "partners", "newsletter", "system", "scraping", "all"]:
            await client.subscribe(chat_id, topic)
        await callback_query.answer("🔔 Subscribed to all")
    elif action == "all_off":
        sub = await client.get_subscriber(chat_id)
        if sub:
            for topic in sub.get("subscriptions", []):
                await client.unsubscribe(chat_id, topic)
        await callback_query.answer("🔕 Unsubscribed from all")
    
    new_sub = await client.get_subscriber(chat_id)
    lang = get_lang(new_sub)
    await callback_query.message.edit_reply_markup(
        reply_markup=get_subscription_keyboard(new_sub.get("subscriptions", []), lang)
    )

@dp.message(Command("unsubscribe"))
async def cmd_unsubscribe(message: Message, command: CommandObject):
    if not command.args:
        await message.answer("Usage: `/unsubscribe <topic>`", parse_mode="Markdown")
        return

    topic = command.args.strip().lower()
    success = await client.unsubscribe(message.chat.id, topic)
    if success:
        await message.answer(f"🔕 Unsubscribed from topic: *{topic}*", parse_mode="Markdown")
    else:
        await message.answer("❌ Failed to unsubscribe.")

@dp.message(F.text.in_(["🔔 Подписки", "🔔 Мои подписки", "🔔 Subscriptions", "🔔 My Subs"]))
@dp.message(Command("my_subscriptions"))
async def cmd_my_subs(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if sub:
        await message.answer(
            f"<b>{t('subs_title', lang)}</b>", 
            reply_markup=get_subscription_keyboard(sub.get("subscriptions", []), lang),
            parse_mode="HTML"
        )
    else:
        await message.answer(t("onboarding", lang), parse_mode="Markdown")

# Removed unsub callback - replaced by sub_toggle

@dp.callback_query(F.data.startswith("handled:"))
async def process_handled_callback(callback_query: types.CallbackQuery):
    action = callback_query.data.split(":")[1]
    await callback_query.answer(f"✅ Noted as handled: {action}")
    # Update message text to show it was handled
    await callback_query.message.edit_text(
        f"{callback_query.message.text}\n\n✅ *Handled by {callback_query.from_user.first_name}*",
        parse_mode="Markdown"
    )

# --- RabbitMQ Consumer ---

async def consume_notifications():
    """
    Background task to consume messages from RabbitMQ and send them to Telegram.
    """
    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue("notifications", durable=True)

        logger.info("RabbitMQ Consumer started. Waiting for notifications...")
        
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        topic = data.get("topic")
                        text = data.get("text")
                        
                        logger.info(f"Processing notification for topic: {topic}. Text preview: {text[:50]}...")
                        
                        # Find all subscribers for this topic
                        subscribers = await client.get_topic_subscribers(topic)
                        logger.info(f"Found {len(subscribers)} potential subscribers for topic {topic}")
                        
                        for sub in subscribers:
                            try:
                                logger.info(f"Sending message to chat_id: {sub.get('chat_id')}")
                                reply_markup = None
                                # Add buttons for investor notifications
                                if topic == "investors":
                                    inline_kb = [
                                        [InlineKeyboardButton(text="✅ Mark Handled", callback_data="handled:investor")]
                                    ]
                                    reply_markup = InlineKeyboardMarkup(inline_keyboard=inline_kb)

                                await bot.send_message(
                                    chat_id=sub["chat_id"],
                                    text=text,
                                    parse_mode="HTML",
                                    reply_markup=reply_markup
                                )
                            except Exception as e:
                                logger.error(f"Failed to send TG message to {sub['chat_id']}: {e}")
                                
                    except Exception as e:
                        logger.error(f"Error processing RabbitMQ message: {e}")

async def main():
    # Run both bot polling and RabbitMQ consumer concurrently
    await asyncio.gather(
        dp.start_polling(bot),
        consume_notifications()
    )

if __name__ == "__main__":
    asyncio.run(main())
