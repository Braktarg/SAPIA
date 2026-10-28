"use client";

import { useEffect, useState } from "react";
import { AppShell, StatusBadge } from "@/components/AppShell";
import { SimpleBarChart } from "@/components/SimpleBarChart";
import {
  CourseAnalytics,
  CourseRow,
  CourseTimeline,
  downloadCourseCsv,
  downloadCourseXlsx,
  getAuditTimeline,
  getCourseAnalytics,
  listCourses,
  listStudents,
  StudentRow,
} from "@/lib/api";

function formatTs(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-CL");
}

export default function PanelDocentePage() {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [studentId, setStudentId] = useState<number | "">("");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [timeline, setTimeline] = useState<CourseTimeline | null>(null);
  const [analytics, setAnalytics] = useState<CourseAnalytics | null>(null);
  const [anonymize, setAnonymize] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listCourses()
      .then((rows) => {
        setCourses(rows);
        if (rows.length > 0) setCourseId(rows[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (courseId == null) return;
    listStudents(courseId).then(setStudents).catch(() => setStudents([]));
    setStudentId("");
  }, [courseId]);

  useEffect(() => {
    if (courseId == null) return;
    const params: { studentId?: number; fromDate?: string; toDate?: string } = {};
    if (studentId !== "") params.studentId = studentId;
    if (fromDate) params.fromDate = new Date(`${fromDate}T00:00:00`).toISOString();
    if (toDate) params.toDate = new Date(`${toDate}T23:59:59`).toISOString();
    getAuditTimeline(courseId, params).then(setTimeline).catch((e) => setError(e.message));
    getCourseAnalytics(courseId).then(setAnalytics).catch(() => setAnalytics(null));
  }, [courseId, studentId, fromDate, toDate]);

  async function onExportCsv() {
    if (courseId == null) return;
    setBusy(true);
    setError("");
    try {
      await downloadCourseCsv(courseId, anonymize);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar");
    } finally {
      setBusy(false);
    }
  }

  async function onExportXlsx() {
    if (courseId == null) return;
    setBusy(true);
    setError("");
    try {
      await downloadCourseXlsx(courseId, anonymize);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al exportar Excel");
    } finally {
      setBusy(false);
    }
  }

  const summary = timeline?.summary;

  return (
    <AppShell
      variant="teacher"
      title="Panel de seguimiento"
      subtitle="Indicadores del curso, trazabilidad MitL y exportación PIE"
    >
      <div className="toolbar toolbar-wrap">
        <label className="field">
          <span className="field-label">Curso</span>
          <select className="select" value={courseId ?? ""} onChange={(e) => setCourseId(Number(e.target.value))}>
            {courses.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Estudiante</span>
          <select className="select" value={studentId} onChange={(e) => setStudentId(e.target.value ? Number(e.target.value) : "")}>
            <option value="">Todos</option>
            {students.map((s) => (
              <option key={s.id} value={s.id}>{s.full_name}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field-label">Desde</span>
          <input type="date" className="input" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
        </label>
        <label className="field">
          <span className="field-label">Hasta</span>
          <input type="date" className="input" value={toDate} onChange={(e) => setToDate(e.target.value)} />
        </label>
        <label className="field" style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <input type="checkbox" checked={anonymize} onChange={(e) => setAnonymize(e.target.checked)} />
          <span className="field-label" style={{ marginBottom: 0 }}>Anonimizar exportación</span>
        </label>
        <button type="button" className="btn btn-primary" onClick={onExportCsv} disabled={busy || courseId == null}>
          {busy ? "Exportando…" : "Exportar CSV"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onExportXlsx} disabled={busy || courseId == null}>
          Exportar Excel
        </button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {summary && (
        <div className="kpi-grid">
          <div className="kpi-card"><div className="kpi-label">TAI (perfil)</div><div className="kpi-value">{summary.tai_pct}%</div></div>
          <div className="kpi-card"><div className="kpi-label">Estudiantes</div><div className="kpi-value">{summary.students_total}</div></div>
          <div className="kpi-card"><div className="kpi-label">Pendientes</div><div className="kpi-value">{summary.recommendations_pending}</div></div>
          <div className="kpi-card"><div className="kpi-label">Publicadas</div><div className="kpi-value">{summary.recommendations_published}</div></div>
        </div>
      )}

      {analytics && (
        <div className="page-grid-2">
          <SimpleBarChart
            title="Recomendaciones por estado"
            items={[
              { label: "Pendientes", value: analytics.status_breakdown.pending ?? 0, color: "#d97706" },
              { label: "Aceptadas", value: analytics.status_breakdown.accepted ?? 0, color: "#059669" },
              { label: "Editadas", value: analytics.status_breakdown.edited ?? 0, color: "#6366f1" },
              { label: "Rechazadas", value: analytics.status_breakdown.rejected ?? 0, color: "#dc2626" },
            ]}
          />
          <SimpleBarChart
            title="Promedio perfil pedagógico del curso"
            items={analytics.descriptor_averages.map((d) => ({
              label: d.label,
              value: Math.round(d.value * 100),
            }))}
            max={100}
          />
        </div>
      )}

      {analytics && analytics.difficulty_feedback_count > 0 && (
        <div className="kpi-grid" style={{ marginTop: "1rem" }}>
          <div className="kpi-card">
            <div className="kpi-label">Autoevaluaciones de dificultad</div>
            <div className="kpi-value">{analytics.difficulty_feedback_count}</div>
          </div>
          <div className="kpi-card">
            <div className="kpi-label">Dificultad percibida (promedio)</div>
            <div className="kpi-value">
              {analytics.difficulty_rating_avg != null ? `${analytics.difficulty_rating_avg}/5` : "—"}
            </div>
          </div>
        </div>
      )}

      <h2>Trazabilidad por recomendación</h2>
      {!timeline || timeline.chains.length === 0 ? (
        <p className="empty-state">No hay recomendaciones que coincidan con los filtros.</p>
      ) : (
        timeline.chains.map((chain) => (
          <article key={chain.recommendation_id} className="card" style={{ marginBottom: "1rem" }}>
            <h3>#{chain.recommendation_id} — {chain.student_name}: {chain.planning_topic}</h3>
            <p>Estado: <StatusBadge status={chain.status} /></p>
            <ol className="timeline-steps">
              {chain.steps.map((step) => (
                <li key={step.order} className="timeline-step">
                  <span className="timeline-num">{step.order}</span>
                  <div>
                    <strong>{step.label}</strong> ({step.stage}) — {formatTs(step.timestamp)}
                    <br /><small className="text-muted">{step.detail}</small>
                  </div>
                </li>
              ))}
            </ol>
          </article>
        ))
      )}

      <p className="institutional-footer">
        SAPIA — Proyecto de título INACAP · Datos simulados con fines académicos · Ley 19.628
      </p>
    </AppShell>
  );
}
