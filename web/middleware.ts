import { NextRequest, NextResponse } from "next/server";

const AUTH_COOKIE_KEY = "schedule-agent.refresh-token";

const PUBLIC_AUTH_PATHS = new Set(["/login", "/register"]);

function isDashboardPath(pathname: string) {
  return pathname === "/dashboard" || pathname.startsWith("/dashboard/");
}

function isPublicAuthPath(pathname: string) {
  return PUBLIC_AUTH_PATHS.has(pathname);
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const authToken = request.cookies.get(AUTH_COOKIE_KEY)?.value;
  const hasAuthSession = Boolean(authToken);

  if (isDashboardPath(pathname) && !hasAuthSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    return NextResponse.redirect(url);
  }

  if (isPublicAuthPath(pathname) && hasAuthSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/dashboard/today";
    url.search = "";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard", "/dashboard/:path*", "/login", "/register"],
};
