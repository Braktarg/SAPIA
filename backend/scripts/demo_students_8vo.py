"""Curso simulado: 15 estudiantes de 8° básico con perfiles pedagógicos distintos."""

from datetime import UTC, datetime

from app.core.enums import UserRole
from app.core.security import hash_password
from app.models import (
    Course,
    DiagnosticAnswer,
    DiagnosticItem,
    DiagnosticSession,
    Enrollment,
    Organization,
    PedagogicalProfile,
    User,
)
from app.services.diagnostic_service import get_latest_profile
from ml.predictor import get_predictor

DEMO_PASSWORD = "Sapia2026!"
COURSE_NAME = "8° Básico A"
SEED_MARKER_EMAIL = "catalina.morales@8vo.demo.sapia.cl"

# Respuestas diagnóstico (12 ítems, valores 0–2) → perfiles variados vía Random Forest
STUDENTS_8VO = [
    {
        "full_name": "Matías Rojas",
        "email": "estudiante@demo.sapia.cl",
        "birth_year": 2012,
        "answers": [1, 0, 2, 1, 0, 0, 1, 1, 0, 2, 1, 1],
        "note": "Apoyo visual y rutinas",
    },
    {
        "full_name": "Catalina Morales",
        "email": "catalina.morales@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [2, 2, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2],
        "note": "Alto desempeño general",
    },
    {
        "full_name": "Benjamín Soto",
        "email": "benjamin.soto@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [1, 0, 2, 0, 0, 0, 0, 0, 0, 2, 0, 1],
        "note": "Atención y lectura con apoyo",
    },
    {
        "full_name": "Sofía Herrera",
        "email": "sofia.herrera@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [2, 1, 2, 2, 1, 1, 2, 1, 1, 1, 2, 2],
        "note": "Colaborativa y visual",
    },
    {
        "full_name": "Diego Paredes",
        "email": "diego.paredes@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [0, 2, 0, 1, 2, 2, 1, 2, 1, 0, 2, 1],
        "note": "Autónomo, prefiere texto",
    },
    {
        "full_name": "Valentina Cruz",
        "email": "valentina.cruz@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [1, 1, 2, 1, 1, 0, 1, 0, 1, 2, 1, 2],
        "note": "Regulación emocional con apoyo",
    },
    {
        "full_name": "Tomás Abarca",
        "email": "tomas.abarca@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [2, 0, 1, 0, 1, 1, 2, 2, 0, 1, 1, 2],
        "note": "Fuerte en lógica matemática",
    },
    {
        "full_name": "Isidora Campos",
        "email": "isidora.campos@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [1, 2, 2, 2, 2, 1, 1, 1, 2, 2, 2, 1],
        "note": "Trabajo grupal y pictogramas",
    },
    {
        "full_name": "Lucas Fernández",
        "email": "lucas.fernandez@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [0, 1, 1, 1, 0, 2, 2, 1, 2, 0, 2, 2],
        "note": "Interés temático alto",
    },
    {
        "full_name": "Antonia Vega",
        "email": "antonia.vega@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [2, 1, 0, 2, 1, 2, 2, 0, 1, 1, 2, 0],
        "note": "Lectora fluida, poco apoyo visual",
    },
    {
        "full_name": "Vicente Miranda",
        "email": "vicente.miranda@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [1, 0, 1, 0, 0, 0, 0, 1, 0, 2, 0, 1],
        "note": "Necesita tiempo y estructura",
    },
    {
        "full_name": "Florencia Núñez",
        "email": "florencia.nunez@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [1, 2, 2, 1, 2, 1, 1, 2, 2, 1, 2, 2],
        "note": "Equilibrada, buena autonomía",
    },
    {
        "full_name": "Maximiliano Salinas",
        "email": "maximiliano.salinas@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [2, 2, 0, 0, 2, 2, 1, 2, 1, 0, 1, 1],
        "note": "Independiente, baja preferencia grupal",
    },
    {
        "full_name": "Javiera Toledo",
        "email": "javiera.toledo@8vo.demo.sapia.cl",
        "birth_year": 2013,
        "answers": [1, 1, 2, 2, 0, 1, 0, 0, 2, 2, 2, 2],
        "note": "Visual y expresiva",
    },
    {
        "full_name": "Cristóbal Espinoza",
        "email": "cristobal.espinoza@8vo.demo.sapia.cl",
        "birth_year": 2012,
        "answers": [0, 0, 2, 1, 1, 0, 1, 1, 1, 2, 1, 0],
        "note": "Perfil mixto con apoyo lector",
    },
]


def _age(birth_year: int) -> int:
    return datetime.now(UTC).year - birth_year


def _create_profile(db, student_id: int, answers: list[int]) -> None:
    if get_latest_profile(db, student_id):
        return
    items = db.query(DiagnosticItem).order_by(DiagnosticItem.sort_order).all()
    if len(items) != 12:
        raise RuntimeError("Banco diagnóstico incompleto — ejecute seed_diagnostic_items primero")

    session = DiagnosticSession(student_id=student_id)
    db.add(session)
    db.flush()

    for item, value in zip(items, answers, strict=True):
        db.add(
            DiagnosticAnswer(
                session_id=session.id,
                item_id=item.id,
                answer_value=value,
                response_ms=3000 + value * 500,
                skipped=False,
            )
        )

    predictor = get_predictor()
    descriptors, importances = predictor.predict(answers)
    import json

    profile = PedagogicalProfile(
        student_id=student_id,
        session_id=session.id,
        version=1,
        descriptors_json=json.dumps(descriptors),
        feature_importance_json=json.dumps(importances),
        model_version=predictor.model_version,
    )
    session.completed_at = datetime.now(UTC)
    db.add(profile)


def seed_8vo_classroom(db) -> None:
    if db.query(User).filter(User.email == SEED_MARKER_EMAIL).first():
        print("Curso 8° básico (15 estudiantes) ya cargado — omitiendo.")
        return

    org = db.query(Organization).first()
    if not org:
        print("Sin organización demo — omitiendo curso 8vo.")
        return

    course = (
        db.query(Course)
        .filter(Course.org_id == org.id, Course.grade_level == "8°")
        .first()
    )
    if not course:
        course = Course(org_id=org.id, name=COURSE_NAME, grade_level="8°")
        db.add(course)
        db.flush()

    pwd = hash_password(DEMO_PASSWORD)
    created = 0

    for spec in STUDENTS_8VO:
        student = db.query(User).filter(User.email == spec["email"]).first()
        if student:
            student.full_name = spec["full_name"]
            student.birth_year = spec["birth_year"]
        else:
            student = User(
                org_id=org.id,
                email=spec["email"],
                password_hash=pwd,
                full_name=spec["full_name"],
                birth_year=spec["birth_year"],
                role=UserRole.STUDENT.value,
            )
            db.add(student)
            db.flush()
            created += 1

        enrolled = (
            db.query(Enrollment)
            .filter(Enrollment.course_id == course.id, Enrollment.student_id == student.id)
            .first()
        )
        if not enrolled:
            db.add(Enrollment(course_id=course.id, student_id=student.id))

        _create_profile(db, student.id, spec["answers"])

    db.commit()
    print(f"Curso «{COURSE_NAME}»: {len(STUDENTS_8VO)} estudiantes con perfil ({created} usuarios nuevos).")
    print(f"  Acceso estudiante demo: estudiante@demo.sapia.cl / {DEMO_PASSWORD}")
    print(f"  Edades: {_age(2013)}–{_age(2012)} años (8° básico)")
