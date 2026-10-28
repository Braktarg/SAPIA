"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { fetchMe, orgLookup, register, roleHomePath } from "@/lib/api";

export default function RegisterPage() {
  const router = useRouter();
  const [orgCode, setOrgCode] = useState("");
  const [orgName, setOrgName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<"student" | "teacher">("student");
  const [birthYear, setBirthYear] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [lookupBusy, setLookupBusy] = useState(false);

  async function validateOrg() {
    if (orgCode.trim().length < 4) return;
    setLookupBusy(true);
    setError("");
    try {
      const org = await orgLookup(orgCode);
      setOrgName(org.name);
    } catch (e) {
      setOrgName("");
      setError(e instanceof Error ? e.message : "Código no válido");
    } finally {
      setLookupBusy(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const token = await register({
        email,
        password,
        full_name: fullName,
        org_code: orgCode,
        role,
        birth_year: birthYear ? Number(birthYear) : undefined,
      });
      const me = await fetchMe(token);
      document.cookie = `sapia_token=${token}; path=/; max-age=28800; SameSite=Lax`;
      document.cookie = `sapia_role=${me.role}; path=/; max-age=28800; SameSite=Lax`;
      router.push(roleHomePath(me.role));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-hero">
        <div className="login-hero-badge">Registro institucional</div>
        <img src="/sapia-icon.png?v=5" alt="" className="login-logo" />
        <h1 className="login-title">Crear cuenta SAPIA</h1>
        <p className="login-tagline">
          Solicite el código de registro a su establecimiento. Los datos se tratan conforme a la Ley 19.628.
        </p>
      </div>
      <div className="login-form-side">
        <form onSubmit={handleSubmit} className="login-card">
          <h2>Registro con código</h2>
          <p className="subtitle">RF-01/02 — auto-registro con código de organización</p>

          <label className="field">
            <span className="field-label">Código de institución</span>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input
                className="input"
                required
                value={orgCode}
                onChange={(e) => {
                  setOrgCode(e.target.value.toUpperCase());
                  setOrgName("");
                }}
                onBlur={validateOrg}
                placeholder="Ej. DEMO-SAPIA"
              />
              <button
                type="button"
                className="btn btn-secondary"
                disabled={lookupBusy || orgCode.trim().length < 4}
                onClick={validateOrg}
              >
                {lookupBusy ? "…" : "Validar"}
              </button>
            </div>
            {orgName && <p className="text-muted" style={{ marginTop: "0.35rem" }}>Institución: {orgName}</p>}
          </label>

          <label className="field">
            <span className="field-label">Rol</span>
            <select className="select" value={role} onChange={(e) => setRole(e.target.value as "student" | "teacher")}>
              <option value="student">Estudiante</option>
              <option value="teacher">Docente</option>
            </select>
          </label>

          <label className="field">
            <span className="field-label">Nombre completo</span>
            <input className="input" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </label>

          <label className="field">
            <span className="field-label">Correo</span>
            <input
              type="email"
              required
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="nombre@colegio.cl"
            />
          </label>

          {role === "student" && (
            <label className="field">
              <span className="field-label">Año de nacimiento (opcional)</span>
              <input
                type="number"
                className="input"
                min={1990}
                max={2020}
                value={birthYear}
                onChange={(e) => setBirthYear(e.target.value)}
              />
            </label>
          )}

          <label className="field">
            <span className="field-label">Contraseña (mín. 8 caracteres)</span>
            <input
              type="password"
              required
              minLength={8}
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>

          {error && <div className="alert alert-error">{error}</div>}

          <button type="submit" disabled={loading || !orgName} className="btn btn-primary btn-login">
            {loading ? "Creando cuenta…" : "Registrarse"}
          </button>

          <p className="text-muted" style={{ marginTop: "1rem", textAlign: "center" }}>
            ¿Ya tiene cuenta? <Link href="/login">Iniciar sesión</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
