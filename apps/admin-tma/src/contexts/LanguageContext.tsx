"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { en } from "@/locales/en";
import { ru } from "@/locales/ru";

type Locale = "en" | "ru";
type Dictionary = typeof en;

interface LanguageContextType {
    language: Locale;
    setLanguage: (lang: Locale) => void;
    t: (key: string, params?: Record<string, string | number>) => string;
}

const LanguageContext = createContext<LanguageContextType | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
    const [language, setLanguageState] = useState<Locale>("ru"); // Default to Russian as per user hint

    // Helper to load from local storage if available
    useEffect(() => {
        const saved = localStorage.getItem("app_lang") as Locale;
        if (saved && (saved === "en" || saved === "ru")) {
            setLanguageState(saved);
        }
    }, []);

    const setLanguage = (lang: Locale) => {
        setLanguageState(lang);
        localStorage.setItem("app_lang", lang);
    };

    const getDictionary = (): Dictionary => {
        return language === "ru" ? ru : en;
    };

    const t = (key: string, params?: Record<string, string | number>): string => {
        const keys = key.split(".");
        let value: any = getDictionary();

        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k as keyof typeof value];
            } else {
                return key; // Fallback to key if not found
            }
        }

        if (typeof value === "string" && params) {
            return value.replace(/{(\w+)}/g, (_, k) => String(params[k] || `{${k}}`));
        }

        return typeof value === "string" ? value : key;
    };

    return (
        <LanguageContext.Provider value={{ language, setLanguage, t }}>
            {children}
        </LanguageContext.Provider>
    );
}

export function useLanguage() {
    const context = useContext(LanguageContext);
    if (context === undefined) {
        throw new Error("useLanguage must be used within a LanguageProvider");
    }
    return context;
}
