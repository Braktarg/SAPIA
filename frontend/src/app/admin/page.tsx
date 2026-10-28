"use client";

import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { EnrollmentPanel } from "@/components/EnrollmentPanel";
import { AdminUser, createAdminUser, listAdminUsers, updateAdminUser } from "@/lib/api";

const ROLES = [
  { value: "teacher", label: "Docente" },
  { value: "student", label: "Estudiante" },
  { value: "coordinator", label: "Coordinador PIE" },
  { value: "admin", label: "Administrador" },
];

export default function AdminPage() {
  const [tab, setTab] = useState<"users" | "enrollment">("users");
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    email: "",
    password: "",
    full_name: "",
    role: "teacher",
  });

  function load() {
    listAdminUsers().then(setUsers).catch((e) => setError(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await createAdminUser(form);
      setForm({ email: "", password: "", full_name: "", role: "teacher" });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear");
    } finally {
      setBusy(false);
    }
  }

  async function toggleActive(user: AdminUser) {
    setError("");
    try {
      await updateAdminUser(user.id, { is_active: !user.is_active });
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar");
    }
  }

  return (
    <AppShell variant="admin" title="Administración institucional" subtitle="Usuarios (RF-03) y matrícula (RF-04)">
      <div className="tab-bar">
        <button
          type="button"
          className={`tab-btn ${tab === "users" ? "active" : ""}`}
          onClick={() => setTab("users")}
        >
          Usuarios
        </button>
        <button
          type="button"
          className={`tab-btn ${tab === "enrollment" ? "active" : ""}`}
          onClick={() => setTab("enrollment")}
        >
          Matrícula
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {tab === "users" && (
        <div className="page-grid-2">
          <section className="card">
            <h2 className="card-title">Crear usuario</h2>
            <form onSubmit={onCreate} className="form-stack">
              <label className="field">
                <span className="field-label">Nombre completo</span>
                <input
                  className="input"
                  required
                  value={form.full_name}
                  onChange={(e) => setForm({ ...form, full_name: e.target.value })}
                />
              </label>
              <label className="field">
                <span className="field-label">Correo</span>
                <input
                  className="input"
                  type="email"
                  required
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                />
              </label>
              <label className="field">
                <span className="field-label">Contraseña</span>
                <input
                  className="input"
                  type="password"
                  required
                  minLength={6}
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                />
              </label>
              <label className="field">
                <span className="field-label">Rol</span>
                <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                  {ROLES.map((r) => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>
              </label>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                {busy ? "Creando…" : "Crear usuario"}
              </button>
            </form>
          </section>

          <section className="card">
            <h2 className="card-title">Usuarios ({users.length})</h2>
            {users.length === 0 ? (
              <p className="empty-state">Sin usuarios.</p>
            ) : (
              <ul className="admin-user-list">
                {users.map((u) => (
                  <li key={u.id} className="admin-user-row">
                    <div>
                      <strong>{u.full_name}</strong>
                      <br />
                      <span className="text-muted">{u.email}</span>
                      <br />
                      <span className="descriptor-chip">{u.role}</span>
                      {!u.is_active && <span className="descriptor-chip" style={{ background: "#fee2e2" }}>Inactivo</span>}
                    </div>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => toggleActive(u)}
                    >
                      {u.is_active ? "Desactivar" : "Activar"}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {tab === "enrollment" && <EnrollmentPanel allowCreateStudent />}
    </AppShell>
  );
}
