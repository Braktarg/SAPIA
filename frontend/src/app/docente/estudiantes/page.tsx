"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ProfileRadar } from "@/components/ProfileRadar";
import { StudentStatusDot } from "@/components/StudentStatusDot";
import { TeacherOnboarding } from "@/components/TeacherOnboarding";
import {
  AttentionLevel,
  CourseRow,
  getStudentProfile,
  getStudentSummary,
  getTeacherSetupStatus,
  listCourses,
  listStudents,
  PedagogicalProfile,
  StudentRow,
  StudentTeacherSummary,
  TeacherSetupStatus,
} from "@/lib/api";

export default function EstudiantesDocentePage() {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<number | null>(null);
  const [summary, setSummary] = useState<StudentTeacherSummary | null>(null);
  const [profile, setProfile] = useState<PedagogicalProfile | null>(null);
  const [setup, setSetup] = useState<TeacherSetupStatus | null>(null);
  const [hideOnboarding, setHideOnboarding] = useState(false);
  const [error, setError] = useState("");
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    const hidden = localStorage.getItem("sapia_hide_onboarding") === "1";
    setHideOnboarding(hidden);
    listCourses()
      .then((c) => {
        setCourses(c);
        if (c.length > 0) setCourseId(c[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (courseId == null) return;
    Promise.all([listStudents(courseId), getTeacherSetupStatus(courseId)])
      .then(([s, st]) => {
        setStudents(s);
        setSetup(st);
      })
      .catch((e) => setError(e.message));
  }, [courseId]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return students;
    return students.filter(
      (s) => s.full_name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q),
    );
  }, [students, search]);

  async function loadStudent(id: number) {
    setSelected(id);
    setError("");
    setSummary(null);
    setProfile(null);
    setLoadingDetail(true);
    try {
      const [sum, prof] = await Promise.all([
        getStudentSummary(id),
        getStudentProfile(id).catch(() => null),
      ]);
      setSummary(sum);
      setProfile(prof);
    } catch (e) {
      setError(e instanceof Error ? e.message : "No se pudo cargar");
    } finally {
      setLoadingDetail(false);
    }
  }

  function dismissOnboarding() {
    localStorage.setItem("sapia_hide_onboarding", "1");
    setHideOnboarding(true);
  }

  const courseName = courses.find((c) => c.id === courseId)?.name;
  const defaultTopic = "Ecuaciones lineales";

  return (
    <AppShell
      variant="teacher"
      title="Estudiantes PIE"
      subtitle={courseName ? `${courseName} — perfiles y seguimiento pedagógico` : "Fichas y perfiles"}
    >
      {!hideOnboarding && <TeacherOnboarding status={setup} onDismiss={dismissOnboarding} />}

      <div className="toolbar">
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
        <input
          className="input search-input"
          placeholder="Buscar estudiante…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="page-grid-2">
        <section className="card" data-tour="student-list">
          <h2 className="card-title">Listado ({filtered.length})</h2>
          {filtered.length === 0 ? (
            <p className="empty-state">No hay estudiantes en este curso.</p>
          ) : (
            <ul>
              {filtered.map((s) => (
                <li key={s.id}>
                  <button
                    type="button"
                    onClick={() => loadStudent(s.id)}
                    className={`list-item-btn ${selected === s.id ? "selected" : ""}`}
                  >
                    <span className="list-item-row">
                      <StudentStatusDot level={(s.attention_level ?? "monitor") as AttentionLevel} />
                      <span>{s.full_name}</span>
                    </span>
                    <span className="list-item-meta">
                      {s.age != null ? `${s.age} años` : "—"}
                      {" · "}
                      {s.has_profile ? "Perfil ✓" : "Sin test"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <h2 className="card-title">Ficha del estudiante</h2>
          {error && <div className="alert alert-error">{error}</div>}
          {loadingDetail && <p className="text-muted">Cargando…</p>}
          {!loadingDetail && !summary && !error && (
            <p className="empty-state">
              Selecciona un estudiante para ver su radar de perfil y generar recomendaciones personalizadas.
            </p>
          )}
          {summary && !loadingDetail && (
            <>
              <div className="student-header">
                <h3>{summary.full_name}</h3>
                <p className="text-muted">
                  {summary.email}
                  {summary.age != null ? ` · ${summary.age} años` : ""}
                </p>
                {summary.course_names.length > 0 && (
                  <p className="text-muted">Curso(s): {summary.course_names.join(", ")}</p>
                )}
                <div className="student-stats">
                  <span className="student-stat">{summary.recommendation_counts.pending} pendientes</span>
                  <span className="student-stat">{summary.recommendation_counts.published} publicadas</span>
                  <span className="student-stat">{summary.recommendation_counts.rejected} rechazadas</span>
                </div>
              </div>

              {profile && (
                <div className="profile-radar-section">
                  <h4>Perfil pedagógico (Random Forest)</h4>
                  <p className="text-muted profile-meta">
                    Modelo <code>{profile.model_version}</code> · versión perfil v{profile.version}
                  </p>
                  <ProfileRadar descriptors={profile.descriptors} />
                </div>
              )}

              {summary.diagnostic_telemetry && (
                <div className="diagnostic-telemetry">
                  <h4>Telemetría del test diagnóstico</h4>
                  <ul className="telemetry-list">
                    <li>Ítems respondidos: {summary.diagnostic_telemetry.items_answered}</li>
                    <li>Omisiones: {summary.diagnostic_telemetry.items_skipped}</li>
                    {summary.diagnostic_telemetry.avg_response_ms != null && (
                      <li>Tiempo promedio por ítem: {Math.round(summary.diagnostic_telemetry.avg_response_ms / 1000)} s</li>
                    )}
                    {summary.diagnostic_telemetry.total_duration_ms != null && (
                      <li>Duración total registrada: {Math.round(summary.diagnostic_telemetry.total_duration_ms / 1000)} s</li>
                    )}
                  </ul>
                </div>
              )}

              {summary.model_version && !profile && (
                <p className="text-muted">Modelo RF: <code>{summary.model_version}</code></p>
              )}

              {summary.top_descriptors.length > 0 && !profile && (
                <>
                  <h4>Fortalezas del perfil</h4>
                  <div className="descriptor-chips">
                    {summary.top_descriptors.map((d) => (
                      <span key={d.key} className="descriptor-chip">
                        {d.label} {Math.round(d.value * 100)}%
                      </span>
                    ))}
                  </div>
                </>
              )}

              {summary.latest_recommendation && (
                <div className="callout" style={{ marginTop: "1rem" }}>
                  <h4>Última recomendación</h4>
                  <p>
                    <strong>{summary.latest_recommendation.title}</strong>
                    <br />
                    <span className="text-muted">
                      {summary.latest_recommendation.planning_topic} · {summary.latest_recommendation.status}
                    </span>
                  </p>
                  <Link
                    href={`/docente/recomendaciones?rec=${summary.latest_recommendation.id}`}
                    className="btn btn-secondary btn-sm"
                    style={{ display: "inline-flex", marginTop: "0.5rem" }}
                  >
                    Ver en recomendaciones
                  </Link>
                </div>
              )}

              {summary.has_profile && courseId != null && (
                <div className="btn-group" style={{ marginTop: "1rem" }}>
                  <Link
                    href={`/docente/recomendaciones?student=${summary.id}&topic=${encodeURIComponent(defaultTopic)}`}
                    className="btn btn-primary"
                  >
                    Generar recomendación IA
                  </Link>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </AppShell>
  );
}
