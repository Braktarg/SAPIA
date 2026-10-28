"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AppShell } from "@/components/AppShell";
import { DifficultyFeedback } from "@/components/DifficultyFeedback";
import { EmptyState } from "@/components/EmptyState";
import { StudentBodyBlocks } from "@/components/StudentBodyBlocks";
import {
  StudentRecommendation,
  downloadStudentDocument,
  getDiagnosticStatus,
  getStudentRecommendation,
  getStudentRecommendations,
  openStudentDocument,
} from "@/lib/api";

function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString("es-CL");
}

export default function RecomendacionesEstudiantePage() {
  const router = useRouter();
  const [items, setItems] = useState<StudentRecommendation[]>([]);
  const [selected, setSelected] = useState<StudentRecommendation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busyDoc, setBusyDoc] = useState<number | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const status = await getDiagnosticStatus();
        if (!status.has_profile) {
          router.replace("/estudiante/diagnostico");
          return;
        }
        setItems(await getStudentRecommendations());
      } catch {
        router.replace("/login");
      } finally {
        setLoading(false);
      }
    })();
  }, [router]);

  async function openItem(id: number) {
    setError("");
    try {
      setSelected(await getStudentRecommendation(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo abrir");
    }
  }

  async function onOpenPdf(documentId: number) {
    setBusyDoc(documentId);
    setError("");
    try {
      await openStudentDocument(documentId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo abrir el PDF");
    } finally {
      setBusyDoc(null);
    }
  }

  async function onDownload(documentId: number, filename: string) {
    setBusyDoc(documentId);
    setError("");
    try {
      await downloadStudentDocument(documentId, filename);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo descargar");
    } finally {
      setBusyDoc(null);
    }
  }

  if (loading) {
    return (
      <AppShell variant="student" title="Mis recomendaciones" subtitle="Cargando…">
        <div className="loading-page">Cargando…</div>
      </AppShell>
    );
  }

  return (
    <AppShell
      variant="student"
      title="Mis recomendaciones"
      subtitle="Recursos aprobados por tu docente, adaptados a tu perfil de apoyo pedagógico"
    >
      <div className="page-grid-wide">
        <section>
          {error && <div className="alert alert-error">{error}</div>}
          <div className="card">
            {items.length === 0 ? (
              <EmptyState
                title="Aún no hay actividades"
                description="Cuando tu docente apruebe una recomendación personalizada para ti, aparecerá aquí con los materiales de apoyo."
              />
            ) : (
              <ul className="student-rec-list">
                {items.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => openItem(r.id)}
                      className={`student-rec-card ${selected?.id === r.id ? "selected" : ""}`}
                    >
                      <span className="student-rec-title">{r.title}</span>
                      <span className="student-rec-meta">
                        Aprobada por {r.teacher_name}
                        {r.published_at ? ` · ${formatDate(r.published_at)}` : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>

        <section className="card">
          <h2 className="card-title">Detalle</h2>
          {!selected ? (
            <EmptyState
              title="Tu actividad"
              description="Elige una recomendación de la lista para ver la guía y los materiales que tu docente aprobó para ti."
            />
          ) : (
            <>
              <p>
                <span className="badge badge-success">
                  {selected.status === "edited" ? "Editada y aprobada" : "Aprobada"}
                </span>{" "}
                por {selected.teacher_name}
              </p>
              <h3>{selected.title}</h3>
              <p className="text-muted">{selected.planning_topic}</p>
              <StudentBodyBlocks body={selected.body} />

              {selected.resources.length > 0 && (
                <div style={{ marginBottom: "1rem" }}>
                  <h4>Materiales de apoyo</h4>
                  {selected.resources.map((res) => (
                    <div key={res.document_id} className="resource-card">
                      <strong>{res.unit_name}</strong> — {res.filename}
                      <div className="btn-group" style={{ marginTop: "0.75rem" }}>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busyDoc === res.document_id}
                          onClick={() => onOpenPdf(res.document_id)}
                        >
                          Abrir PDF
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary"
                          disabled={busyDoc === res.document_id}
                          onClick={() => onDownload(res.document_id, res.filename)}
                        >
                          Descargar
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="callout">
                <h4>¿Por qué me asignaron esto?</h4>
                <div className="callout-body student-explanation">
                  {(selected.explanation_student || selected.explanation).split("\n").map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                </div>
              </div>

              <DifficultyFeedback
                recommendationId={selected.id}
                initialRating={selected.my_difficulty_rating}
                onSaved={(rating) =>
                  setSelected((prev) => (prev ? { ...prev, my_difficulty_rating: rating } : prev))
                }
              />
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
