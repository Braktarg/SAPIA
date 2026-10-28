import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const PUBLIC = ["/login", "/register"];
const PUBLIC_ASSET = /\.(png|jpe?g|gif|svg|ico|webp|woff2?|txt|xml)$/i;

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_ASSET.test(pathname)) {
    return NextResponse.next();
  }
  if (PUBLIC.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }
  const token = request.cookies.get("sapia_token")?.value;
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  const role = request.cookies.get("sapia_role")?.value;
  if (pathname.startsWith("/docente") && role && !["teacher", "admin", "coordinator"].includes(role)) {
    return NextResponse.redirect(new URL("/estudiante", request.url));
  }
  if (pathname.startsWith("/estudiante") && role && role !== "student") {
    return NextResponse.redirect(new URL("/docente", request.url));
  }
  if (pathname.startsWith("/admin") && role && role !== "admin") {
    return NextResponse.redirect(new URL("/docente", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
