import { Suspense } from "react";
import RecomendacionesClient from "./RecomendacionesClient";

export default function RecomendacionesPage() {
  return (
    <Suspense fallback={<div className="loading-page">Cargando…</div>}>
      <RecomendacionesClient />
    </Suspense>
  );
}
