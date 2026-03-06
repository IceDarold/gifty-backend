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

    "settings.topics.investors": "Инвесторы",
    "settings.topics.partners": "Партнеры",
    "settings.topics.newsletter": "Новости",
    "settings.topics.monitoring": "Мониторинг",
    "settings.topics.scraping": "Скрапинг",
    "settings.topics.global": "Общие",
  },
  en: {
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

    "settings.topics.investors": "Investors",
    "settings.topics.partners": "Partners",
    "settings.topics.newsletter": "Newsletter",
    "settings.topics.monitoring": "Monitoring",
    "settings.topics.scraping": "Scraping",
    "settings.topics.global": "Global",
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

