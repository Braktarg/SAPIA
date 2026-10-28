"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AppShell, StatusBadge } from "@/components/AppShell";
import { CitationCard } from "@/components/CitationCard";
import { EmptyState } from "@/components/EmptyState";
import { EvidenceChainPanel } from "@/components/EvidenceChainPanel";
import { GeneratingOverlay } from "@/components/GeneratingOverlay";
import { MitLCompare } from "@/components/MitLCompare";
import { StudentBodyBlocks } from "@/components/StudentBodyBlocks";
import {
  CourseRow,
  CONSENT_VERSION,
  RecommendationDetail,
  RecommendationSummary,
  StudentRow,
  downloadRecommendationPdf,
  generateRecommendation,
  generateCourseRecommendation,
  getRecommendation,
  listCourses,
  listInboxRecommendations,
  listStudents,
  validateRecommendation,
} from "@/lib/api";

type MitlMode = "none" | "reject" | "edit";
type HistoryTab = "pending" | "published" | "rejected" | "all";
type GenerationMode = "student" | "course";

const TABS: { id: HistoryTab; label: string }[] = [
  { id: "pending", label: "Pendientes" },
  { id: "published", label: "Publicadas" },
  { id: "rejected", label: "Rechazadas" },
  { id: "all", label: "Todas" },
];

export default function RecomendacionesClient() {
  const searchParams = useSearchParams();
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [studentId, setStudentId] = useState<number | null>(null);
  const [generationMode, setGenerationMode] = useState<GenerationMode>("student");
  const [includePerStudent, setIncludePerStudent] = useState(true);
  const [topic, setTopic] = useState("");
  const [tab, setTab] = useState<HistoryTab>("pending");
  const [history, setHistory] = useState<RecommendationSummary[]>([]);
  const [selected, setSelected] = useState<RecommendationDetail | null>(null);
  const [generating, setGenerating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [mitlMode, setMitlMode] = useState<MitlMode>("none");
  const [reason, setReason] = useState("");
  const [editedBody, setEditedBody] = useState("");
  const [aiConsent, setAiConsent] = useState(false);

  const studentName = students.find((s) => s.id === studentId)?.full_name;

  useEffect(() => {
    listCourses()
      .then((c) => {
        setCourses(c);
        if (c.length > 0) setCourseId(c[0].id);
        const topicUrl = searchParams.get("topic");
        if (topicUrl) setTopic(topicUrl);
      })
      .catch((e) => setError(e.message));
  }, [searchParams]);

  useEffect(() => {
    if (courseId == null) return;
    listStudents(courseId)
      .then((rows) => {
        const withProfile = rows.filter((x) => x.has_profile);
        setStudents(withProfile);
        const fromUrl = searchParams.get("student");
        if (fromUrl && withProfile.some((s) => s.id === Number(fromUrl))) {
          setStudentId(Number(fromUrl));
        } else if (withProfile.length > 0) {
          setStudentId(withProfile[0].id);
        } else {
          setStudentId(null);
        }
      })
      .catch((e) => setError(e.message));
  }, [courseId, searchParams]);

  useEffect(() => {
    const recId = searchParams.get("rec");
    if (recId) openRecommendation(Number(recId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    if (courseId == null) return;
    refreshHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [courseId, tab]);

  async function refreshHistory() {
    if (courseId == null) return;
    try {
      setHistory(await listInboxRecommendations(courseId, tab));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al cargar historial");
    }
  }

  async function onGenerate(e: FormEvent) {
    e.preventDefault();
    if (courseId == null || !topic.trim()) return;
    if (generationMode === "student" && studentId == null) return;
    if (!aiConsent) {
      setError("Debe aceptar el consentimiento de uso de IA antes de generar.");
      return;
    }
    setGenerating(true);
    setError("");
    setMessage("");
    try {
      if (generationMode === "course") {
        const batch = await generateCourseRecommendation({
          course_id: courseId,
          planning_topic: topic.trim(),
          include_per_student: includePerStudent,
          ai_consent_accepted: true,
          consent_version: CONSENT_VERSION,
        });
        const modeLabel = batch.course.degraded_mode ? "modo plantilla" : "GPT";
        const extra =
          batch.student_count > 0
            ? ` + ${batch.student_count} recomendación(es) individual(es) en bandeja.`
            : "";
        setMessage(
          `Planificación grupal #${batch.course.id} (${modeLabel})${extra}`,
        );
        setTopic("");
        setTab("pending");
        await refreshHistory();
        setSelected(batch.course);
      } else {
        const rec = await generateRecommendation({
          student_id: studentId!,
          course_id: courseId,
          planning_topic: topic.trim(),
          ai_consent_accepted: true,
          consent_version: CONSENT_VERSION,
        });
        setMessage(
          rec.degraded_mode
            ? `Recomendación #${rec.id} generada (modo plantilla).`
            : `Recomendación #${rec.id} generada con GPT.`,
        );
        setTopic("");
        setTab("pending");
        await refreshHistory();
        setSelected(rec);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al generar");
    } finally {
      setGenerating(false);
    }
  }

  async function openRecommendation(id: number) {
    setError("");
    setMitlMode("none");
    setReason("");
    setEditedBody("");
    try {
      const rec = await getRecommendation(id);
      setSelected(rec);
      if (rec.status !== "pending") setTab(rec.status === "rejected" ? "rejected" : "published");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo abrir");
    }
  }

  async function onAccept() {
    if (!selected || courseId == null) return;
    setBusy(true);
    setError("");
    try {
      const updated = await validateRecommendation(selected.id, { action: "accept" });
      setSelected(updated);
      setMessage(
        selected.scope === "course"
          ? "Planificación del curso aceptada y archivada."
          : "Recomendación aceptada y publicada al estudiante.",
      );
      await refreshHistory();
      setTab("published");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al aceptar");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirmMitl() {
    if (!selected || courseId == null) return;
    const wasEdit = mitlMode === "edit";
    setBusy(true);
    setError("");
    try {
      const updated = await validateRecommendation(selected.id, {
        action: wasEdit ? "edit" : "reject",
        reason: reason.trim(),
        edited_body: wasEdit ? editedBody.trim() : undefined,
      });
      setSelected(updated);
      setMitlMode("none");
      setReason("");
      setEditedBody("");
      setMessage(wasEdit ? "Recomendación editada y publicada." : "Recomendación rechazada.");
      await refreshHistory();
      setTab(wasEdit ? "published" : "rejected");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al validar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell
      variant="teacher"
      title="Recomendaciones (MitL)"
      subtitle="La IA propone; tú validas antes de publicar al estudiante"
    >
      <GeneratingOverlay
        active={generating}
        mode={generationMode}
        studentName={generationMode === "course" ? "todo el curso" : studentName}
        topic={topic}
        batchStudentCount={students.length}
        includePerStudent={generationMode === "course" && includePerStudent}
      />

      <div className="page-grid-wide">
        <section>
          <form onSubmit={onGenerate} className="card" style={{ marginBottom: "1.5rem" }}>
            <h2 className="card-title">Nueva planificación</h2>
            <div className="tab-bar" style={{ marginBottom: "1rem" }}>
              <button
                type="button"
                className={`tab-btn ${generationMode === "student" ? "active" : ""}`}
                onClick={() => setGenerationMode("student")}
              >
                Estudiante individual
              </button>
              <button
                type="button"
                className={`tab-btn ${generationMode === "course" ? "active" : ""}`}
                onClick={() => setGenerationMode("course")}
              >
                Curso completo
              </button>
            </div>
            <label className="field">
              <span className="field-label">Curso</span>
              <select
                className="select"
                value={courseId ?? ""}
                onChange={(e) => setCourseId(Number(e.target.value))}
              >
                {courses.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </label>
            {generationMode === "student" ? (
              <label className="field">
                <span className="field-label">Estudiante (con perfil en este curso)</span>
                <select
                  className="select"
                  value={studentId ?? ""}
                  onChange={(e) => setStudentId(Number(e.target.value))}
                >
                  {students.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.full_name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <>
                <p className="text-muted enrollment-hint">
                  Se considerarán <strong>{students.length}</strong> estudiante(s) matriculado(s) con
                  perfil pedagógico en el curso seleccionado.
                </p>
                <label className="field checkbox-field">
                  <input
                    type="checkbox"
                    checked={includePerStudent}
                    onChange={(e) => setIncludePerStudent(e.target.checked)}
                  />
                  <span>
                    Generar también una recomendación <strong>individual</strong> por cada estudiante
                    (aparecen en la bandeja MitL para validar y publicar).
                  </span>
                </label>
              </>
            )}
            <label className="field">
              <span className="field-label">Tema / unidad a planificar</span>
              <input
                required
                className="input"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Ej. Ecuaciones lineales"
              />
            </label>
            <label className="field checkbox-field">
              <input
                type="checkbox"
                checked={aiConsent}
                onChange={(e) => setAiConsent(e.target.checked)}
              />
              <span>
                Autorizo el procesamiento con IA (RAG + modelo generativo) sobre el perfil del estudiante y
                material curricular, conforme TyC versión {CONSENT_VERSION} (RNF-37).
              </span>
            </label>
            <button
              type="submit"
              disabled={
                generating ||
                busy ||
                !aiConsent ||
                (generationMode === "student" && students.length === 0) ||
                (generationMode === "course" && students.length === 0)
              }
              className="btn btn-primary"
            >
              {generating
                ? "Generando con IA…"
                : generationMode === "course"
                  ? "Generar planificación del curso"
                  : "Generar recomendación"}
            </button>
          </form>

          {message && <div className="alert alert-success">{message}</div>}
          {error && <div className="alert alert-error">{error}</div>}

          <div className="card">
            <h2 className="card-title">Historial</h2>
            <div className="tab-bar">
              {TABS.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`tab-btn ${tab === t.id ? "active" : ""}`}
                  onClick={() => setTab(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            {history.length === 0 ? (
              <EmptyState
                title="Sin recomendaciones"
                description="Genere una propuesta con IA o cambie de pestaña para ver el historial."
              />
            ) : (
              <ul>
                {history.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      onClick={() => openRecommendation(item.id)}
                      className={`list-item-btn ${selected?.id === item.id ? "selected" : ""}`}
                    >
                      <strong>{item.title}</strong>
                      <span className="list-item-meta">
                        {item.student_name} — {item.planning_topic}{" "}
                        <StatusBadge status={item.status} />
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
              title="Bandeja MitL"
              description="Seleccione una recomendación pendiente o genere una nueva para revisar la propuesta de la IA antes de publicarla al estudiante."
            />
          ) : (
            <>
              <div className="rec-detail-header">
                <div className="rec-detail-meta">
                  <StatusBadge status={selected.status} />
                  <span className="text-muted">{selected.student_name}</span>
                  {selected.scope === "course" && (
                    <span className="descriptor-chip">Planificación grupal</span>
                  )}
                  {!selected.degraded_mode && <span className="descriptor-chip">GPT activo</span>}
                </div>
                <h3>{selected.title}</h3>
                {selected.evidence_chain?.topic_alignment &&
                !selected.evidence_chain.topic_alignment.aligned ? (
                  <p className="text-muted rec-topic-alignment">
                    <span>
                      Tema solicitado:{" "}
                      <strong>{selected.evidence_chain.topic_alignment.planning_topic}</strong>
                    </span>
                    <span className="rec-topic-arrow"> → </span>
                    <span>
                      Anclado a:{" "}
                      <strong>{selected.evidence_chain.topic_alignment.canonical_topic}</strong>
                    </span>
                  </p>
                ) : (
                  <p className="text-muted">{selected.planning_topic}</p>
                )}
              </div>
              <StudentBodyBlocks body={selected.body} />
              <MitLCompare
                status={selected.status}
                currentBody={selected.body}
                mitl={selected.mitl ?? null}
              />
              {(selected.status === "accepted" || selected.status === "edited") && (
                <div className="btn-group" style={{ marginTop: "1rem" }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={async () => {
                      setBusy(true);
                      try {
                        await downloadRecommendationPdf(selected.id);
                      } catch (e) {
                        setError(e instanceof Error ? e.message : "Error al exportar");
                      } finally {
                        setBusy(false);
                      }
                    }}
                    disabled={busy}
                  >
                    Exportar PDF
                  </button>
                </div>
              )}
              <div className="callout">
                <h4>¿Por qué esta sugerencia?</h4>
                <div className="callout-body student-explanation">
                  {selected.explanation.split("\n").map((line, i) => (
                    <p key={i}>{line}</p>
                  ))}
                </div>
              </div>
              {selected.evidence_chain && (
                <EvidenceChainPanel
                  chain={selected.evidence_chain}
                  sourceChunks={selected.source_chunks}
                />
              )}
              {!selected.evidence_chain && selected.source_chunks.length > 0 && (
                <>
                  <h4>Fuentes curriculares (RAG)</h4>
                  <ul className="citation-list">
                    {selected.source_chunks.map((c) => (
                      <CitationCard
                        key={c.id}
                        unitName={c.unit_name}
                        snippet={c.snippet}
                        score={c.score}
                      />
                    ))}
                  </ul>
                </>
              )}
              {selected.degraded_mode && (
                <div className="alert alert-info">
                  Modo plantilla en esta recomendación. La propuesta es válida para MitL, pero esta
                  generación no usó GPT (API sin clave, error del modelo o respuesta no estructurada).
                  Genere una nueva planificación para intentar con GPT.
                </div>
              )}
              {selected.status === "pending" && (
                <div className="mitl-panel">
                  <h4>Validación docente — Human-in-the-Loop</h4>
                  <p className="text-muted" style={{ marginBottom: "1rem" }}>
                    {selected.scope === "course"
                      ? "Esta planificación grupal es para su uso docente; no se publica automáticamente a los estudiantes."
                      : "La recomendación no llegará al estudiante hasta que usted acepte, edite o rechace."}
                  </p>
                  {mitlMode === "none" && (
                    <div className="btn-group">
                      <button type="button" className="btn btn-success" onClick={onAccept} disabled={busy}>
                        Aceptar
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger"
                        onClick={() => setMitlMode("reject")}
                        disabled={busy}
                      >
                        Rechazar
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => {
                          setMitlMode("edit");
                          setEditedBody(selected.body);
                        }}
                        disabled={busy}
                      >
                        Editar
                      </button>
                    </div>
                  )}
                  {mitlMode === "reject" && (
                    <div>
                      <label className="field">
                        <span className="field-label">Motivo del rechazo (obligatorio)</span>
                        <textarea
                          required
                          className="textarea"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          rows={3}
                        />
                      </label>
                      <div className="btn-group">
                        <button type="button" className="btn btn-danger" onClick={onConfirmMitl} disabled={busy}>
                          Confirmar rechazo
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setMitlMode("none")}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                  {mitlMode === "edit" && (
                    <div>
                      <label className="field">
                        <span className="field-label">Contenido editado</span>
                        <textarea
                          required
                          className="textarea"
                          value={editedBody}
                          onChange={(e) => setEditedBody(e.target.value)}
                          rows={6}
                        />
                      </label>
                      <label className="field">
                        <span className="field-label">Motivo de la edición (obligatorio)</span>
                        <textarea
                          required
                          className="textarea"
                          value={reason}
                          onChange={(e) => setReason(e.target.value)}
                          rows={2}
                        />
                      </label>
                      <div className="btn-group">
                        <button type="button" className="btn btn-primary" onClick={onConfirmMitl} disabled={busy}>
                          Publicar edición
                        </button>
                        <button type="button" className="btn btn-secondary" onClick={() => setMitlMode("none")}>
                          Cancelar
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
