import type { Metadata } from "next";
import { Manrope, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { TMAProvider } from "@/components/TMAProvider";

const manrope = Manrope({
  subsets: ["latin", "cyrillic"],
  variable: "--font-manrope",
});
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
});

export const metadata: Metadata = {
  title: "Gifty Admin TMA",
  description: "Telegram Mini App for Gifty Backend Administration",
};

import { QueryProvider } from "@/components/QueryProvider";

import { LanguageProvider } from "@/contexts/LanguageContext";
import { OpsRuntimeSettingsProvider } from "@/contexts/OpsRuntimeSettingsContext";
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
      <body className={`${manrope.variable} ${spaceGrotesk.variable}`}>
        <QueryProvider>
          <TMAProvider>
            <LanguageProvider>
              <OpsRuntimeSettingsProvider>
                <div className="min-h-screen bg-[var(--tg-theme-bg-color)]">
                  {children}
                </div>
              </OpsRuntimeSettingsProvider>
            </LanguageProvider>
          </TMAProvider>
        </QueryProvider>
      </body>
    </html>
  );
}
