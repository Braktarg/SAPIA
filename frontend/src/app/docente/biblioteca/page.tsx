"use client";

import { FormEvent, useEffect, useState } from "react";
import { AppShell, StatusBadge } from "@/components/AppShell";
import { PdfViewerModal } from "@/components/PdfViewerModal";
import {
  CurricularDocument,
  CourseRow,
  deleteDocument,
  DocumentChunkPreview,
  getDocumentChunks,
  listCourseDocuments,
  listCourses,
  openTeacherDocument,
  uploadCourseDocument,
} from "@/lib/api";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export default function BibliotecaPage() {
  const [courses, setCourses] = useState<CourseRow[]>([]);
  const [courseId, setCourseId] = useState<number | null>(null);
  const [documents, setDocuments] = useState<CurricularDocument[]>([]);
  const [unitName, setUnitName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<{ url: string; title: string } | null>(null);
  const [chunksDoc, setChunksDoc] = useState<CurricularDocument | null>(null);
  const [chunks, setChunks] = useState<DocumentChunkPreview[]>([]);
  const [chunksTotal, setChunksTotal] = useState(0);

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
    listCourseDocuments(courseId)
      .then(setDocuments)
      .catch((e) => setError(e.message));
  }, [courseId]);

  async function refreshDocs(id: number) {
    setDocuments(await listCourseDocuments(id));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (courseId == null || !file) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await uploadCourseDocument(courseId, unitName, file);
      setMessage(
        `«${res.document.original_filename}» indexado en ${res.processing_ms} ms (${res.document.chunk_count} fragmentos).`,
      );
      setUnitName("");
      setFile(null);
      await refreshDocs(courseId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir");
    } finally {
      setBusy(false);
    }
  }

  async function onShowChunks(doc: CurricularDocument) {
    setError("");
    setChunksDoc(doc);
    try {
      const data = await getDocumentChunks(doc.id);
      setChunks(data.previews);
      setChunksTotal(data.total_chunks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudieron cargar fragmentos");
      setChunksDoc(null);
    }
  }

  async function onPreview(doc: CurricularDocument) {
    setError("");
    try {
      const url = await openTeacherDocument(doc.id);
      setPreview({ url, title: doc.original_filename });
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo abrir el PDF");
    }
  }

  function closePreview() {
    if (preview) URL.revokeObjectURL(preview.url);
    setPreview(null);
  }

  async function onDelete(docId: number) {
    if (courseId == null) return;
    setError("");
    try {
      await deleteDocument(docId);
      await refreshDocs(courseId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  return (
    <AppShell
      variant="teacher"
      title="Biblioteca curricular"
      subtitle="Material curricular indexado para RAG — la IA cita solo fragmentos de sus PDFs"
    >
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
                {c.name} {c.grade_level ? `(${c.grade_level})` : ""}
              </option>
            ))}
          </select>
        </label>
      </div>

      <form onSubmit={onSubmit} className="card" style={{ marginBottom: "1.5rem" }}>
        <h2 className="card-title">Nuevo documento</h2>
        <label className="field">
          <span className="field-label">Unidad curricular</span>
          <input
            required
            className="input"
            value={unitName}
            onChange={(e) => setUnitName(e.target.value)}
            placeholder="Ej. Fracciones y decimales"
          />
        </label>
        <label className="field">
          <span className="field-label">Archivo PDF</span>
          <input
            required
            type="file"
            accept="application/pdf,.pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <button type="submit" disabled={busy || !file} className="btn btn-primary">
          {busy ? "Procesando…" : "Subir e indexar"}
        </button>
      </form>

      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-error">{error}</div>}

      <div className="card">
        <h2 className="card-title">Documentos del curso</h2>
        {documents.length === 0 ? (
          <p className="empty-state">No hay documentos cargados.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Unidad</th>
                  <th>Archivo</th>
                  <th>Estado</th>
                  <th>Fragmentos</th>
                  <th>Tamaño</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {documents.map((d) => (
                  <tr key={d.id}>
                    <td>{d.unit_name}</td>
                    <td>{d.original_filename}</td>
                    <td><StatusBadge status={d.status} /></td>
                    <td>{d.chunk_count}</td>
                    <td>{formatBytes(d.file_size_bytes)}</td>
                    <td>
                      <div className="btn-group">
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => onShowChunks(d)}
                          disabled={d.status !== "indexed"}
                        >
                          Fragmentos RAG
                        </button>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => onPreview(d)}
                          disabled={d.status !== "indexed"}
                        >
                          Ver PDF
                        </button>
                        <button type="button" className="btn btn-danger btn-sm" onClick={() => onDelete(d.id)}>
                          Eliminar
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {chunksDoc && (
        <div className="card chunk-preview-panel">
          <h2 className="card-title">
            Vista previa RAG — {chunksDoc.unit_name}
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ float: "right" }}
              onClick={() => setChunksDoc(null)}
            >
              Cerrar
            </button>
          </h2>
          <p className="text-muted">
            Muestra de {chunks.length} de {chunksTotal} fragmentos vectorizados. La IA recupera estos textos al
            generar recomendaciones.
          </p>
          <ol className="chunk-preview-list">
            {chunks.map((c) => (
              <li key={c.id} className="chunk-preview-item">
                <span className="chunk-preview-meta">
                  Fragmento {c.chunk_index + 1}/{chunksTotal} · ~{c.token_count} tokens
                </span>
                <p>{c.snippet}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {preview && (
        <PdfViewerModal url={preview.url} title={preview.title} onClose={closePreview} />
      )}
    </AppShell>
  );
}
