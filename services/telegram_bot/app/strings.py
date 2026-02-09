STRINGS = {
    "ru": {
        "welcome_new": "✅ Регистрация прошла успешно! Добро пожаловать в админ-панель Gifty AI.",
        "welcome_back": "👋 С возвращением! Вы уже зарегистрированы как администратор.",
        "onboarding": (
            "🤖 *Чем я могу помочь?*\n\n"
            "• *Stats* — Аналитика пользователей (DAU/MAU/Конверсия)\n"
            "• *Health* — Техническое состояние серверов\n"
            "• *Scraping* — Мониторинг наполнения каталога\n"
            "• *Tasks* — Управление задачами Weeek\n"
            "• *Уведомления* — Настройте подписки на новые заявки\n\n"
            "Используйте кнопки меню ниже для навигации или команды `/help`."
        ),
        "provide_secret": "Пожалуйста, укажите секретный ключ: `/start <secret>`",
        "invalid_secret": "⛔ Неверный секретный ключ.",
        "stats_title": "📊 *Аналитический Дашборд*",
        "stats_summary": "Сводка за последние 24ч",
        "stats_btn_summary": "📈 Сводка (Last 24h)",
        "stats_btn_growth": "📈 MAU / DAU Trends",
        "stats_btn_technical": "⚙️ Тех. детали",
        "stats_mau_title": "📊 *MAU Growth Trend*",
        "stats_dau_title": "📊 *DAU Activity Trend*",
        "health_title": "🚀 *Техническое состояние системы*",
        "health_latency": "Задержка API",
        "health_errors": "Ошибки (5xx)",
        "health_memory": "Память Redis",
        "health_disk": "Диск",
        "scraping_title": "🕷 *Мониторинг парсинга*",
        "scraping_active": "Активных источников",
        "scraping_unmapped": "Неразобранных категорий",
        "scraping_items": "Спаршено за 24ч",
        "lang_btn": "🌐 Язык / Language",
        "lang_switched": "🇷🇺 Язык изменен на Русский",
        "help_title": "🤖 *Справка Gifty Admin*",
        "help_text": (
             "Этот бот — ваш личный ассистент по управлению Gifty.\n\n"
              "*Управление задачами (Weeek):*\n"
              "• `/weeek_connect` — Подключить аккаунт\n"
              "• `/tasks` — Управление задачами\n\n"
              "*Настройки подписок:*\n"
              "• `/subscribe investors` — Новые инвесторы\n"
              "• `/subscribe partners` — Партнеры\n"
              "• `/subscribe newsletter` — Рассылка\n"
              "• `/subscribe all` — Все уведомления\n\n"
              "Все отчеты доступны через кнопки главного меню."
         ),
        "btn_stats": "📊 Статистика",
        "btn_health": "🚀 Состояние",
        "btn_scraping": "🕷 Парсинг",
        "btn_subs": "🔔 Подписки",
        "btn_tasks": "📝 Задачи",
        "subs_title": "Управление подписками",
        "btn_help": "ℹ️ Помощь",
        "no_permission": "⛔ У вас нет прав на выполнение этого действия.",
        "edit_url": "🔗 Пожалуйста, отправьте новый URL для паука:",
        "edit_interval": "🕒 Пожалуйста, отправьте новый интервал обновления в часах (целое число):",
        "update_success": "✅ Данные успешно обновлены!",
        "btn_users": "👥 Пользователи",
        "users_title": "👥 Управление доступом",
        "user_details": "👤 Пользователь: {name}\nUsername: @{slug}\nРоль: {role}\nID: `{chat_id}`",
        "role_changed": "✅ Роль пользователя {name} изменена на {role}",
        "perms_updated": "✅ Права пользователя обновлены",
        "become_superadmin_success": "👑 Поздравляем! Вы стали Superadmin. Теперь вы можете управлять правами других пользователей.",
        "superadmin_only": "🔐 Эта функция доступна только Superadmin.",
        "btn_manage_perms": "🔐 Управление правами",
        "perms_list_title": "🔐 Права пользователя {name}",
        "perm_info_title": "Право: {perm}",
        "btn_grant": "✅ Предоставить",
        "btn_revoke": "❌ Отозвать",
        "perm_status_active": "✅ Активно",
        "perm_status_inactive": "🔘 Выключено",
        "perm_descs": {
            "all": "Полный доступ ко всем функциям системы без ограничений.",
            "stats:view": "Доступ к аналитике: DAU/MAU, конверсии и отчеты по использованию.",
            "system:health": "Доступ к техническим метрикам: нагрузка, память, ошибки API.",
            "parsing:manage": "Управление парсингом: запуск пауков, изменение URL, мониторинг категорий.",
            "parsing:manage": "Управление парсингом: запуск пауков, изменение URL, мониторинг категорий.",
            "notifications:manage": "Возможность настраивать глобальные уведомления и подписки.",
            "tasks:manage": "Доступ к управлению задачами Weeek: просмотр, создание и редактирование."
        },
        "tasks_title": "📝 *Задачи Weeek*",
        "tasks_dashboard": (
            "🚀 *Активные задачи:* {active_count}\n"
            "👤 *Мои задачи:* {my_count}\n"
            "📅 *Просрочено:* {overdue_count}"
        ),
        "tasks_btn_my": "👤 Мои задачи",
        "tasks_btn_all": "📋 Все задачи",
        "tasks_btn_create": "➕ Новая задача",
        "tasks_empty": "👋 Задач не найдено",
        "tasks_create_prompt": "📝 Введите название новой задачи:",
        "tasks_created": "✅ Задача *{title}* успешно создана!",
        "invalid_input": "❌ Некорректный ввод. Попробуйте еще раз.",
        "cancel": "⌨️ Операция отменена.",
        "weeek_connect_btn": "🔗 Подключить Weeek",
        "weeek_connect_intro": "🔗 *Подключение Weeek*\n\nПожалуйста, отправьте ваш API токен. Вы можете получить его в настройках профиля Weeek.",
        "weeek_connect_success": "✅ Weeek успешно подключен!\nUser ID: `{user_id}`",
        "weeek_connect_error": "❌ Ошибка подключения. Проверьте токен и попробуйте снова.",
        "task_list_title": "📝 *Ваши задачи*",
        "task_list_workspace_title": "🏢 *Задачи Workspace*",
        "task_item": "• {status} *{title}* — {date}",
        "task_details": "📝 *{title}*\n\n{description}\n\n📅 Deadline: {date}\n👤 Assignees: {assignees}",
        "btn_complete": "✅ Выполнить",
        "btn_reschedule": "📅 Перенести",
        "btn_back_list": "⬅️ К списку",
        "reschedule_prompt": "📅 Введите новую дату (YYYY-MM-DD):",
        "reschedule_reason_prompt": "📝 Укажите причину переноса:",
        "reschedule_success": "✅ Дедлайн изменен!",
        "complete_success": "✅ Задача выполнена!",
        "btn_reminders": "🔔 Напоминания",
        "reminders_info": "🔔 *Настройки напоминаний*\n\nВ данный момент включены следующие уведомления (время МСК):\n\n🌅 09:00 — Дайджест на сегодня\n⚠️ 10:00 — Просроченные задачи\n📅 18:00 — Дедлайны завтра",
    },
    "en": {
        "welcome_new": "✅ Registration successful! Welcome to the Gifty AI Admin Panel.",
        "welcome_back": "👋 Welcome back! You are already an admin.",
        "onboarding": (
            "🤖 *What can I do?*\n\n"
            "• 📊 *Stats* — User analytics (DAU/MAU/Conversion)\n"
            "• 🚀 *Health* — Technical system health\n"
            "• 🕷 *Scraping* — Catalog monitoring\n"
            "• 📝 *Tasks* — Weeek Task Management\n"
            "• 🔔 *Notifications* — Setup alerts for new leads\n\n"
            "Use the menu buttons below to navigate or `/help`."
        ),
        "provide_secret": "Please provide the admin secret: `/start <secret>`",
        "invalid_secret": "⛔ Invalid secret password.",
        "stats_title": "📊 *Analytics Dashboard*",
        "stats_summary": "Last 24h summary",
        "stats_btn_summary": "📈 Summary (Last 24h)",
        "stats_btn_growth": "📈 MAU / DAU Trends",
        "stats_btn_technical": "⚙️ Tech details",
        "stats_mau_title": "📊 *MAU Growth Trend*",
        "stats_dau_title": "📊 *DAU Activity Trend*",
        "health_title": "🚀 *System Technical Health*",
        "health_latency": "API Latency",
        "health_errors": "Error Rate (5xx)",
        "health_memory": "Redis Memory",
        "health_disk": "Disk",
        "scraping_title": "🕷 *Scraping Monitoring*",
        "scraping_active": "Active Sources",
        "scraping_unmapped": "Unmapped Categories",
        "scraping_items": "Items Scraped (24h)",
        "lang_btn": "🌐 Language / Язык",
        "lang_switched": "🇺🇸 Language switched to English",
        "help_title": "🤖 *Gifty Admin Help*",
        "help_text": (
             "This bot is your Gifty control panel assistant.\n\n"
              "*Task Management (Weeek):*\n"
              "• `/weeek_connect` — Connect Account\n"
              "• `/tasks` — Manage Tasks\n\n"
              "*Subscription Settings:*\n"
              "• `/subscribe investors` — New investors\n"
              "• `/subscribe partners` — Partners\n"
              "• `/subscribe newsletter` — Newsletter\n"
              "• `/subscribe all` — All notifications\n\n"
              "All reports are available via the main menu buttons."
         ),
        "btn_stats": "📊 Stats",
        "btn_health": "🚀 Health",
        "btn_scraping": "🕷 Scraping",
        "btn_scraping": "🕷 Scraping",
        "btn_subs": "🔔 Subscriptions",
        "btn_tasks": "📝 Tasks",
        "subs_title": "Subscription Management",
        "btn_help": "ℹ️ Help",
        "no_permission": "⛔ You do not have permission to perform this action.",
        "edit_url": "🔗 Please send the new URL for the spider:",
        "edit_interval": "🕒 Please send the new refresh interval in hours (integer):",
        "update_success": "✅ Successfully updated!",
        "btn_users": "👥 Users",
        "users_title": "👥 Access Management",
        "user_details": "👤 User: {name}\nUsername: @{slug}\nRole: {role}\nID: `{chat_id}`",
        "role_changed": "✅ Role of {name} changed to {role}",
        "perms_updated": "✅ User permissions updated",
        "become_superadmin_success": "👑 Congratulations! You are now a Superadmin. You can now manage other users' rights.",
        "superadmin_only": "🔐 This feature is only available for Superadmin.",
        "btn_manage_perms": "🔐 Manage Permissions",
        "perms_list_title": "🔐 Permissions for {name}",
        "perm_info_title": "Permission: {perm}",
        "btn_grant": "✅ Grant",
        "btn_revoke": "❌ Revoke",
        "perm_status_active": "✅ Active",
        "perm_status_inactive": "🔘 Inactive",
        "perm_descs": {
            "all": "Full access to all system features without restrictions.",
            "stats:view": "Access to analytics: DAU/MAU, conversions, and usage reports.",
            "system:health": "Access to technical metrics: load, memory, API errors.",
            "parsing:manage": "Scraping management: run spiders, change URLs, monitor categories.",
            "notifications:manage": "Ability to configure global notifications and subscriptions.",
            "tasks:manage": "Access to Weeek task management: view, create, and edit tasks."
        },
        "tasks_title": "📝 *Weeek Tasks*",
        "tasks_dashboard": (
            "🚀 *Active Tasks:* {active_count}\n"
            "👤 *My Tasks:* {my_count}\n"
            "📅 *Overdue:* {overdue_count}"
        ),
        "tasks_btn_my": "👤 My Tasks",
        "tasks_btn_all": "📋 All Tasks",
        "tasks_btn_create": "➕ New Task",
        "tasks_empty": "👋 No tasks found",
        "tasks_create_prompt": "📝 Enter title for the new task:",
        "tasks_created": "✅ Task *{title}* created successfully!",
        "invalid_input": "❌ Invalid input. Please try again.",
        "cancel": "⌨️ Operation cancelled.",
        "weeek_connect_btn": "🔗 Connect Weeek",
        "weeek_connect_intro": "🔗 *Connect Weeek*\n\nPlease send your API token. You can generate it in your Weeek profile settings.",
        "weeek_connect_success": "✅ Weeek connected successfully!\nUser ID: `{user_id}`",
        "weeek_connect_error": "❌ Connection failed. Please check your token and try again.",
        "task_list_title": "📝 *Your Tasks*",
        "task_list_workspace_title": "🏢 *Workspace Tasks*",
        "task_item": "• {status} *{title}* — {date}",
        "task_details": "📝 *{title}*\n\n{description}\n\n📅 Deadline: {date}\n👤 Assignees: {assignees}",
        "btn_complete": "✅ Complete",
        "btn_reschedule": "📅 Reschedule",
        "btn_back_list": "⬅️ Back to List",
        "reschedule_prompt": "📅 Enter new date (YYYY-MM-DD):",
        "reschedule_reason_prompt": "📝 Enter reason for rescheduling:",
        "reschedule_success": "✅ Deadline updated!",
        "complete_success": "✅ Task completed!",
        "btn_reminders": "🔔 Reminders",
        "reminders_info": "🔔 *Reminder Settings*\n\nThe following notifications are currently enabled (Moscow Time):\n\n🌅 09:00 — Daily Digest\n⚠️ 10:00 — Overdue Tasks\n📅 18:00 — Due Tomorrow",
    }
}
