"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

type Language = "ru" | "en";

type TFn = (key: string, params?: Record<string, string | number | boolean | null | undefined>) => string;

type LanguageContextType = {
  language: Language;
  setLanguage: (lang: Language) => void;
  t: TFn;
};

const LanguageContext = createContext<LanguageContextType | null>(null);

const STORAGE_KEY = "gifty_admin_lang";

const STRINGS: Record<Language, Record<string, string>> = {
  ru: {
    "common.no_data": "Нет данных",
    "common.superadmin_panel": "Superadmin Panel",
    "common.system_optimal": "Система работает оптимально",
    "common.system_high_load": "Повышенная нагрузка",
    "common.ai_recommendation": "Текущая задержка API: {latency}ms",

    "spiders.connected_spiders": "Подключенные пауки",
    "spiders.syncing": "Синхронизация…",
    "spiders.sync_now": "Синхронизировать",
    "spiders.items": "items",
    "spiders.synced": "Synced",
    "spiders.new": "New",
    "spiders.no_spiders": "Пауки не подключены.",
    "spiders.click_sync": "Нажмите синхронизацию, чтобы импортировать из кода.",

    "categories.title": "Категории",
    "categories.subtitle": "Мониторинг {count} источников",
    "categories.category": "Категория",
    "categories.products": "Товаров",
    "categories.status": "Статус",
    "categories.last_run": "Последний запуск",
    "categories.next_run": "Следующий запуск",
    "categories.actions": "Действия",
    "categories.view_chart": "График",
    "categories.view_details": "Подробнее",
    "categories.status_running": "Работает",
    "categories.status_waiting": "Ожидает",
    "categories.status_error": "Ошибка",
    "categories.status_broken": "Сломан",
    "categories.status_disabled": "Отключен",
    "categories.never": "Никогда",
    "categories.unknown": "Неизвестно",
    "categories.scheduled_now": "Запланирован сейчас",

    "settings.topics.investors": "Инвесторы",
    "settings.topics.partners": "Партнеры",
    "settings.topics.newsletter": "Новости",
    "settings.topics.monitoring": "Мониторинг",
    "settings.topics.scraping": "Скрапинг",
    "settings.topics.global": "Общие",

    "settings.internal_api": "Internal API",
    "settings.internal_token_desc": "Нужен для внутренних эндпоинтов (LLM Logs, Operations). Сохраняется в этом браузере.",
    "settings.internal_token_placeholder": "Вставьте x-internal-token",
    "settings.internal_token_save": "Сохранить",
    "settings.internal_token_clear": "Очистить",
    "settings.internal_token_saved": "Токен сохранён",
    "settings.internal_token_missing": "Токен не задан",
    "settings.internal_token_error": "Не удалось сохранить токен",
    "settings.internal_token_show": "Показать",
    "settings.internal_token_hide": "Скрыть",
  },
  en: {
    "common.no_data": "No data available",
    "common.superadmin_panel": "Superadmin Panel",
    "common.system_optimal": "System is optimal",
    "common.system_high_load": "High load",
    "common.ai_recommendation": "API latency: {latency}ms",

    "spiders.connected_spiders": "Connected spiders",
    "spiders.syncing": "Syncing…",
    "spiders.sync_now": "Sync now",
    "spiders.items": "items",
    "spiders.synced": "Synced",
    "spiders.new": "New",
    "spiders.no_spiders": "No spiders connected yet.",
    "spiders.click_sync": "Click sync to import from codebase.",

    "categories.title": "Categories",
    "categories.subtitle": "Monitoring {count} sources",
    "categories.category": "Category",
    "categories.products": "Products",
    "categories.status": "Status",
    "categories.last_run": "Last run",
    "categories.next_run": "Next run",
    "categories.actions": "Actions",
    "categories.view_chart": "Chart",
    "categories.view_details": "Details",
    "categories.status_running": "Running",
    "categories.status_waiting": "Waiting",
    "categories.status_error": "Error",
    "categories.status_broken": "Broken",
    "categories.status_disabled": "Disabled",
    "categories.never": "Never",
    "categories.unknown": "Unknown",
    "categories.scheduled_now": "Scheduled now",

    "settings.topics.investors": "Investors",
    "settings.topics.partners": "Partners",
    "settings.topics.newsletter": "Newsletter",
    "settings.topics.monitoring": "Monitoring",
    "settings.topics.scraping": "Scraping",
    "settings.topics.global": "Global",

    "settings.internal_api": "Internal API",
    "settings.internal_token_desc": "Required for internal endpoints (LLM Logs, Operations). Stored in this browser.",
    "settings.internal_token_placeholder": "Paste x-internal-token",
    "settings.internal_token_save": "Save",
    "settings.internal_token_clear": "Clear",
    "settings.internal_token_saved": "Token saved",
    "settings.internal_token_missing": "Token not set",
    "settings.internal_token_error": "Failed to save token",
    "settings.internal_token_show": "Show",
    "settings.internal_token_hide": "Hide",
  },
};

function interpolate(template: string, params?: Record<string, string | number | boolean | null | undefined>) {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key: string) => {
    const value = params[key];
    if (value === null || value === undefined) return "";
    return String(value);
  });
}

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const [language, setLanguageState] = useState<Language>("ru");

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "ru" || saved === "en") setLanguageState(saved);
    } catch {
      // ignore
    }
  }, []);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
    try {
      window.localStorage.setItem(STORAGE_KEY, lang);
    } catch {
      // ignore
    }
  }, []);

  const t: TFn = useCallback(
    (key, params) => {
      const value = STRINGS[language]?.[key] ?? STRINGS.ru[key] ?? key;
      return interpolate(value, params);
    },
    [language],
  );

  const value = useMemo(() => ({ language, setLanguage, t }), [language, setLanguage, t]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return ctx;
}
