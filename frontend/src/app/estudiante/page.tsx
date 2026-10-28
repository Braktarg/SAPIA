"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getDiagnosticStatus } from "@/lib/api";

export default function EstudiantePage() {
  const router = useRouter();

  useEffect(() => {
    getDiagnosticStatus()
      .then((status) => {
        if (!status.has_profile) router.replace("/estudiante/diagnostico");
        else router.replace("/estudiante/recomendaciones");
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  return <div className="loading-page">Redirigiendo…</div>;
}
