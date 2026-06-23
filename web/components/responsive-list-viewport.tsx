"use client";

export function ResponsiveListViewport({
  desktop,
  mobile,
  tablet,
  mobileBreakpoint = 768,
  desktopBreakpoint = 1280,
}: Readonly<{
  desktop: React.ReactNode;
  mobile: React.ReactNode;
  tablet?: React.ReactNode;
  mobileBreakpoint?: number;
  desktopBreakpoint?: number;
}>) {
  const hasTablet = Boolean(tablet);

  return (
    <div
      className={[
        "responsive-list-viewport",
        hasTablet ? "responsive-list-viewport--with-tablet" : "responsive-list-viewport--no-tablet",
      ].join(" ")}
      data-mobile-breakpoint={mobileBreakpoint}
      data-desktop-breakpoint={desktopBreakpoint}
    >
      <div className="responsive-list-viewport__desktop">{desktop}</div>
      {tablet ? <div className="responsive-list-viewport__tablet">{tablet}</div> : null}
      <div className="responsive-list-viewport__mobile">{mobile}</div>
    </div>
  );
}
