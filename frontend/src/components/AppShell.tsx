"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { DemoTour } from "@/components/DemoTour";
import { STUDENT_NAV_ICONS, TEACHER_NAV_ICONS, IconLogout } from "@/components/NavIcons";
import { fetchMe, getTeacherSetupStatus, logout as apiLogout, UserMe } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  exact?: boolean;
  tourId?: string;
  badgeKey?: "pending";
};

const TEACHER_NAV: NavItem[] = [
  { href: "/docente", label: "Inicio", exact: true },
  { href: "/docente/estudiantes", label: "Estudiantes", tourId: "nav-estudiantes" },
  { href: "/docente/matricula", label: "Matrícula", tourId: "nav-matricula" },
  { href: "/docente/biblioteca", label: "Biblioteca", tourId: "nav-biblioteca" },
  { href: "/docente/recomendaciones", label: "Recomendaciones", tourId: "nav-recomendaciones", badgeKey: "pending" },
  { href: "/docente/panel", label: "Seguimiento", tourId: "nav-panel" },
];

const STUDENT_NAV: NavItem[] = [
  { href: "/estudiante/recomendaciones", label: "Mis recomendaciones" },
  { href: "/estudiante/perfil", label: "Mi perfil" },
  { href: "/estudiante/diagnostico", label: "Test diagnóstico" },
];

type Props = {
  variant: "teacher" | "student" | "admin";
  title: string;
  subtitle?: string;
  children: React.ReactNode;
};

export function AppShell({ variant, title, subtitle, children }: Props) {
  const pathname = usePathname();
  const router = useRouter();
  const [logoOk, setLogoOk] = useState(true);
  const [pendingBadge, setPendingBadge] = useState(0);
  const [user, setUser] = useState<UserMe | null>(null);
  const nav = variant === "student" ? STUDENT_NAV : variant === "teacher" ? TEACHER_NAV : [];
  const navIcons = variant === "student" ? STUDENT_NAV_ICONS : TEACHER_NAV_ICONS;

  useEffect(() => {
    fetchMe().then(setUser).catch(() => setUser(null));
  }, []);

  useEffect(() => {
    if (variant !== "teacher") return;
    getTeacherSetupStatus()
      .then((s) => setPendingBadge(s.recommendations_pending))
      .catch(() => setPendingBadge(0));
  }, [variant, pathname]);

  const brandMark = logoOk ? (
    <img src="/sapia-icon.png?v=5" alt="" className="brand-logo" onError={() => setLogoOk(false)} />
  ) : (
    <div className="sidebar-logo">S</div>
  );

  async function logout() {
    await apiLogout();
    document.cookie = "sapia_token=; path=/; max-age=0";
    document.cookie = "sapia_role=; path=/; max-age=0";
    router.push("/login");
  }

  function isActive(item: NavItem) {
    if (item.exact) return pathname === item.href;
    return pathname === item.href || pathname.startsWith(`${item.href}/`);
  }

  const headerExtra =
    variant === "teacher" && pendingBadge > 0 ? (
      <Link href="/docente/recomendaciones" className="header-pill header-pill-warn">
        {pendingBadge} pendiente{pendingBadge > 1 ? "s" : ""} MitL
      </Link>
    ) : null;

  if (variant === "admin") {
    return (
      <div className="app-shell">
        <aside className="sidebar">
          <div className="sidebar-brand">
            {brandMark}
            <div>
              <div className="sidebar-title">SAPIA</div>
              <div className="sidebar-subtitle">Administración</div>
            </div>
          </div>
          <div className="sidebar-footer">
            <button type="button" className="nav-link" onClick={logout}>
              <IconLogout className="nav-svg" />
              Cerrar sesión
            </button>
          </div>
        </aside>
        <div className="main-content">
          <header className="page-header">
            <h1>{title}</h1>
            {subtitle && <p>{subtitle}</p>}
          </header>
          <div className="page-body">{children}</div>
        </div>
      </div>
    );
  }

  return (
    <div className={`app-shell ${variant === "student" ? "student-shell" : ""}`}>
      {variant === "teacher" && <DemoTour role="teacher" />}
      <aside className="sidebar">
        <div className="sidebar-brand">
          {brandMark}
          <div>
            <div className="sidebar-title">SAPIA</div>
            <div className="sidebar-subtitle">
              {variant === "student" ? "Espacio estudiante" : "Apoyo pedagógico PIE"}
            </div>
          </div>
        </div>
        <nav className="sidebar-nav">
          {nav.map((item, i) => {
            const Icon = navIcons[i];
            return (
              <Link
                key={item.href}
                href={item.href}
                data-tour={item.tourId}
                className={`nav-link ${isActive(item) ? "active" : ""}`}
              >
                {Icon && <Icon className="nav-svg" />}
                <span className="nav-label-text">{item.label}</span>
                {item.badgeKey === "pending" && pendingBadge > 0 && (
                  <span className="nav-badge">{pendingBadge}</span>
                )}
              </Link>
            );
          })}
        </nav>
        <div className="sidebar-footer">
          {user && (
            <div className="sidebar-user">
              <span className="sidebar-user-name">{user.full_name}</span>
              <span className="sidebar-user-role">{user.role}</span>
            </div>
          )}
          <button type="button" className="nav-link" onClick={logout}>
            <IconLogout className="nav-svg" />
            Cerrar sesión
          </button>
        </div>
      </aside>
      <div className="main-content">
        <header className="page-header">
          <div className="page-header-inner">
            <div>
              <h1>{title}</h1>
              {subtitle && <p>{subtitle}</p>}
            </div>
            {headerExtra}
          </div>
        </header>
        <div className="page-body">{children}</div>
      </div>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "badge-pending",
    accepted: "badge-success",
    edited: "badge-edited",
    rejected: "badge-rejected",
    indexed: "badge-success",
    processing: "badge-pending",
    failed: "badge-rejected",
  };
  const labels: Record<string, string> = {
    pending: "Pendiente",
    accepted: "Aceptada",
    edited: "Editada",
    rejected: "Rechazada",
    indexed: "Indexado",
    processing: "Procesando",
    failed: "Error",
  };
  return <span className={`badge ${map[status] ?? "badge-muted"}`}>{labels[status] ?? status}</span>;
}
