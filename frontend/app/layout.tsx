import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./components/AuthContext";
import { AppWrapper } from "./components/AppWrapper";
import { NavigationChrome } from "./components/NavigationChrome";
import { ShellHeader } from "./components/ShellHeader";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const plusJakartaSans = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-plus-jakarta-sans", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: "SEÑORITA // OS",
  description: "Intelligent Personal AI Assistant",
  icons: {
    icon: [
      { url: "/favicon.ico", sizes: "32x32" },
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [
      { url: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
    shortcut: "/favicon.ico",
  },
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.variable} ${plusJakartaSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="h-screen bg-[#070b14] text-white flex overflow-hidden" suppressHydrationWarning>
        <AuthProvider>
          <AppWrapper>
            <NavigationChrome />

            <main className="flex-1 flex flex-col h-screen overflow-hidden bg-[#070b14] relative">
              <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.02)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.02)_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none" />

              <ShellHeader />

              <div className="flex-1 overflow-y-auto relative z-10">
                <div className="mx-auto max-w-6xl px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">
                  {children}
                </div>
              </div>
            </main>
          </AppWrapper>
        </AuthProvider>
      </body>
    </html>
  );
}
