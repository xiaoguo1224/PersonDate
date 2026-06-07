import { DashboardShell } from "@/components/dashboard-shell";
import ThemeProvider from "@/components/theme-provider";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ThemeProvider>
      <DashboardShell>{children}</DashboardShell>
    </ThemeProvider>
  );
}
