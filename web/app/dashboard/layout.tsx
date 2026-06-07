import BackgroundAnimation from "@/components/background-animation";
import { DashboardShell } from "@/components/dashboard-shell";
import ThemeProvider from "@/components/theme-provider";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ThemeProvider>
      <BackgroundAnimation />
      <DashboardShell>{children}</DashboardShell>
    </ThemeProvider>
  );
}
