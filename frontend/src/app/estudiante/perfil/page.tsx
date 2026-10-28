"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { getDiagnosticStatus, getMyProfile, PedagogicalProfile } from "@/lib/api";

export default function PerfilEstudiantePage() {
  const router = useRouter();
  const [profile, setProfile] = useState<PedagogicalProfile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const status = await getDiagnosticStatus();
        if (!status.has_profile) {
          router.replace("/estudiante/diagnostico");
          return;
        }
        setProfile(await getMyProfile());
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  if (loading) {
    return (
      <AppShell variant="student" title="Mi perfil" subtitle="Cargando…">
        <div className="loading-page">Cargando…</div>
      </AppShell>
    );
  }

  return (
    <AppShell variant="student" title="Mi perfil pedagógico" subtitle="Resultados de tu test diagnóstico">
      <div className="card" style={{ maxWidth: 560 }}>
        {profile && (
          <>
            <p className="text-muted">
              Modelo <strong>{profile.model_version}</strong> — versión {profile.version}
            </p>
            <ul>
              {profile.descriptors.map((d) => (
                <li key={d.key} className="progress-row">
                  <div className="progress-header">
                    <span>{d.label}</span>
                    <span>{Math.round(d.value * 100)}%</span>
                  </div>
                  <div className="progress-track">
                    <div className="progress-fill" style={{ width: `${d.value * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
        <button type="button" className="btn btn-secondary" onClick={() => router.push("/estudiante/diagnostico")}>
          Repetir test diagnóstico
        </button>
      </div>
    </AppShell>
  );
}
