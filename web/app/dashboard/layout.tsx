import BackgroundAnimation from "@/components/background-animation";
import { DashboardShell } from "@/components/dashboard-shell";

export default function DashboardLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <>
      <BackgroundAnimation />
      <DashboardShell>{children}</DashboardShell>
    </>
  );
}
