"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { initData, miniApp, themeParams, viewport } from "@telegram-apps/sdk";
import { ShieldAlert, Send } from "lucide-react";
import { authWithTelegram, getInitDataRaw } from "@/lib/api";

interface AuthUser {
    id: number;
    name?: string;
    role?: string;
    permissions?: string[];
}

interface TMAContextType {
    user: any;
    authUser: AuthUser | null;
    startParam: string | null;
    platform: string;
    initDataRaw: string;
}

const TMAContext = createContext<TMAContextType | null>(null);
const BOT_USERNAME = process.env.NEXT_PUBLIC_TELEGRAM_BOT_USERNAME || "GiftyAIBot";
const BOT_LINK = `https://t.me/${BOT_USERNAME}`;

export function TMAProvider({ children }: { children: React.ReactNode }) {
    const [isReady, setIsReady] = useState(false);
    const [isAuthorized, setIsAuthorized] = useState(false);
    const [context, setContext] = useState<TMAContextType | null>(null);

    useEffect(() => {
        const getUnsafeUser = () => (window as any)?.Telegram?.WebApp?.initDataUnsafe?.user || null;
        const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

        const init = async () => {
            try {
                if (miniApp.mount.isAvailable()) miniApp.mount();
                if (miniApp.ready.isAvailable()) miniApp.ready();

                if (viewport.mount.isAvailable()) {
                    await viewport.mount();
                    if (viewport.expand.isAvailable()) viewport.expand();
                }

                if (themeParams.mount.isAvailable()) themeParams.mount();

                let rawInitData = "";
                for (let i = 0; i < 20; i++) {
                    rawInitData = getInitDataRaw();
                    if (rawInitData) break;
                    await sleep(120);
                }

                const sdkUser = initData.user();
                const unsafeUser = getUnsafeUser();
                const tmaUser = sdkUser || unsafeUser;

                const auth = await authWithTelegram();
                const authUser = auth?.user || null;

                setContext({
                    user: tmaUser || authUser || null,
                    authUser,
                    startParam: initData.startParam() || null,
                    platform: "unknown",
                    initDataRaw: rawInitData,
                });

                setIsAuthorized(true);
            } catch (e) {
                console.error("TMA auth initialization failed", e);
                setIsAuthorized(false);
            } finally {
                setIsReady(true);
            }
        };

        init();
    }, []);

    if (!isReady) {
        return (
            <div className="flex items-center justify-center h-screen bg-[#17212b]">
                <div className="animate-pulse text-[#5288c1] font-bold text-xl flex flex-col items-center gap-4">
                    <div className="w-12 h-12 border-4 border-[#5288c1] border-t-transparent rounded-full animate-spin"></div>
                    <span>Gifty Admin Center</span>
                </div>
            </div>
        );
    }

    if (!isAuthorized) {
        return (
            <div className="min-h-screen bg-gradient-to-b from-[#17212b] via-[#111c28] to-[#0d141d] px-6 py-8 flex items-center justify-center">
                <div className="max-w-md w-full rounded-3xl border border-[#ec3942]/30 bg-[#0e1621]/95 p-7 text-center shadow-2xl">
                    <div className="mx-auto w-14 h-14 rounded-2xl bg-[#ec3942]/15 border border-[#ec3942]/35 flex items-center justify-center">
                        <ShieldAlert size={28} className="text-[#ec3942]" />
                    </div>

                    <h2 className="mt-4 text-xl font-extrabold text-white">Доступ запрещен</h2>
                    <p className="mt-2 text-sm text-[#9fb3c8]">
                        Требуется авторизация через Telegram WebApp и права администратора.
                    </p>

                    <div className="mt-4 rounded-xl border border-[#5288c1]/30 bg-[#5288c1]/10 p-3 text-left">
                        <p className="text-xs font-semibold text-[#9ec8f0]">Как войти:</p>
                        <p className="mt-1 text-xs text-[#c7d8ea]">
                            Открой бота в Telegram и запусти дашборд кнопкой меню.
                        </p>
                    </div>

                    <a
                        href={BOT_LINK}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-5 w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#2481cc] text-white px-4 py-3 font-bold shadow-lg shadow-[#2481cc]/30 hover:brightness-110 active:scale-[0.98] transition-all"
                    >
                        <Send size={16} />
                        Открыть в Telegram
                    </a>
                </div>
            </div>
        );
    }

    return <TMAContext.Provider value={context}>{children}</TMAContext.Provider>;
}

export const useTMA = () => useContext(TMAContext);
