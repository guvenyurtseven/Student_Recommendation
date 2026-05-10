PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    retrieved_at_utc TEXT NOT NULL,
    content_path TEXT,
    content_sha256 TEXT,
    parser_version TEXT,
    UNIQUE(source_url, content_sha256)
);

CREATE TABLE IF NOT EXISTS programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    abbr TEXT NOT NULL UNIQUE,
    catalog_program_id TEXT UNIQUE,
    name_en TEXT NOT NULL,
    name_tr TEXT,
    faculty TEXT NOT NULL,
    is_active_undergraduate INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    numeric_code TEXT UNIQUE,
    subject_code TEXT NOT NULL,
    course_number INTEGER NOT NULL,
    display_code TEXT NOT NULL UNIQUE,
    title_en TEXT,
    title_tr TEXT,
    level TEXT NOT NULL DEFAULT 'undergraduate'
);

CREATE TABLE IF NOT EXISTS course_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    alias TEXT NOT NULL UNIQUE,
    relation_type TEXT NOT NULL DEFAULT 'manual_alias',
    review_status TEXT NOT NULL DEFAULT 'reviewed',
    notes TEXT,
    source_document_id INTEGER REFERENCES source_documents(id)
);

CREATE TABLE IF NOT EXISTS manual_correction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    correction_type TEXT NOT NULL,
    correction_key TEXT NOT NULL,
    action TEXT NOT NULL,
    review_status TEXT NOT NULL,
    applied_at_utc TEXT NOT NULL,
    source_document_id INTEGER REFERENCES source_documents(id),
    payload_json TEXT NOT NULL,
    notes TEXT,
    UNIQUE(correction_type, correction_key, action, source_document_id)
);

CREATE TABLE IF NOT EXISTS curriculum_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL REFERENCES programs(id) ON DELETE CASCADE,
    version_label TEXT NOT NULL,
    effective_from_year INTEGER,
    effective_to_year INTEGER,
    is_latest INTEGER NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'scraped',
    source_document_id INTEGER REFERENCES source_documents(id),
    notes TEXT,
    UNIQUE(program_id, version_label)
);

CREATE TABLE IF NOT EXISTS curriculum_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    curriculum_version_id INTEGER NOT NULL REFERENCES curriculum_versions(id) ON DELETE CASCADE,
    requirement_type TEXT NOT NULL,
    label TEXT NOT NULL,
    recommended_year INTEGER,
    recommended_term TEXT,
    course_count_min INTEGER,
    credits_min REAL,
    ects_min REAL,
    sort_order INTEGER,
    review_status TEXT NOT NULL DEFAULT 'scraped',
    source_document_id INTEGER REFERENCES source_documents(id)
);

CREATE TABLE IF NOT EXISTS requirement_options (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requirement_id INTEGER NOT NULL REFERENCES curriculum_requirements(id) ON DELETE CASCADE,
    course_id INTEGER REFERENCES courses(id),
    option_label TEXT,
    option_group TEXT,
    is_required_option INTEGER NOT NULL DEFAULT 1,
    source_document_id INTEGER REFERENCES source_documents(id),
    CHECK(course_id IS NOT NULL OR option_label IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS prerequisite_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prerequisite_course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    set_no TEXT,
    min_grade TEXT,
    edge_type TEXT,
    position TEXT,
    source_document_id INTEGER REFERENCES source_documents(id),
    UNIQUE(prerequisite_course_id, course_id, set_no, min_grade)
);

CREATE TABLE IF NOT EXISTS offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    semester_no TEXT NOT NULL,
    department_program_id INTEGER REFERENCES programs(id),
    source_document_id INTEGER REFERENCES source_documents(id),
    UNIQUE(course_id, semester_no, department_program_id)
);

CREATE TABLE IF NOT EXISTS student_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    program_id INTEGER NOT NULL REFERENCES programs(id),
    curriculum_version_id INTEGER REFERENCES curriculum_versions(id),
    entry_year INTEGER,
    created_at_utc TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS student_completed_courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_profile_id INTEGER NOT NULL REFERENCES student_profiles(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    grade TEXT,
    completed_semester_no TEXT,
    UNIQUE(student_profile_id, course_id)
);

CREATE INDEX IF NOT EXISTS idx_courses_subject_number
    ON courses(subject_code, course_number);

CREATE INDEX IF NOT EXISTS idx_course_aliases_course
    ON course_aliases(course_id);

CREATE INDEX IF NOT EXISTS idx_curriculum_requirements_version
    ON curriculum_requirements(curriculum_version_id);

CREATE INDEX IF NOT EXISTS idx_prereq_edges_course
    ON prerequisite_edges(course_id);

CREATE INDEX IF NOT EXISTS idx_prereq_edges_prerequisite
    ON prerequisite_edges(prerequisite_course_id);
