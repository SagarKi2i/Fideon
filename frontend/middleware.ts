import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/**
 * Your app uses React Router client-side.
 * On hard refresh, Next.js will try to serve the route directly and may return 404.
 * This middleware rewrites all non-API / non-static requests back to `/`
 * so React Router can take over.
 */
export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Let the homepage through unchanged.
  if (pathname === "/") {
    return NextResponse.next();
  }

  // Skip Next internals and API routes
  if (pathname.startsWith("/api") || pathname.startsWith("/_next")) {
    return NextResponse.next();
  }

  // Skip requests that look like files (e.g. /favicon.ico, /robots.txt, /something.css)
  if (pathname.includes(".")) {
    return NextResponse.next();
  }

  // Rewrite to the app root; React Router renders the correct UI route.
  return NextResponse.rewrite(new URL("/", req.url));
}

export const config = {
  // Apply to all routes except API/static/Next internals.
  matcher: ["/((?!api|_next|.*\\..*).*)"],
};

