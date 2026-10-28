"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { PipelineBanner } from "@/components/PipelineBanner";
import { StudentStatusDot } from "@/components/StudentStatusDot";
import { TeacherOnboarding } from "@/components/TeacherOnboarding";
import {
  AttentionLevel,
  CourseRow,
  getTeacherSetupStatus,
  listCourses,
  listStudents,
  StudentRow,
  TeacherSetupStatus,
} from "@/lib/api";

export default function DocenteHomePage() {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [setup, setSetup] = useState<TeacherSetupStatus | null>(null);
  const [students, setStudents] = useState<StudentRow[]>([]);
  const [hideOnboarding, setHideOnboarding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setHideOnboarding(localStorage.getItem("sapia_hide_onboarding") === "1");
    listCourses()
      .then((c) => {
        setCourses(c);
        if (c.length > 0) setCourseId(c[0].id);
      })
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    if (courseId == null) return;
    Promise.all([getTeacherSetupStatus(courseId), listStudents(courseId)])
      .then(([st, rows]) => {
        setSetup(st);
        setStudents(rows);
      })
      .catch((e) => setError(e.message));
  }, [courseId]);

  const attentionStudents = students.filter((s) =>
    ["no_profile", "pending", "alert"].includes(s.attention_level ?? ""),
  );
  const antonia = students.find((s) => s.email.includes("antonia.vega"));

  const courseName = courses.find((c) => c.id === courseId)?.name;

  return (
    <AppShell
      variant="teacher"
      title="Centro de mando PIE"
      subtitle={
        courseName
          ? `${courseName} — planificación diferenciada con IA explicable`
          : "Panel docente SAPIA"
      }
    >
      <PipelineBanner />

      {!hideOnboarding && (
        <TeacherOnboarding
          status={setup}
          onDismiss={() => {
            localStorage.setItem("sapia_hide_onboarding", "1");
            setHideOnboarding(true);
          }}
        />
      )}

      <div className="toolbar">
        <label className="field">
          <span className="field-label">Curso activo</span>
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
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {antonia && (
        <div className="featured-case card">
          <div className="featured-case-badge">Caso demo — defensa tribunal</div>
          <h2>Antonia Vega</h2>
          <p className="text-muted">
            Estudiante 8° Básico · perfil neurodivergente simulado · unidad «Ecuaciones lineales»
          </p>
          <div className="btn-group">
            <Link
              href={`/docente/recomendaciones?student=${antonia.id}&topic=${encodeURIComponent("Ecuaciones lineales")}`}
              className="btn btn-primary"
            >
              Generar recomendación IA
            </Link>
            <Link href={`/docente/estudiantes`} className="btn btn-secondary">
              Ver ficha y radar
            </Link>
          </div>
        </div>
      )}

      {setup && (
        <>
          <div className="kpi-grid" data-tour="home-kpis">
            <div className="kpi-card kpi-card-accent">
              <div className="kpi-label">Estudiantes</div>
              <div className="kpi-value">{setup.students_total}</div>
            </div>
            <div className="kpi-card kpi-card-accent">
              <div className="kpi-label">Con perfil RF</div>
              <div className="kpi-value">{setup.students_with_profile}</div>
            </div>
            <div className="kpi-card kpi-card-warn">
              <div className="kpi-label">MitL pendientes</div>
              <div className="kpi-value">{setup.recommendations_pending}</div>
            </div>
            <div className="kpi-card kpi-card-success">
              <div className="kpi-label">Publicadas</div>
              <div className="kpi-value">{setup.recommendations_published}</div>
            </div>
          </div>

          <div className="quick-actions card">
            <h2 className="card-title">Acciones rápidas</h2>
            <div className="quick-actions-grid">
              <Link href="/docente/recomendaciones" className="quick-action-tile" data-tour="cta-mitl">
                <strong>Bandeja MitL</strong>
                <span>
                  {setup.recommendations_pending > 0
                    ? `${setup.recommendations_pending} propuesta(s) esperando su validación`
                    : "Generar o revisar recomendaciones con IA"}
                </span>
              </Link>
              <Link href="/docente/biblioteca" className="quick-action-tile">
                <strong>Biblioteca curricular</strong>
                <span>{setup.indexed_documents_count} documento(s) indexados para RAG</span>
              </Link>
              <Link href="/docente/estudiantes" className="quick-action-tile" data-tour="cta-students">
                <strong>Fichas estudiantes</strong>
                <span>{setup.students_needing_attention ?? 0} con seguimiento prioritario</span>
              </Link>
              <Link href="/docente/matricula" className="quick-action-tile">
                <strong>Matrícula</strong>
                <span>Inscribir alumnos en {courseName ?? "el curso"}</span>
              </Link>
              <Link href="/docente/panel" className="quick-action-tile">
                <strong>Panel PIE</strong>
                <span>Gráficos, trazabilidad y exportación para reuniones</span>
              </Link>
            </div>
          </div>

          {attentionStudents.length > 0 && (
            <div className="card">
              <h2 className="card-title">Seguimiento prioritario</h2>
              <ul className="attention-list">
                {attentionStudents.slice(0, 8).map((s) => (
                  <li key={s.id}>
                    <StudentStatusDot level={(s.attention_level ?? "monitor") as AttentionLevel} showLabel />
                    <span>{s.full_name}</span>
                    <Link href="/docente/estudiantes" className="btn btn-secondary btn-sm">
                      Ver ficha
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <p className="institutional-footer">
            SAPIA complementa plataformas de gestión PIE · No sustituye FUDEI · Ley 19.628
          </p>
        </>
      )}
    </AppShell>
  );
}
