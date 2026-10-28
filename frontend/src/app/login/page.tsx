"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { DemoCredentials } from "@/components/DemoCredentials";
import { fetchMe, login, roleHomePath } from "@/lib/api";

const FEATURES = [
  "Perfil pedagógico con Random Forest",
  "RAG sobre su material curricular (PDF)",
  "Recomendaciones explicables (XAI)",
  "Validación docente obligatoria (MitL)",
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const token = await login(email, password);
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

  function fillDemo(demoEmail: string, demoPassword: string) {
    setEmail(demoEmail);
    setPassword(demoPassword);
    setError("");
  }

  return (
    <div className="login-page">
      <div className="login-hero">
        <div className="login-hero-badge">Proyecto de título · INACAP</div>
        <img src="/sapia-icon.png?v=5" alt="" className="login-logo" />
        <h1 className="login-title">SAPIA</h1>
        <p className="login-tagline">
          Sistema de Apoyo Pedagógico basado en IA para estudiantes neurodivergentes en aula PIE.
        </p>
        <ul className="login-features">
          {FEATURES.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
        <div className="login-quote">«La IA propone; el docente dispone.»</div>
      </div>
      <div className="login-form-side">
        <form onSubmit={handleSubmit} className="login-card">
          <h2>Iniciar sesión</h2>
          <p className="subtitle">Plataforma institucional — datos protegidos (Ley 19.628)</p>
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
          <label className="field">
            <span className="field-label">Contraseña</span>
            <input
              type="password"
              required
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" disabled={loading} className="btn btn-primary btn-login">
            {loading ? "Ingresando…" : "Ingresar a SAPIA"}
          </button>
          <p className="text-muted" style={{ marginTop: "1rem", textAlign: "center" }}>
            ¿Primera vez? <a href="/register">Registrarse con código institucional</a>
          </p>
        </form>
        <DemoCredentials onSelect={fillDemo} />
      </div>
    </div>
  );
}
