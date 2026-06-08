import type { Metadata } from "next";
import { Noto_Sans_SC, Noto_Serif_SC, Space_Grotesk } from "next/font/google";

import Providers from "./providers";
import "./globals.css";

const notoSansSC = Noto_Sans_SC({
  subsets: ["latin"],
  variable: "--font-noto-sans-sc",
  weight: ["400", "500", "700"],
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  weight: ["400", "500", "700"],
});

const notoSerifSC = Noto_Serif_SC({
  subsets: ["latin"],
  variable: "--font-noto-serif-sc",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  title: {
    default: "PersonDate · Your AI Time Copilot",
    template: "%s | PersonDate",
  },
  description: "面向 owner/member 的安排驾驶舱与 Agent 管理界面。",
  icons: {
    icon: "/small_logo.png",
    shortcut: "/small_logo.png",
    apple: "/small_logo.png",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body className={`${notoSansSC.variable} ${spaceGrotesk.variable} ${notoSerifSC.variable}`}>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
