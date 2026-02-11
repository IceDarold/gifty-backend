"use client";

import { createContext, useContext, useEffect, useState } from "react";
import { postEvent, initData, viewport, miniApp, themeParams } from "@telegram-apps/sdk";

interface TMAContextType {
    user: any;
    startParam: string | null;
    platform: string;
}

const TMAContext = createContext<TMAContextType | null>(null);

export function TMAProvider({ children }: { children: React.ReactNode }) {
    const [isReady, setIsReady] = useState(false);
    const [context, setContext] = useState<TMAContextType | null>(null);

    useEffect(() => {
        const init = async () => {
            try {
                // Initialize Mini App
                if (miniApp.mount.isAvailable()) {
                    miniApp.mount();
                }

                if (miniApp.ready.isAvailable()) {
                    miniApp.ready();
                }

                // Initialize Viewport
                if (viewport.mount.isAvailable()) {
                    await viewport.mount();
                    if (viewport.expand.isAvailable()) {
                        viewport.expand();
                    }
                }

                // Sync Theme
                if (themeParams.mount.isAvailable()) {
                    themeParams.mount();
                }

                // Get Init Data
                const data = initData.user();
                setContext({
                    user: data || null,
                    startParam: initData.startParam() || null,
                    platform: "unknown", // platform not directly on initData in this way
                });

                setIsReady(true);
            } catch (e) {
                console.error("TMA Initialization failed", e);
                setIsReady(true); // Fallback
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

    return <TMAContext.Provider value={context}>{children}</TMAContext.Provider>;
}

export const useTMA = () => {
    const context = useContext(TMAContext);
    return context;
};
