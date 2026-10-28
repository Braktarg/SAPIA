const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Versión vigente de TyC / consentimiento (RNF-37). */
export const CONSENT_VERSION = "2026-06";

export type UserMe = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  org_id: number;
};

export type DiagnosticOption = { value: number; label: string };

export type DiagnosticItem = {
  id: number;
  sort_order: number;
  question_text: string;
  options: DiagnosticOption[];
};

export type ProfileDescriptor = { key: string; label: string; value: number };

export type PedagogicalProfile = {
  id: number;
  student_id: number;
  version: number;
  model_version: string;
  descriptors: ProfileDescriptor[];
  feature_importance: Record<string, number>;
  created_at: string;
};

export type CourseRow = {
  id: number;
  name: string;
  grade_level: string | null;
};

export type CurricularDocument = {
  id: number;
  course_id: number;
  unit_name: string;
  original_filename: string;
  status: string;
  page_count: number | null;
  file_size_bytes: number;
  chunk_count: number;
  error_message: string | null;
  created_at: string;
};

export async function listCourses(): Promise<CourseRow[]> {
  const res = await fetch(`${API_URL}/api/v1/courses`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudieron cargar cursos");
  return res.json();
}

export async function listCourseDocuments(courseId: number): Promise<CurricularDocument[]> {
  const res = await fetch(`${API_URL}/api/v1/courses/${courseId}/documents`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudieron cargar documentos");
  return res.json();
}

export async function uploadCourseDocument(
  courseId: number,
  unitName: string,
  file: File,
): Promise<{ document: CurricularDocument; processing_ms: number }> {
  const form = new FormData();
  form.append("unit_name", unitName);
  form.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}/api/v1/courses/${courseId}/documents`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al subir PDF");
  }
  return res.json();
}

export async function deleteDocument(documentId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/documents/${documentId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("No se pudo eliminar el documento");
}

export type DocumentChunkPreview = {
  id: number;
  chunk_index: number;
  snippet: string;
  token_count: number;
};

export async function getDocumentChunks(documentId: number): Promise<{
  total_chunks: number;
  previews: DocumentChunkPreview[];
}> {
  const res = await fetch(`${API_URL}/api/v1/documents/${documentId}/chunks`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("No se pudieron cargar fragmentos");
  return res.json();
}

export type RecommendationSummary = {
  id: number;
  student_id: number | null;
  student_name: string;
  course_id: number;
  scope: "student" | "course";
  status: string;
  planning_topic: string;
  title: string;
  created_at: string;
};

export type SourceChunkRef = {
  id: number;
  unit_name: string;
  snippet: string;
  score: number;
};

export type EvidenceChain = {
  steps: {
    order: number;
    stage: string;
    label: string;
    detail: string;
    chunk_id?: number | null;
  }[];
  evidence_rows: {
    evidence: string;
    decision: string;
    descriptor_key?: string | null;
    chunk_id?: number | null;
    rationale?: string | null;
  }[];
  curricular_anchor?: {
    oa: string;
    unit_name: string;
    concepts: string[];
    main_activity: string;
    chunk_id?: number | null;
  };
  tier_assignment?: { A: string[]; B: string[]; C: string[] };
  descriptor_scores?: {
    key: string;
    label: string;
    value: number;
    tier: string;
  }[];
  topic_alignment?: {
    planning_topic: string;
    canonical_topic: string;
    aligned: boolean;
    note: string;
  };
  profile_synthesis?: {
    strengths: { key: string; label: string; value: number }[];
    supports: { key: string; label: string; value: number }[];
  };
  citations?: string[];
};

export type RecommendationDetail = RecommendationSummary & {
  teacher_id: number;
  body: string;
  explanation: string;
  source_chunks: SourceChunkRef[];
  profile_version: number;
  degraded_mode: boolean;
  evidence_chain?: EvidenceChain | null;
  course_context?: {
    scope?: string;
    course_name?: string;
    student_count?: number;
    students?: { student_id: number; student_name: string; profile_version: number }[];
  } | null;
  mitl?: {
    action: string;
    reason: string | null;
    original_body: string | null;
    validated_at: string | null;
  } | null;
};

export async function generateRecommendation(body: {
  student_id: number;
  course_id: number;
  planning_topic: string;
  ai_consent_accepted: boolean;
  consent_version: string;
}): Promise<RecommendationDetail> {
  const res = await fetch(`${API_URL}/api/v1/recommendations/generate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al generar recomendación");
  }
  return res.json();
}

export type CourseBatchGenerateResponse = {
  course: RecommendationDetail;
  students: RecommendationSummary[];
  student_count: number;
};

export async function generateCourseRecommendation(body: {
  course_id: number;
  planning_topic: string;
  include_per_student?: boolean;
  ai_consent_accepted: boolean;
  consent_version: string;
}): Promise<CourseBatchGenerateResponse> {
  const res = await fetch(`${API_URL}/api/v1/recommendations/generate-course`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al generar planificación del curso");
  }
  return res.json();
}

export async function listInboxRecommendations(
  courseId?: number,
  status: "pending" | "published" | "accepted" | "edited" | "rejected" | "all" = "pending",
): Promise<RecommendationSummary[]> {
  const params = new URLSearchParams();
  if (courseId != null) params.set("course_id", String(courseId));
  if (status !== "pending") params.set("status", status);
  const q = params.toString() ? `?${params}` : "";
  const res = await fetch(`${API_URL}/api/v1/recommendations/inbox${q}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudo cargar la bandeja");
  return res.json();
}

export async function getRecommendation(id: number): Promise<RecommendationDetail> {
  const res = await fetch(`${API_URL}/api/v1/recommendations/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Recomendación no encontrada");
  return res.json();
}

export async function validateRecommendation(
  id: number,
  body: { action: "accept" | "reject" | "edit"; reason?: string; edited_body?: string },
): Promise<RecommendationDetail> {
  const res = await fetch(`${API_URL}/api/v1/recommendations/${id}/validate`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al validar");
  }
  return res.json();
}

export type StudentResource = {
  document_id: number;
  unit_name: string;
  filename: string;
};

export type StudentRecommendation = {
  id: number;
  title: string;
  body: string;
  planning_topic: string;
  status: string;
  explanation: string;
  explanation_student: string;
  teacher_name: string;
  published_at: string | null;
  resources: StudentResource[];
  created_at: string;
  my_difficulty_rating: number | null;
};

function authHeadersNoContentType(): HeadersInit {
  const token = getToken();
  const h: Record<string, string> = {};
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function getStudentRecommendations(): Promise<StudentRecommendation[]> {
  const res = await fetch(`${API_URL}/api/v1/student/recommendations`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudieron cargar recomendaciones");
  return res.json();
}

export async function getStudentRecommendation(id: number): Promise<StudentRecommendation> {
  const res = await fetch(`${API_URL}/api/v1/student/recommendations/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Recomendación no encontrada");
  return res.json();
}

export async function submitStudentDifficultyFeedback(
  recommendationId: number,
  difficulty_rating: number,
): Promise<{ difficulty_rating: number; submitted_at: string }> {
  const res = await fetch(
    `${API_URL}/api/v1/student/recommendations/${recommendationId}/feedback`,
    {
      method: "POST",
      headers: authHeaders(),
      body: JSON.stringify({ difficulty_rating }),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "No se pudo enviar la autoevaluación");
  }
  return res.json();
}

export async function downloadStudentDocument(documentId: number, filename: string): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/student/documents/${documentId}/download`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo descargar el PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function openStudentDocument(documentId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/student/documents/${documentId}/download`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo abrir el PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export type TimelineStep = {
  order: number;
  stage: string;
  label: string;
  detail: string;
  timestamp: string | null;
};

export type RecommendationChain = {
  recommendation_id: number;
  student_id: number;
  student_name: string;
  planning_topic: string;
  status: string;
  steps: TimelineStep[];
};

export type CourseDashboardSummary = {
  course_id: number;
  course_name: string;
  students_total: number;
  students_with_profile: number;
  recommendations_total: number;
  recommendations_pending: number;
  recommendations_published: number;
  tai_pct: number;
};

export type CourseTimeline = {
  course_id: number;
  summary: CourseDashboardSummary;
  chains: RecommendationChain[];
};

export async function getAuditTimeline(
  courseId: number,
  params?: { studentId?: number; recommendationId?: number; fromDate?: string; toDate?: string },
): Promise<CourseTimeline> {
  const q = new URLSearchParams({ course_id: String(courseId) });
  if (params?.studentId != null) q.set("student_id", String(params.studentId));
  if (params?.recommendationId != null) q.set("recommendation_id", String(params.recommendationId));
  if (params?.fromDate) q.set("from_date", params.fromDate);
  if (params?.toDate) q.set("to_date", params.toDate);
  const res = await fetch(`${API_URL}/api/v1/audit/timeline?${q}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudo cargar trazabilidad");
  return res.json();
}

export async function downloadCourseXlsx(courseId: number, anonymize = false): Promise<void> {
  const q = anonymize ? "?anonymize=true" : "";
  const res = await fetch(`${API_URL}/api/v1/reports/course/${courseId}/xlsx${q}`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo exportar Excel");
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `sapia_curso_${courseId}.xlsx`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function importCourseCsv(courseId: number, file: File): Promise<{
  created: number;
  enrolled: number;
  skipped: number;
}> {
  const form = new FormData();
  form.append("file", file);
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(`${API_URL}/api/v1/reports/course/${courseId}/import-csv`, {
    method: "POST",
    headers,
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al importar CSV");
  }
  return res.json();
}

export async function downloadCourseCsv(courseId: number, anonymize = false): Promise<void> {
  const q = anonymize ? "?anonymize=true" : "";
  const res = await fetch(`${API_URL}/api/v1/reports/course/${courseId}/csv${q}`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo exportar CSV");
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `sapia_curso_${courseId}.csv`;
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export type AttentionLevel = "ok" | "no_profile" | "pending" | "alert" | "monitor";

export type StudentRow = {
  id: number;
  full_name: string;
  email: string;
  birth_year?: number | null;
  age?: number | null;
  has_profile: boolean;
  attention_level?: AttentionLevel;
};

export type StudentTeacherSummary = {
  id: number;
  full_name: string;
  email: string;
  age: number | null;
  has_profile: boolean;
  model_version: string | null;
  diagnostic_telemetry: {
    items_answered: number;
    items_skipped: number;
    avg_response_ms: number | null;
    total_duration_ms: number | null;
  } | null;
  course_names: string[];
  top_descriptors: { key: string; label: string; value: number }[];
  latest_recommendation: {
    id: number;
    title: string;
    status: string;
    planning_topic: string;
    created_at: string;
  } | null;
  recommendation_counts: { pending: number; published: number; rejected: number };
};

export type TeacherSetupStatus = {
  course_id: number | null;
  course_name: string | null;
  has_indexed_documents: boolean;
  indexed_documents_count: number;
  students_total: number;
  students_with_profile: number;
  students_needing_attention: number;
  recommendations_total: number;
  recommendations_pending: number;
  recommendations_published: number;
  has_generated_recommendation: boolean;
  has_published_recommendation: boolean;
};

export function getToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/sapia_token=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : null;
}

export function authHeaders(): HeadersInit {
  const token = getToken();
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export type OrgLookup = { id: number; name: string; registration_code: string };

export async function orgLookup(code: string): Promise<OrgLookup> {
  const res = await fetch(
    `${API_URL}/api/v1/auth/org-lookup?code=${encodeURIComponent(code.trim())}`,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Código de institución no válido");
  }
  return res.json();
}

export async function register(body: {
  email: string;
  password: string;
  full_name: string;
  org_code: string;
  role: "student" | "teacher";
  birth_year?: number;
}): Promise<string> {
  const res = await fetch(`${API_URL}/api/v1/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al registrarse");
  }
  const data = await res.json();
  return data.access_token as string;
}

export async function login(email: string, password: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      signal: AbortSignal.timeout(15_000),
    });
  } catch {
    throw new Error("No se pudo conectar con el servidor API. Intente de nuevo en unos segundos.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al iniciar sesión");
  }
  const data = await res.json();
  return data.access_token as string;
}

export async function logout(): Promise<void> {
  const token = getToken();
  if (token) {
    await fetch(`${API_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => undefined);
  }
}

export type AdminUser = {
  id: number;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
};

export async function listAdminUsers(): Promise<AdminUser[]> {
  const res = await fetch(`${API_URL}/api/v1/admin/users`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudieron cargar usuarios");
  return res.json();
}

export async function createAdminUser(body: {
  email: string;
  password: string;
  full_name: string;
  role: string;
}): Promise<AdminUser> {
  const res = await fetch(`${API_URL}/api/v1/admin/users`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al crear usuario");
  }
  return res.json();
}

export async function updateAdminUser(
  userId: number,
  body: { full_name?: string; role?: string; is_active?: boolean },
): Promise<AdminUser> {
  const res = await fetch(`${API_URL}/api/v1/admin/users/${userId}`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al actualizar usuario");
  }
  return res.json();
}

export async function fetchMe(token?: string): Promise<UserMe> {
  const t = token ?? getToken();
  if (!t) throw new Error("Sin sesión");
  const res = await fetch(`${API_URL}/api/v1/auth/me`, {
    headers: { Authorization: `Bearer ${t}` },
  });
  if (!res.ok) throw new Error("Sesión inválida");
  return res.json();
}

export function roleHomePath(role: string): string {
  switch (role) {
    case "admin":
      return "/admin";
    case "teacher":
    case "coordinator":
      return "/docente";
    case "student":
      return "/estudiante";
    default:
      return "/login";
  }
}

export async function getDiagnosticStatus(): Promise<{ has_profile: boolean }> {
  const res = await fetch(`${API_URL}/api/v1/diagnostic/status`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudo consultar estado");
  return res.json();
}

export async function getDiagnosticItems(): Promise<DiagnosticItem[]> {
  const res = await fetch(`${API_URL}/api/v1/diagnostic/items`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudieron cargar preguntas");
  return res.json();
}

export async function submitDiagnostic(
  answers: { item_id: number; answer_value: number; response_ms: number; skipped: boolean }[],
  consent: { consent_accepted: boolean; consent_version: string },
): Promise<PedagogicalProfile> {
  const res = await fetch(`${API_URL}/api/v1/diagnostic/submit`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ answers, ...consent }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "Error al enviar test");
  }
  return res.json();
}

export async function getMyProfile(): Promise<PedagogicalProfile> {
  const res = await fetch(`${API_URL}/api/v1/students/me/profile`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Perfil no disponible");
  return res.json();
}

export async function listStudents(courseId?: number): Promise<StudentRow[]> {
  const q = courseId != null ? `?course_id=${courseId}` : "";
  const res = await fetch(`${API_URL}/api/v1/students${q}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudo listar estudiantes");
  return res.json();
}

export async function enrollStudent(courseId: number, studentId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/courses/${courseId}/students`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ student_id: studentId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "No se pudo matricular");
  }
}

export async function unenrollStudent(courseId: number, studentId: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/courses/${courseId}/students/${studentId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail ?? "No se pudo desinscribir");
  }
}

export async function getStudentSummary(studentId: number): Promise<StudentTeacherSummary> {
  const res = await fetch(`${API_URL}/api/v1/teacher/students/${studentId}/summary`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("No se pudo cargar resumen del estudiante");
  return res.json();
}

export async function getTeacherSetupStatus(courseId?: number): Promise<TeacherSetupStatus> {
  const q = courseId != null ? `?course_id=${courseId}` : "";
  const res = await fetch(`${API_URL}/api/v1/teacher/setup-status${q}`, { headers: authHeaders() });
  if (!res.ok) throw new Error("No se pudo cargar estado demo");
  return res.json();
}

export type CourseAnalytics = {
  status_breakdown: Record<string, number>;
  descriptor_averages: { key: string; label: string; value: number }[];
  students_with_profile: number;
  students_total: number;
  difficulty_feedback_count: number;
  difficulty_rating_avg: number | null;
};

export async function getCourseAnalytics(courseId: number): Promise<CourseAnalytics> {
  const res = await fetch(`${API_URL}/api/v1/teacher/courses/${courseId}/analytics`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("No se pudieron cargar analíticas");
  return res.json();
}

export function teacherDocumentUrl(documentId: number): string {
  const token = getToken();
  return `${API_URL}/api/v1/documents/${documentId}/file?token=${token ?? ""}`;
}

export async function downloadRecommendationPdf(id: number): Promise<void> {
  const res = await fetch(`${API_URL}/api/v1/recommendations/${id}/export.pdf`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo exportar PDF");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `sapia_recomendacion_${id}.pdf`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function openTeacherDocument(documentId: number): Promise<string> {
  const res = await fetch(`${API_URL}/api/v1/documents/${documentId}/file`, {
    headers: authHeadersNoContentType(),
  });
  if (!res.ok) throw new Error("No se pudo abrir el PDF");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

export async function getStudentProfile(studentId: number): Promise<PedagogicalProfile> {
  const res = await fetch(`${API_URL}/api/v1/students/${studentId}/profile`, { headers: authHeaders() });
  if (!res.ok) throw new Error("Perfil no generado");
  return res.json();
}
