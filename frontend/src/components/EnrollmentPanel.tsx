"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  CourseRow,
  createAdminUser,
  enrollStudent,
  importCourseCsv,
  listCourses,
  listStudents,
  StudentRow,
  unenrollStudent,
} from "@/lib/api";

type Props = {
  /** Permite crear cuenta estudiante y matricular en un paso (admin). */
  allowCreateStudent?: boolean;
};

export function EnrollmentPanel({ allowCreateStudent = false }: Props) {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [enrolled, setEnrolled] = useState<StudentRow[]>([]);
  const [orgStudents, setOrgStudents] = useState<StudentRow[]>([]);
  const [pickId, setPickId] = useState<number | "">("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [createForm, setCreateForm] = useState({
    full_name: "",
    email: "",
    password: "",
  });
  const [importFile, setImportFile] = useState<File | null>(null);

  const load = useCallback(async (cid: number) => {
    const [inCourse, all] = await Promise.all([listStudents(cid), listStudents()]);
    setEnrolled(inCourse);
    setOrgStudents(all);
  }, []);

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
    setError("");
    setSuccess("");
    load(courseId).catch((e) => setError(e.message));
  }, [courseId, load]);

  const enrolledIds = useMemo(() => new Set(enrolled.map((s) => s.id)), [enrolled]);

  const available = useMemo(() => {
    const q = search.trim().toLowerCase();
    return orgStudents
      .filter((s) => !enrolledIds.has(s.id))
      .filter((s) => !q || s.full_name.toLowerCase().includes(q) || s.email.toLowerCase().includes(q));
  }, [orgStudents, enrolledIds, search]);

  async function onEnroll(studentId: number) {
    if (courseId == null) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await enrollStudent(courseId, studentId);
      setSuccess("Estudiante matriculado correctamente.");
      setPickId("");
      await load(courseId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al matricular");
    } finally {
      setBusy(false);
    }
  }

  async function onUnenroll(student: StudentRow) {
    if (courseId == null) return;
    if (!window.confirm(`¿Quitar a ${student.full_name} del curso?`)) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await unenrollStudent(courseId, student.id);
      setSuccess(`${student.full_name} fue desinscrito del curso.`);
      await load(courseId);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Error al desinscribir");
    } finally {
      setBusy(false);
    }
  }

  async function onCreateAndEnroll(e: React.FormEvent) {
    e.preventDefault();
    if (courseId == null) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const user = await createAdminUser({
        ...createForm,
        role: "student",
      });
      await enrollStudent(courseId, user.id);
      setCreateForm({ full_name: "", email: "", password: "" });
      setSuccess(`${user.full_name} creado y matriculado.`);
      await load(courseId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear estudiante");
    } finally {
      setBusy(false);
    }
  }

  async function onImportCsv(e: React.FormEvent) {
    e.preventDefault();
    if (courseId == null || !importFile) return;
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const result = await importCourseCsv(courseId, importFile);
      setImportFile(null);
      setSuccess(
        `Importación CSV: ${result.created} cuenta(s) creada(s), ${result.enrolled} matriculada(s), ${result.skipped} omitida(s).`,
      );
      await load(courseId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al importar CSV");
    } finally {
      setBusy(false);
    }
  }

  const courseName = courses.find((c) => c.id === courseId)?.name;

  return (
    <div className="enrollment-panel">
      <div className="toolbar toolbar-wrap">
        <label className="field">
          <span className="field-label">Curso / sección</span>
          <select
            className="select"
            value={courseId ?? ""}
            onChange={(e) => setCourseId(Number(e.target.value))}
          >
            {courses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.grade_level ? ` (${c.grade_level})` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-info">{success}</div>}

      <div className="page-grid-2">
        <section className="card">
          <h2 className="card-title">Matricular estudiante</h2>
          <p className="text-muted enrollment-hint">
            Asocie alumnos de la institución a <strong>{courseName ?? "el curso"}</strong> (RF-04).
          </p>
          <input
            className="input search-input"
            placeholder="Buscar por nombre o correo…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <label className="field">
            <span className="field-label">Estudiante sin matrícula en este curso</span>
            <select
              className="select"
              value={pickId}
              onChange={(e) => setPickId(e.target.value ? Number(e.target.value) : "")}
            >
              <option value="">Seleccione…</option>
              {available.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.full_name} — {s.email}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || pickId === "" || courseId == null}
            onClick={() => pickId !== "" && onEnroll(pickId)}
          >
            {busy ? "Procesando…" : "Matricular en curso"}
          </button>
          {available.length === 0 && (
            <p className="empty-state">No hay estudiantes disponibles para matricular.</p>
          )}
        </section>

        {allowCreateStudent && (
          <section className="card">
            <h2 className="card-title">Crear estudiante y matricular</h2>
            <form onSubmit={onCreateAndEnroll} className="form-stack">
              <label className="field">
                <span className="field-label">Nombre completo</span>
                <input
                  className="input"
                  required
                  value={createForm.full_name}
                  onChange={(e) => setCreateForm({ ...createForm, full_name: e.target.value })}
                />
              </label>
              <label className="field">
                <span className="field-label">Correo</span>
                <input
                  className="input"
                  type="email"
                  required
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                />
              </label>
              <label className="field">
                <span className="field-label">Contraseña inicial</span>
                <input
                  className="input"
                  type="password"
                  required
                  minLength={6}
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                />
              </label>
              <button type="submit" className="btn btn-secondary" disabled={busy || courseId == null}>
                Crear y matricular
              </button>
            </form>
          </section>
        )}
      </div>

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 className="card-title">Importar estudiantes (CSV)</h2>
        <p className="text-muted enrollment-hint">
          Columnas: <code>full_name,email,birth_year</code> (UTF-8). Contraseña inicial por defecto según política
          institucional.
        </p>
        <form onSubmit={onImportCsv} className="form-stack">
          <input
            type="file"
            accept=".csv,text/csv"
            className="input"
            onChange={(e) => setImportFile(e.target.files?.[0] ?? null)}
          />
          <button type="submit" className="btn btn-secondary" disabled={busy || !importFile || courseId == null}>
            {busy ? "Importando…" : "Importar y matricular"}
          </button>
        </form>
      </section>

      <section className="card" style={{ marginTop: "1rem" }}>
        <h2 className="card-title">Alumnos matriculados ({enrolled.length})</h2>
        {enrolled.length === 0 ? (
          <p className="empty-state">Este curso aún no tiene estudiantes inscritos.</p>
        ) : (
          <ul className="admin-user-list">
            {enrolled.map((s) => (
              <li key={s.id} className="admin-user-row">
                <div>
                  <strong>{s.full_name}</strong>
                  <br />
                  <span className="text-muted">{s.email}</span>
                  <br />
                  <span className="descriptor-chip">
                    {s.has_profile ? "Perfil ✓" : "Pendiente test"}
                  </span>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={busy}
                  onClick={() => onUnenroll(s)}
                >
                  Quitar del curso
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
