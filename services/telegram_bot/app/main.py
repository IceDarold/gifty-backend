import asyncio
import json
import logging
import re
import aio_pika
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, 
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, URLInputFile,
    WebAppInfo
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramBadRequest
from datetime import datetime

class EditSpider(StatesGroup):
    waiting_for_url = State()
    waiting_for_interval = State()

class NewTask(StatesGroup):
    waiting_for_title = State()

class ConnectWeeek(StatesGroup):
    waiting_for_token = State()

class RescheduleTask(StatesGroup):
    waiting_for_date = State()
    waiting_for_reason = State()

class AddUser(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()
    waiting_for_name = State()
    waiting_for_mentor = State()
    waiting_for_permissions = State()
from services.telegram_bot.app.strings import STRINGS

from app.config import get_settings
from services.telegram_bot.app.client import TelegramInternalClient
from app.services.weeek import WeeekClient

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
weeek_client = WeeekClient()

async def smart_edit(message: Message, text: str = None, reply_markup = None, photo_url: str = None, parse_mode: str = "Markdown"):
    """
    Smartly edits a message or sends a new one if media type changes.
    Prevents 'there is no text in the message to edit' errors.
    """
    try:
        # CASE 1: We want to show a PHOTO
        if photo_url:
            media = types.InputMediaPhoto(media=URLInputFile(photo_url), caption=text, parse_mode=parse_mode)
            if message.photo:
                # Photo -> Photo: Edit media
                await message.edit_media(media=media, reply_markup=reply_markup)
            else:
                # Text -> Photo: Delete text, Send photo
                await message.delete()
                await message.answer_photo(photo=URLInputFile(photo_url), caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
                
        # CASE 2: We want to show TEXT
        else:
            if message.text:
                # Text -> Text: Edit text
                await message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                # Photo -> Text: Delete photo, Send text
                await message.delete()
                await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Smart edit failed: {e}")
        # Fallback: just answer
        if photo_url:
            await message.answer_photo(photo=URLInputFile(photo_url), caption=text, parse_mode=parse_mode, reply_markup=reply_markup)
        else:
            await message.answer(text, parse_mode=parse_mode, reply_markup=reply_markup)

def get_lang(user_data: dict) -> str:
    return user_data.get("language", "ru") if user_data else "ru"

def has_permission(user_data: dict, permission: str) -> bool:
    if not user_data:
        return False
    if user_data.get("role") == "superadmin":
        return True
    perms = user_data.get("permissions", [])
    # Support for simple namespaced permissions
    return permission in perms or "all" in perms or f"{permission.split(':')[0]}:*" in perms

def t(key: str, lang: str, **kwargs):
    text = STRINGS.get(lang, STRINGS["ru"]).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

def get_main_keyboard(lang: str, sub: dict = None):
    keyboard = []
    
    # Row 1: Stats & Health
    row1 = []
    if has_permission(sub, "stats:view"):
        row1.append(KeyboardButton(text=t("btn_stats", lang)))
    if has_permission(sub, "system:health"):
        row1.append(KeyboardButton(text=t("btn_health", lang)))
    if row1:
        keyboard.append(row1)
        
    # Row 2: Scraping & Subs & Tasks
    row2 = []
    if has_permission(sub, "parsing:manage"):
        if settings.telegram_webapp_url:
            row2.append(KeyboardButton(text=t("btn_scraping", lang), web_app=WebAppInfo(url=settings.telegram_webapp_url)))
        else:
            row2.append(KeyboardButton(text=t("btn_scraping", lang)))
    
    
    if has_permission(sub, "tasks:manage"):
        row2.append(KeyboardButton(text=t("btn_tasks", lang)))
    else:
        # Show Connect button only if NOT connected (i.e. no permission)
        row2.append(KeyboardButton(text=t("weeek_connect_btn", lang)))
        
    row2.append(KeyboardButton(text=t("btn_subs", lang)))
    keyboard.append(row2)
    
    # Row 3: Admin tools
    row3 = [KeyboardButton(text=t("btn_help", lang)), KeyboardButton(text=t("lang_btn", lang))]
    if sub and sub.get("role") == "superadmin":
        row3.insert(0, KeyboardButton(text=t("btn_users", lang)))
    keyboard.append(row3)
    
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

AVAILABLE_PERMS = ["all", "stats:view", "system:health", "parsing:manage", "notifications:manage", "tasks:manage"]

def get_permissions_keyboard(selected: list, lang: str):
    rows = []
    row = []
    for perm in AVAILABLE_PERMS:
        status = "✅" if perm in selected else "❌"
        row.append(InlineKeyboardButton(text=f"{status} {perm}", callback_data=f"invite_perm:toggle:{perm}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([
        InlineKeyboardButton(text=t("perm_save", lang), callback_data="invite_perm:save"),
        InlineKeyboardButton(text=t("perm_cancel", lang), callback_data="invite_perm:cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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
            username = (message.from_user.username or "").strip()
            if not username:
                await message.answer(t("invite_need_username", "ru"))
                return
            claimed = await client.claim_invite(
                username=username,
                password=command.args,
                chat_id=message.chat.id,
                name=message.from_user.full_name
            )
            if claimed:
                lang = get_lang(claimed)
                await message.answer(
                    t("welcome_invited", lang, name=claimed.get("name") or message.from_user.full_name),
                    reply_markup=get_main_keyboard(lang, claimed)
                )
                await message.answer(t("onboarding", lang), parse_mode="Markdown")
                return
            await message.answer(t("invalid_secret", "ru"))
            return

        subscriber = await client.create_subscriber(
            chat_id=message.chat.id,
            name=message.from_user.full_name,
            slug=message.from_user.username
        )
        if subscriber:
            lang = get_lang(subscriber)
            try:
                await message.answer(t("welcome_new", lang), reply_markup=get_main_keyboard(lang, subscriber))
            except TelegramBadRequest as e:
                if "Web App" in str(e):
                    await message.answer(t("welcome_new", lang))
                    await message.answer(f"⚠️ <b>HTTPS Required</b>\n\nOpen Dashboard: {settings.telegram_webapp_url}", parse_mode="HTML")
                else:
                    raise e
            
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
        try:
            await message.answer(t("welcome_back", lang), reply_markup=get_main_keyboard(lang, subscriber))
        except TelegramBadRequest as e:
            if "Web App" in str(e):
                await message.answer(t("welcome_back", lang))
                await message.answer(f"⚠️ <b>HTTPS Required</b>\n\nOpen Dashboard: {settings.telegram_webapp_url}", parse_mode="HTML")
            else:
                raise e

@dp.message(Command("become_superadmin"))
async def cmd_become_superadmin(message: Message, command: CommandObject):
    if not command.args:
        return
    
    if command.args == settings.telegram_superadmin_secret:
        success = await client.set_role(message.chat.id, "superadmin")
        if success:
            sub = await client.get_subscriber(message.chat.id)
            lang = get_lang(sub)
            await message.answer(t("become_superadmin_success", lang), reply_markup=get_main_keyboard(lang, sub))

@dp.message(F.text.in_(["👥 Пользователи", "👥 Users"]))
@dp.message(Command("users"))
async def cmd_users(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    if not sub or sub.get("role") != "superadmin":
        lang = get_lang(sub)
        await message.answer(t("superadmin_only", lang))
        return

    lang = get_lang(sub)
    users = await client.get_all_subscribers()
    
    rows = []
    for u in users:
        role_label = "👑" if u.get("role") == "superadmin" else ("🛠" if u.get("role") == "admin" else "👤")
        rows.append([
            InlineKeyboardButton(text=f"{role_label} {u.get('name') or u.get('slug') or u.get('chat_id')}", callback_data=f"user:details:{u.get('chat_id')}")
        ])
    rows.append([InlineKeyboardButton(text=t("btn_add_user", lang), callback_data="user:add")])
    
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await message.answer(t("users_title", lang), reply_markup=markup)

async def _show_user_details(callback_query: CallbackQuery, user_id: int, lang: str):
    user = await client.get_subscriber(user_id)
    if not user:
        await callback_query.answer("User not found")
        return
        
    text = t("user_details", lang, name=user.get("name", "N/A"), slug=user.get("slug", "N/A"), role=user.get("role"), chat_id=user.get("chat_id"))
    
    rows = [
        [InlineKeyboardButton(text="Promotion to Admin", callback_data=f"user:set_role:{user_id}:admin")],
        [InlineKeyboardButton(text="Demote to User", callback_data=f"user:set_role:{user_id}:user")],
        [InlineKeyboardButton(text=t("btn_manage_perms", lang), callback_data=f"user:perms_list:{user_id}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="user:list:0")]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")

async def _show_perms_list(callback_query: CallbackQuery, user_id: int, lang: str):
    user = await client.get_subscriber(user_id)
    user_perms = user.get("permissions") or []
    is_super = user.get("role") == "superadmin"
    AVAILABLE_PERMS = ["all", "stats:view", "system:health", "parsing:manage", "notifications:manage", "tasks:manage"]
    
    text = t("perms_list_title", lang, name=user.get("name") or user.get("slug") or user.get("chat_id"))
    if is_super:
        text += f"\n\n👑 *Inherited from Superadmin*"
        
    rows = []
    for p in AVAILABLE_PERMS:
        is_active = p in user_perms or "all" in user_perms or is_super
        status = t("perm_status_active", lang) if is_active else t("perm_status_inactive", lang)
        rows.append([InlineKeyboardButton(text=f"{status} {p}", callback_data=f"user:perms_view:{user_id}:{p}")])
    
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data=f"user:details:{user_id}")])
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

async def _show_perm_view(callback_query: CallbackQuery, user_id: int, perm_key: str, lang: str):
    user = await client.get_subscriber(user_id)
    user_perms = user.get("permissions") or []
    is_super = user.get("role") == "superadmin"
    
    is_active = perm_key in user_perms or "all" in user_perms or is_super
        
    perm_desc_dict = STRINGS.get(lang, STRINGS["ru"]).get("perm_descs", {})
    desc = perm_desc_dict.get(perm_key, "No description available.")
    
    text = (
        f"🔐 *{t('perm_info_title', lang, perm=perm_key)}*\n\n"
        f"{desc}\n\n"
        f"Status: {t('perm_status_active' if is_active else 'perm_status_inactive', lang)}"
    )
    
    btn_text = t("btn_revoke" if is_active else "btn_grant", lang)
    toggle_action = "revoke" if is_active else "grant"
    
    rows = [
        [InlineKeyboardButton(text=btn_text, callback_data=f"user:perms_toggle:{user_id}:{toggle_action}:{perm_key}")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"user:perms_list:{user_id}")]
    ]
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")

@dp.callback_query(F.data.startswith("user:"))
async def handle_user_actions(callback_query: CallbackQuery, state: FSMContext):
    admin_sub = await client.get_subscriber(callback_query.message.chat.id)
    if not admin_sub or admin_sub.get("role") != "superadmin":
        await callback_query.answer(t("superadmin_only", get_lang(admin_sub)), show_alert=True)
        return

    lang = get_lang(admin_sub)
    data = callback_query.data
    parts = data.split(":")
    action = parts[1]
    
    # Common permissions to manage
    # AVAILABLE_PERMS = ["all", "stats:view", "system:health", "parsing:manage", "notifications:manage"] # Moved to _show_perms_list

    if action == "details":
        await _show_user_details(callback_query, int(parts[2]), lang)
    elif action == "add":
        await state.clear()
        await state.set_state(AddUser.waiting_for_username)
        await callback_query.message.answer(t("add_user_username", lang))
        await callback_query.answer()

    elif action == "perms_list":
        await _show_perms_list(callback_query, int(parts[2]), lang)

    elif action == "perms_view":
        # pattern: user:perms_view:user_id:perm_key
        # We need to re-parse because of potential colons in perm_key
        v_parts = data.split(":", 3)
        await _show_perm_view(callback_query, int(v_parts[2]), v_parts[3], lang)

    elif action == "perms_toggle":
        # pattern: user:perms_toggle:user_id:grant|revoke:perm_key
        t_parts = data.split(":", 4)
        user_id = int(t_parts[2])
        toggle_type = t_parts[3] 
        perm_key = t_parts[4]
        
        user = await client.get_subscriber(user_id)
        current_perms = user.get("permissions") or []
        
        if toggle_type == "grant":
            if perm_key not in current_perms:
                current_perms.append(perm_key)
        else:
            if perm_key in current_perms:
                current_perms.remove(perm_key)
            if perm_key == "all" and "all" in current_perms:
                current_perms.remove("all")
        
        await client.set_permissions(user_id, current_perms)
        await callback_query.answer(t("perms_updated", lang))
        
        # Immediate UI refresh: reload the view with updated data
        # Correctly reconstruct the data to avoid split errors
        # callback_query.data = f"user:perms_view:{user_id}:{perm_key}" # Replaced with direct call
        await _show_perm_view(callback_query, user_id, perm_key, lang)

    elif action == "set_role":
        user_id = int(parts[2])
        new_role = parts[3]
        user = await client.get_subscriber(user_id)
        await client.set_role(user_id, new_role)
        await callback_query.answer(t("role_changed", lang, name=user.get('name', 'User'), role=new_role))
        # Refresh details
        # callback_query.data = f"user:details:{user_id}" # Replaced with direct call
        await _show_user_details(callback_query, user_id, lang)

    elif action == "list":
        users = await client.get_all_subscribers()
        rows = []
        for u in users:
            role_label = "👑" if u.get("role") == "superadmin" else ("🛠" if u.get("role") == "admin" else "👤")
            rows.append([
                InlineKeyboardButton(text=f"{role_label} {u.get('name') or u.get('slug') or u.get('chat_id')}", callback_data=f"user:details:{u.get('chat_id')}")
            ])
        rows.append([InlineKeyboardButton(text=t("btn_add_user", lang), callback_data="user:add")])
        await callback_query.message.edit_text(t("users_title", lang), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
        await callback_query.answer()@dp.message(AddUser.waiting_for_username)
async def process_add_user_username(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if not sub or sub.get("role") != "superadmin":
        await message.answer(t("superadmin_only", lang))
        await state.clear()
        return
    username = message.text.strip().lstrip("@").lower()
    if not re.match(r"^[a-z0-9_]{3,32}$", username):
        await message.answer(t("add_user_username_invalid", lang))
        return
    await state.update_data(username=username)
    await state.set_state(AddUser.waiting_for_password)
    await message.answer(t("add_user_password", lang))

@dp.message(AddUser.waiting_for_password)
async def process_add_user_password(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if not sub or sub.get("role") != "superadmin":
        await message.answer(t("superadmin_only", lang))
        await state.clear()
        return
    password = message.text.strip()
    if len(password) < 4:
        await message.answer(t("add_user_password_invalid", lang))
        return
    await state.update_data(password=password)
    await state.set_state(AddUser.waiting_for_name)
    await message.answer(t("add_user_name", lang))

@dp.message(AddUser.waiting_for_name)
async def process_add_user_name(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if not sub or sub.get("role") != "superadmin":
        await message.answer(t("superadmin_only", lang))
        await state.clear()
        return
    name = message.text.strip()
    if len(name) < 2:
        await message.answer(t("add_user_name_invalid", lang))
        return
    await state.update_data(name=name)
    await state.set_state(AddUser.waiting_for_mentor)
    await message.answer(t("add_user_mentor", lang))

@dp.message(AddUser.waiting_for_mentor)
async def process_add_user_mentor(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    if not sub or sub.get("role") != "superadmin":
        await message.answer(t("superadmin_only", lang))
        await state.clear()
        return
    raw = message.text.strip()
    if raw in {"-", "skip", "пропуск", "нет"}:
        await state.update_data(mentor_id=None, permissions=[])
        await state.set_state(AddUser.waiting_for_permissions)
        await message.answer(t("add_user_permissions", lang), reply_markup=get_permissions_keyboard([], lang))
        return
    username = raw.lstrip("@").lower()
    if not re.match(r"^[a-z0-9_]{3,32}$", username):
        await message.answer(t("add_user_mentor_invalid", lang))
        return
    mentor = await client.get_subscriber_by_username(username)
    if not mentor:
        await message.answer(t("add_user_mentor_not_found", lang))
        return
    await state.update_data(mentor_id=mentor.get("id"), permissions=[])
    await state.set_state(AddUser.waiting_for_permissions)
    await message.answer(t("add_user_permissions", lang), reply_markup=get_permissions_keyboard([], lang))

@dp.callback_query(AddUser.waiting_for_permissions, F.data.startswith("invite_perm:"))
async def process_invite_permissions(callback_query: CallbackQuery, state: FSMContext):
    sub = await client.get_subscriber(callback_query.message.chat.id)
    lang = get_lang(sub)
    if not sub or sub.get("role") != "superadmin":
        await callback_query.answer(t("superadmin_only", lang), show_alert=True)
        await state.clear()
        return
    data = await state.get_data()
    selected = list(data.get("permissions", []))
    action = callback_query.data.split(":")[1]
    if action == "toggle":
        perm = callback_query.data.split(":")[2]
        if perm in selected:
            selected.remove(perm)
        else:
            selected.append(perm)
        await state.update_data(permissions=selected)
        await callback_query.message.edit_reply_markup(reply_markup=get_permissions_keyboard(selected, lang))
        await callback_query.answer()
        return
    if action == "cancel":
        await state.clear()
        await callback_query.message.answer(t("add_user_cancelled", lang))
        await callback_query.answer()
        return
    if action == "save":
        data = await state.get_data()
        created = await client.create_invite(
            username=data.get("username"),
            password=data.get("password"),
            name=data.get("name"),
            mentor_id=data.get("mentor_id"),
            permissions=data.get("permissions", []),
        )
        await state.clear()
        if created:
            await callback_query.message.answer(
                t("add_user_done", lang, username=data.get("username"), password=data.get("password")),
                parse_mode="Markdown"
            )
        else:
            await callback_query.message.answer(t("add_user_error", lang))
        await callback_query.answer()


@dp.message(F.text.in_(["📊 Stats", "📊 Статистика"]))
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "stats:view"):
        await message.answer(t("no_permission", lang))
        return

    await message.answer(
        t("stats_title", lang),
        reply_markup=get_stats_panel(lang),
        parse_mode="Markdown"
    )

@dp.callback_query(F.data.startswith("stats:"))
async def process_stats_callback(callback_query: CallbackQuery):
    sub = await client.get_subscriber(callback_query.message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "stats:view"):
        await callback_query.answer(t("no_permission", lang), show_alert=True)
        return

    action = callback_query.data.split(":")[1]

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
            await smart_edit(callback_query.message, text=text, reply_markup=get_stats_panel(lang))
        else:
            await callback_query.answer("Error fetching stats")

    elif action in ["dau", "mau"]:
        is_mau = action == "mau"
        days = 30 if is_mau else 7
        trends = await client.get_trends(days=days)
        
        if not trends or not trends.get("dau_trend"):
            await callback_query.answer("No trend data available", show_alert=True)
            return

        labels = trends.get("dates", [])
        data = trends.get("dau_trend", [])
        
        chart_config = {
            "type": "line",
            "data": {
                "labels": labels,
                "datasets": [{
                    "label": "DAU" if not is_mau else "MAU (30d)",
                    "data": data,
                    "borderColor": "rgba(75, 192, 192, 1)",
                    "backgroundColor": "rgba(75, 192, 192, 0.2)",
                    "fill": True,
                    "tension": 0.4
                }]
            },
            "options": {
                "title": {"display": True, "text": f"{'30-Day' if is_mau else '7-Day'} Activity"},
                "legend": {"display": False}
            }
        }
        chart_url = f"https://quickchart.io/chart?c={json.dumps(chart_config)}&width=600&height=400&bkg=white"
        
        caption = t("stats_mau_title" if is_mau else "stats_dau_title", lang)
        await smart_edit(callback_query.message, text=caption, photo_url=chart_url, reply_markup=get_stats_panel(lang))
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
            await smart_edit(callback_query.message, text=text, reply_markup=get_stats_panel(lang))
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

    monitoring = await client.get_monitoring()
    stats = await client.get_internal_stats()
    workers = await client.get_active_workers()

    if monitoring is None:
        await message.answer("❌ Error fetching monitoring data")
        return

    # Aggregate stats from monitoring
    active_count = sum(1 for m in monitoring if m.get("status") != "broken")
    broken_count = sum(1 for m in monitoring if m.get("status") == "broken")
    
    text = (
        f"{t('scraping_title', lang)}\n\n"
        f"✅ *{t('scraping_active', lang)}:* {active_count}\n"
        f"📦 *{t('scraping_items', lang)}:* {stats.get('scraped_24h', 0)}\n\n"
    )
    
    # 1. Workers Section
    if workers:
        text += f"{t('scraping_workers_title', lang, count=len(workers))}\n"
        for w in workers:
            hostname = w.get("hostname", "unknown")
            ram = w.get("ram_usage_pct", 0)
            tasks = w.get("concurrent_tasks", 0)
            status_emoji = "🟢" if ram < 80 else "🟡" if ram < 90 else "🔴"
            text += f"{status_emoji} <code>{hostname}</code>: Load {tasks} | RAM {ram}%\n"
        text += "\n"
    
    # To get source IDs for buttons, we still need a list of sources, 
    # but we only filter for the main representatives (hubs).
    sources = await client.get_sources()
    site_hubs = {s['site_key']: s['id'] for s in sources if s.get('type') == 'hub'}
    # fallback to first source for site if no hub
    for s in sources:
        if s['site_key'] not in site_hubs:
            site_hubs[s['site_key']] = s['id']

    buttons = []
    # Sort monitoring by site_key
    monitoring = sorted(monitoring, key=lambda x: x.get("site_key"))
    
    current_row = []
    for m in monitoring:
        key = m.get("site_key")
        status = m.get("status", "waiting")
        s_id = site_hubs.get(key)
        
        icon = "🟢"
        if status == "running": icon = "🔄"
        if status == "queued": icon = "⏳"
        if status == "error": icon = "🟡"
        if status == "broken": icon = "🔴"
             
        current_row.append(InlineKeyboardButton(text=f"{icon} {key}", callback_data=f"spider:view:{s_id}"))
        if len(current_row) == 2:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)
        
    # Navigation row
    buttons.append([InlineKeyboardButton(text="🧩 Map Categories", callback_data="spider:unmapped:0")])
        
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode="HTML")

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
        for s in sources:
            is_active = s.get("is_active")
            status = s.get("status", "waiting")
            status_icon = "🟢" if is_active else "🔴"
            if status == "running": status_icon = "🔄"
            elif status == "broken" or s.get("config", {}).get("fix_required"): status_icon = "🛠"
            
            buttons.append([InlineKeyboardButton(text=f"{status_icon} {s['site_key']}", callback_data=f"spider:view:{s['id']}")])
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
        sub = await client.get_subscriber(callback_query.message.chat.id)
        await callback_query.answer(t("lang_switched", lang))
        await callback_query.message.answer(
            t("lang_switched", lang),
            reply_markup=get_main_keyboard(lang, sub)
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
                        
                        if topic == "private":
                            target_chat_id = data.get("data", {}).get("target_chat_id")
                            if target_chat_id:
                                try:
                                    await bot.send_message(target_chat_id, text, parse_mode="Markdown")
                                except Exception as e:
                                    logger.error(f"Failed to send private message to {target_chat_id}: {e}")
                            else:
                                logger.error("Private notification missing target_chat_id")
                            continue

                        # Noise reduction for scraper errors
                        # If it's a 'scrapers' notification, we only alert if it explicitly mentions a broken state
                        # or if we want to implement more complex logic here.
                        # For now, let's just make sure we don't spam for every minor error if it's not 'broken'.
                        if topic == "scrapers" and "Broken:" not in text and "Need to Fix" not in text:
                            logger.info(f"Skipping noisy scraper notification: {text[:50]}...")
                            continue

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
    # Set commands
    try:
        commands = [
            types.BotCommand(command="start", description="Start bot"),
            types.BotCommand(command="help", description="Help"),
            types.BotCommand(command="weeek_connect", description="Connect Weeek Account"),
            types.BotCommand(command="tasks", description="Manage Tasks"),
            types.BotCommand(command="stats", description="Bot Statistics"),
        ]
        await bot.set_my_commands(commands)
        logger.info("Bot commands set successfully.")
    except Exception as e:
        logger.error(f"Failed to set bot commands: {e}")
    
    # Run both bot polling and RabbitMQ consumer concurrently
    await asyncio.gather(
        dp.start_polling(bot),
        consume_notifications()
    )

# --- Weeek Handlers ---

@dp.message(F.text.in_([STRINGS["ru"]["weeek_connect_btn"], STRINGS["en"]["weeek_connect_btn"]]))
@dp.message(Command("weeek_connect"))
async def cmd_weeek_connect(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    await message.answer(t("weeek_connect_intro", lang), parse_mode="Markdown", reply_markup=types.ReplyKeyboardRemove())
    await state.set_state(ConnectWeeek.waiting_for_token)

@dp.message(ConnectWeeek.waiting_for_token)
async def process_weeek_token(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    token = message.text.strip()
    
    if token.lower() in ["cancel", "/cancel"]:
        await message.answer(t("cancel", lang), reply_markup=get_main_keyboard(lang, sub))
        await state.clear()
        return

    # Call internal API
    resp = await client.connect_weeek(message.chat.id, token)
    
    if resp and resp.get("status") == "ok":
        # Grant tasks:manage permission
        perms = sub.get("permissions", [])
        if "tasks:manage" not in perms:
            perms.append("tasks:manage")
            await client.set_permissions(message.chat.id, perms)
            # Refresh sub to get updated perms for keyboard
            sub = await client.get_subscriber(message.chat.id)

        await message.answer(
            t("weeek_connect_success", lang, user_id=resp.get("weeek_user_id")),
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(lang, sub)
        )
        await message.answer(t("onboarding_tasks", lang), parse_mode="Markdown")
        await state.clear()
    else:
        detail = resp.get("detail") if isinstance(resp, dict) else None
        if detail:
            await message.answer(detail, reply_markup=get_main_keyboard(lang, sub))
        else:
            await message.answer(t("weeek_connect_error", lang), reply_markup=get_main_keyboard(lang, sub))
        await state.clear()

@dp.message(F.text.in_([STRINGS["ru"]["btn_tasks"], STRINGS["en"]["btn_tasks"]]))
@dp.message(Command("tasks"))
async def cmd_tasks(message: Message):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "tasks:manage"):
         await message.answer(t("no_permission", lang))
         return

    # Fetch tasks to show dashboard stats
    # We fetch 'all' and calculate locally to save API calls, or just fetch needed counts?
    # get_tasks returns list.
    tasks_resp = await client.get_tasks(message.chat.id, type="all")
    tasks = tasks_resp.get("tasks", []) if tasks_resp else []
    
    my_count = len(tasks) # Assumes backend filtered for us? "type=all" implementation in routes/weeek.py did filtering.
    # routes/weeek.py: type="all" filters by userId. So 'tasks' are MY tasks.
    
    # Count overdue
    today_iso = __import__("datetime").date.today().isoformat()
    overdue_count = sum(1 for t in tasks if t.get("date") and t.get("date") < today_iso and not t.get("isCompleted"))
    active_count = sum(1 for t in tasks if not t.get("isCompleted"))
    
    text = t("tasks_dashboard", lang, active_count=active_count, my_count=my_count, overdue_count=overdue_count)
    
    kb = get_tasks_keyboard(lang)
    await message.answer(text, parse_mode="Markdown", reply_markup=kb)

def get_tasks_keyboard(lang: str):
    inline_kb = [
        [
            InlineKeyboardButton(text=t("tasks_btn_my", lang), callback_data="tasks:list:my"),
            InlineKeyboardButton(text=t("tasks_btn_all", lang), callback_data="tasks:list:all")
        ],
        [
            InlineKeyboardButton(text=t("tasks_btn_create", lang), callback_data="tasks:create"),
            InlineKeyboardButton(text=t("tasks_btn_onboarding", lang), callback_data="tasks:onboarding")
        ],
        [InlineKeyboardButton(text=t("btn_reminders", lang), callback_data="tasks:reminders:info")],
        [InlineKeyboardButton(text="⬅️ Back", callback_data="tasks:menu:back")] # Uses nice-to-have back logic
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

@dp.callback_query(F.data.startswith("tasks:"))
async def process_tasks_callback(callback_query: CallbackQuery, state: FSMContext):
    sub = await client.get_subscriber(callback_query.message.chat.id)
    lang = get_lang(sub)
    
    if not has_permission(sub, "tasks:manage"):
        await callback_query.answer(t("no_permission", lang), show_alert=True)
        return

    data = callback_query.data
    action_parts = data.split(":")
    action = action_parts[1]
    
    if action == "menu":
        if action_parts[2] == "back":
            # Just show dashboard again
            # We can re-use logic from cmd_tasks but via editing
            tasks_resp = await client.get_tasks(callback_query.message.chat.id, type="all")
            tasks = tasks_resp.get("tasks", []) if tasks_resp else []
            
            my_count = len(tasks)
            today_iso = __import__("datetime").date.today().isoformat()
            overdue_count = sum(1 for t in tasks if t.get("date") and t.get("date") < today_iso and not t.get("isCompleted"))
            active_count = sum(1 for t in tasks if not t.get("isCompleted"))
            
            text = t("tasks_dashboard", lang, active_count=active_count, my_count=my_count, overdue_count=overdue_count)
            await smart_edit(callback_query.message, text=text, reply_markup=get_tasks_keyboard(lang))
            await callback_query.answer()
            
    elif action == "list":
        list_type = action_parts[2] # my, all
        await _show_task_list(callback_query, list_type, lang)
        
    elif action == "details":
        task_id = int(action_parts[2])
        await _show_task_details(callback_query, task_id, lang)
        
    elif action == "create":
        await callback_query.message.answer(t("tasks_create_prompt", lang))
        await state.set_state(NewTask.waiting_for_title)
        await callback_query.answer()
        
    elif action == "onboarding":
        rows = [[InlineKeyboardButton(text="⬅️ Back", callback_data="tasks:menu:back")]]
        await smart_edit(
            callback_query.message,
            text=t("onboarding_tasks", lang),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
        )
        await callback_query.answer()
    elif action == "reschedule":
        task_id = int(action_parts[2])
        await callback_query.message.answer(t("reschedule_prompt", lang))
        await state.update_data(task_id=task_id)
        await state.set_state(RescheduleTask.waiting_for_date)
        await callback_query.answer()
        
    elif action == "complete":
        task_id = int(action_parts[2])
        resp = await client.complete_task(callback_query.message.chat.id, task_id)
        if resp:
            await callback_query.answer(t("complete_success", lang), show_alert=True)
            # Refresh details? Or go back?
            # Let's go back to details to show updated state (or we removed it?)
            # Usually we want to go back to list or stay.
            # Let's re-render details (it will show as completed or we can direct to list)
            # Efficient: just update local message text?
            # Better: call _show_task_details again
            await _show_task_details(callback_query, task_id, lang)
        else:
            await callback_query.answer("❌ Failed to complete task", show_alert=True)

    elif action == "reminders":
        if action_parts[2] == "info":
             text = t("reminders_info", lang)
             rows = [[InlineKeyboardButton(text="⬅️ Back", callback_data="tasks:menu:back")]]
             await smart_edit(callback_query.message, text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

async def _show_task_list(callback_query: CallbackQuery, list_type: str, lang: str):
    # type="all" for my tasks, type="workspace" for all tasks (based on my previous logic update)
    api_type = "workspace" if list_type == "all" else "all" 
    
    tasks_resp = await client.get_tasks(callback_query.message.chat.id, type=api_type)
    tasks = tasks_resp.get("tasks", []) if tasks_resp else []
    
    # Simple pagination? Or just list first 10-20?
    # Let's show up to 10 for MVP.
    tasks = tasks[:10]
    
    if not tasks:
        await smart_edit(callback_query.message, text=t("tasks_empty", lang), reply_markup=get_tasks_keyboard(lang))
        return

    text = t("task_list_title" if list_type == "my" else "task_list_workspace_title", lang) + "\n\n"
    
    rows = []
    for task in tasks:
        status_emoji = "✅" if task.get("isCompleted") else "🔘"
        # Truncate title
        title = task.get("title", "No Title")
        if len(title) > 30: title = title[:27] + "..."
        
        rows.append([InlineKeyboardButton(text=f"{status_emoji} {title}", callback_data=f"tasks:details:{task['id']}")])
        
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="tasks:menu:back")])
    await smart_edit(callback_query.message, text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

async def _show_task_details(callback_query: CallbackQuery, task_id: int, lang: str):
    # We need to fetch single task details?
    # client.get_tasks returns list. Filtering by ID is inefficient but okay for MVP if we fetch all.
    # PROPER WAY: Add get_task(id) endpoint to routes/weeek.py.
    # For now, let's fetch 'all' and find.
    # Note: If it's a huge workspace task list, this is bad.
    # But we don't have get_task endpoint.
    # Let's rely on finding it in "workspace" list?
    # Or just add get_task endpoint?
    # I should add get_task endpoint.
    # Let's try to assume we can find it in 'workspace' list for now to save time, or just fetch 'all'.
    
    tasks_resp = await client.get_tasks(callback_query.message.chat.id, type="workspace") # Get everything
    tasks = tasks_resp.get("tasks", []) if tasks_resp else []
    task = next((t for t in tasks if str(t["id"]) == str(task_id)), None)
    
    if not task:
        await callback_query.answer("Task not found", show_alert=True)
        return
        
    assignees = ", ".join([str(u) for u in task.get("userIds", [])]) or "None"
    
    text = t("task_details", lang, 
        title=task.get("title"), 
        description=task.get("description") or "No description", 
        date=task.get("date") or "No date",
        assignees=assignees
    )
    
    rows = [
        [InlineKeyboardButton(text=t("btn_complete", lang), callback_data=f"tasks:complete:{task_id}")],
        [InlineKeyboardButton(text=t("btn_reschedule", lang), callback_data=f"tasks:reschedule:{task_id}")],
        [InlineKeyboardButton(text=t("btn_back_list", lang), callback_data="tasks:menu:back")]
    ]
    await smart_edit(callback_query.message, text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))

# --- Task FSM Handlers ---

@dp.message(NewTask.waiting_for_title)
async def process_new_task_title(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    title = message.text.strip()
    
    if title.lower() in ["cancel", "/cancel"]:
        await message.answer(t("cancel", lang), reply_markup=get_main_keyboard(lang, sub))
        await state.clear()
        return

    # Call simple create (default project/board/inbox)
    resp = await client.create_task(message.chat.id, title)
    if resp and resp.get("success"):
        await message.answer(t("tasks_created", lang, title=title), reply_markup=get_main_keyboard(lang, sub))
    else:
        await message.answer("❌ Error creating task.", reply_markup=get_main_keyboard(lang, sub))
    await state.clear()

@dp.message(RescheduleTask.waiting_for_date)
async def process_reschedule_date(message: Message, state: FSMContext):
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)
    date_str = message.text.strip()
    
    if date_str.lower() in ["cancel", "/cancel"]:
        await message.answer(t("cancel", lang), reply_markup=get_main_keyboard(lang, sub))
        await state.clear()
        return

    # Simple validation
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        await message.answer(t("invalid_input", lang) + " (Format: YYYY-MM-DD)")
        return

    await state.update_data(new_date=date_str)
    await message.answer(t("reschedule_reason_prompt", lang))
    await state.set_state(RescheduleTask.waiting_for_reason)

@dp.callback_query(lambda c: c.data.startswith("spider:config:"))
async def handle_spider_config(callback_query: CallbackQuery):
    source_id = int(callback_query.data.split(":")[2])
    source = await client.get_source_details(source_id)
    sub = await client.get_subscriber(callback_query.from_user.id)
    lang = get_lang(sub)
    
    if not source:
        await callback_query.answer("❌ Source not found")
        return
        
    text = (
        f"⚙️ *Configure: {source['site_key']}*\n"
        f"URL: `{source['url']}`\n\n"
        f"Current Interval: `{source['refresh_interval_hours']}h`\n"
        f"Current Priority: `{source['priority']}`\n"
        f"Params Strip: `{source.get('config', {}).get('strip_params', [])}`"
    )
    
    btns = [
        [
            InlineKeyboardButton(text="⏰ Interval", callback_data=f"spider:edit:{source_id}:interval"),
            InlineKeyboardButton(text="🔝 Priority", callback_data=f"spider:edit:{source_id}:priority")
        ],
        [InlineKeyboardButton(text="🔙 Back", callback_data=f"spider:view:{source_id}")]
    ]
    await smart_edit(callback_query.message, text=text, reply_markup=InlineKeyboardMarkup(inline_keyboard=btns))

@dp.callback_query(lambda c: c.data.startswith("spider:edit:"))
async def handle_spider_edit(callback_query: CallbackQuery, state: FSMContext):
    data = callback_query.data.split(":")
    source_id = int(data[2])
    field = data[3]
    
    await state.update_data(source_id=source_id, field=field)
    await state.set_state(SpiderConfigEdit.waiting_for_value)
    
    await callback_query.message.answer(f"Enter new value for *{field}* (current source ID: {source_id}):")
    await callback_query.answer()

class SpiderConfigEdit(StatesGroup):
    waiting_for_value = State()

@dp.message(SpiderConfigEdit.waiting_for_value)
async def process_spider_config_value(message: Message, state: FSMContext):
    data = await state.get_data()
    source_id = data.get("source_id")
    field = data.get("field")
    value = message.text.strip()
    
    sub = await client.get_subscriber(message.chat.id)
    lang = get_lang(sub)

    update_payload = {}
    if field == "interval":
        try:
            update_payload["refresh_interval_hours"] = int(value)
        except ValueError:
            await message.answer("❌ Please enter a valid number (hours).")
            return
    elif field == "priority":
        try:
            update_payload["priority"] = int(value)
        except ValueError:
            await message.answer("❌ Please enter a valid number (1-100).")
            return

    success = await client.update_source(source_id, update_payload)
    if success:
        await message.answer(f"✅ Successfully updated *{field}* to `{value}`.", 
                             reply_markup=get_main_keyboard(lang, sub))
    else:
        await message.answer("❌ Failed to update configuration.", 
                             reply_markup=get_main_keyboard(lang, sub))
    await state.clear()

if __name__ == "__main__":
    asyncio.run(main())
