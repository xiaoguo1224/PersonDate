"use client";

import { AuthProvider } from "@/components/auth-provider";
import ThemeProvider from "@/components/theme-provider";

export default function Providers({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ThemeProvider>
      <AuthProvider>{children}</AuthProvider>
    </ThemeProvider>
  );
}
