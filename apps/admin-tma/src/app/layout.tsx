import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { TMAProvider } from "@/components/TMAProvider";

const inter = Inter({ subsets: ["latin", "cyrillic"] });

export const metadata: Metadata = {
  title: "Gifty Admin TMA",
  description: "Telegram Mini App for Gifty Backend Administration",
};

import { QueryProvider } from "@/components/QueryProvider";

import { LanguageProvider } from "@/contexts/LanguageContext";
import Script from "next/script";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru" data-theme="dark" suppressHydrationWarning>
      <head>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
        <Script id="tma-bridge-fix" strategy="beforeInteractive">
          {`
            if (typeof window !== 'undefined') {
              // Fix for some WebView environments where TelegramGameProxy is partially injected
              if (window.TelegramGameProxy && !window.TelegramGameProxy.receiveEvent) {
                window.TelegramGameProxy.receiveEvent = function() {
                  console.warn('TelegramGameProxy.receiveEvent called but not implemented by platform');
                };
              }
            }
          `}
        </Script>
      </head>
      <body className={inter.className}>
        <QueryProvider>
          <TMAProvider>
            <LanguageProvider>
              <div className="min-h-screen bg-[var(--tg-theme-bg-color)]">
                {children}
              </div>
            </LanguageProvider>
          </TMAProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
