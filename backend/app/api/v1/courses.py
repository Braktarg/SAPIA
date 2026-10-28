from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_teacher
from app.core.database import get_db
from app.core.enums import UserRole
from app.models import Course, CourseTeacher, Enrollment, User
from app.schemas.course import CourseCreate, CourseRead, EnrollmentCreate
from app.services.auth_service import log_audit, require_roles
from app.services.document_service import teacher_can_access_course

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseRead])
def list_courses(
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[Course]:
    query = db.query(Course).filter(Course.org_id == current_user.org_id)
    if current_user.role_enum == UserRole.STUDENT:
        query = query.join(Enrollment).filter(Enrollment.student_id == current_user.id)
    elif current_user.role_enum == UserRole.TEACHER:
        query = query.join(CourseTeacher).filter(CourseTeacher.teacher_id == current_user.id)
    return query.order_by(Course.id).all()


@router.post("", response_model=CourseRead, status_code=status.HTTP_201_CREATED)
def create_course(
    body: CourseCreate,
    db: Annotated[Session, Depends(get_db)],
    teacher: Annotated[User, Depends(require_teacher)],
) -> Course:
    course = Course(org_id=teacher.org_id, name=body.name, grade_level=body.grade_level)
    db.add(course)
    db.flush()
    if teacher.role_enum == UserRole.TEACHER:
        db.add(CourseTeacher(course_id=course.id, teacher_id=teacher.id))
    db.commit()
    db.refresh(course)
    return course


def _require_course_access(db: Session, user: User, course_id: int) -> Course:
    course = teacher_can_access_course(db, user, course_id)
    if not course:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sin acceso al curso")
    return course


@router.post("/{course_id}/students", status_code=status.HTTP_201_CREATED)
def enroll_student(
    course_id: int,
    body: EnrollmentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    require_roles(current_user, {UserRole.ADMIN, UserRole.TEACHER, UserRole.COORDINATOR})
    course = _require_course_access(db, current_user, course_id)
    student = db.query(User).filter(
        User.id == body.student_id,
        User.org_id == current_user.org_id,
        User.role == UserRole.STUDENT.value,
        User.is_active.is_(True),
    ).first()
    if not student:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
    exists = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id, Enrollment.student_id == body.student_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Estudiante ya inscrito")
    db.add(Enrollment(course_id=course_id, student_id=body.student_id))
    db.commit()
    log_audit(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        entity_type="enrollment",
        entity_id=f"{course_id}:{body.student_id}",
        action="enroll_student",
        payload={"course_id": course_id, "student_id": body.student_id, "course_name": course.name},
    )
    return {"message": "Estudiante inscrito"}


@router.delete("/{course_id}/students/{student_id}", status_code=status.HTTP_200_OK)
def unenroll_student(
    course_id: int,
    student_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, str]:
    require_roles(current_user, {UserRole.ADMIN, UserRole.TEACHER, UserRole.COORDINATOR})
    course = _require_course_access(db, current_user, course_id)
    row = (
        db.query(Enrollment)
        .filter(Enrollment.course_id == course_id, Enrollment.student_id == student_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inscripción no encontrada")
    db.delete(row)
    db.commit()
    log_audit(
        db,
        org_id=current_user.org_id,
        actor_id=current_user.id,
        entity_type="enrollment",
        entity_id=f"{course_id}:{student_id}",
        action="unenroll_student",
        payload={"course_id": course_id, "student_id": student_id, "course_name": course.name},
    )
    return {"message": "Estudiante desinscrito"}
