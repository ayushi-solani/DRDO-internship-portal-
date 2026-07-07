-- ============================================================
--  DRDO Internship Portal - MySQL Database Schema v2.0
--  Replaces original schema.sql entirely.
--
--  Run:
--    mysql -u root -p < schema.sql
--
--  To reset an existing database first:
--    mysql -u root -p -e "DROP DATABASE IF EXISTS drdo_portal;"
--    mysql -u root -p < schema.sql
--
--  Tables: 17 (was 5)
--  Password hashes: Real Werkzeug scrypt hashes
--  Credentials:
--    admin@drdo.in     → Admin@1234
--    hr@drdo.in        → Hr@1234
--    alice@example.com → Alice@1234
--    bob@example.com   → Bob@1234
-- ============================================================

CREATE DATABASE IF NOT EXISTS drdo_portal
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE drdo_portal;

-- ============================================================
-- TABLE CREATION ORDER (dependency order — do not reorder)
-- users → departments → labs → hr_profiles →
-- candidate_profiles → internship_positions →
-- applications → application_history →
-- interview_schedules → mentor_allocations →
-- notifications → audit_logs → certificates →
-- plagiarism_reports → skill_gap_reports →
-- progress_logs → system_config
-- ============================================================


-- ============================================================
-- TABLE 1: users
-- Central authentication table for all roles.
-- Every person in the system has exactly one row here.
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id               INT           AUTO_INCREMENT PRIMARY KEY,
    full_name        VARCHAR(150)  NOT NULL,
    email            VARCHAR(150)  NOT NULL UNIQUE,
    password_hash    VARCHAR(255)  NOT NULL,
    role             ENUM('admin','hr','candidate')
                                   NOT NULL DEFAULT 'candidate',
    phone            VARCHAR(20),

    -- Account state
    is_active        TINYINT(1)    NOT NULL DEFAULT 1,
    is_approved      TINYINT(1)    NOT NULL DEFAULT 1,
    -- is_approved logic by role:
    --   candidate → 1 (approved immediately on self-registration)
    --   hr        → 0 (Admin must approve before first login)
    --   admin     → 1 (seed-created only, always approved)

    -- Login tracking
    last_login       DATETIME      NULL,
    failed_attempts  TINYINT       NOT NULL DEFAULT 0,
    -- Account locks when failed_attempts reaches 5.
    -- Login route: increment on failure, reset on success.
    -- Admin unlocks by setting is_active=1, failed_attempts=0.

    -- Security clearance (DRDO-specific)
    clearance_level  ENUM('None','Confidential','Secret')
                                   NOT NULL DEFAULT 'None',
    -- Only Admin can change this value.
    -- Gates applications to clearance-required positions.

    -- JWT token invalidation
    jwt_version      INT           NOT NULL DEFAULT 0,
    -- Incremented on every password change.
    -- JWTs carrying a lower version number are immediately invalid.

    created_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role  ON users(role);


-- ============================================================
-- TABLE 2: departments
-- DRDO organisational divisions. Managed by Admin.
-- Must exist before hr_profiles and internship_positions.
-- ============================================================
CREATE TABLE IF NOT EXISTS departments (
    id          INT           AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150)  NOT NULL UNIQUE,
    code        VARCHAR(20)   NOT NULL UNIQUE,
    description TEXT,
    is_active   TINYINT(1)    NOT NULL DEFAULT 1,
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
);


-- ============================================================
-- TABLE 3: labs
-- Laboratories within departments. Managed by Admin.
-- ============================================================
CREATE TABLE IF NOT EXISTS labs (
    id            INT           AUTO_INCREMENT PRIMARY KEY,
    department_id INT           NOT NULL,
    name          VARCHAR(150)  NOT NULL,
    code          VARCHAR(30)   NOT NULL UNIQUE,
    location      VARCHAR(150),
    is_active     TINYINT(1)    NOT NULL DEFAULT 1,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE RESTRICT
    -- RESTRICT: cannot delete a department that still has labs.
);


-- ============================================================
-- TABLE 4: hr_profiles
-- Professional profile for HR officers and scientist mentors.
-- 1-to-1 with users where role = 'hr'.
-- ============================================================
CREATE TABLE IF NOT EXISTS hr_profiles (
    id            INT           AUTO_INCREMENT PRIMARY KEY,
    user_id       INT           NOT NULL UNIQUE,
    designation   VARCHAR(100),
    department_id INT           NULL,
    lab           VARCHAR(150),
    employee_id   VARCHAR(50)   UNIQUE,
    created_at    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE SET NULL
);


-- ============================================================
-- TABLE 5: candidate_profiles
-- Academic and personal profile for candidates.
-- 1-to-1 with users where role = 'candidate'.
-- ============================================================
CREATE TABLE IF NOT EXISTS candidate_profiles (
    id                     INT           AUTO_INCREMENT PRIMARY KEY,
    user_id                INT           NOT NULL UNIQUE,

    -- Personal info
    dob                    DATE,
    gender                 ENUM('Male','Female','Other'),
    address                TEXT,

    -- Academic info
    college                VARCHAR(200),
    degree                 VARCHAR(100),
    branch                 VARCHAR(100),
    graduation_year        YEAR,
    cgpa                   DECIMAL(4,2),

    -- Skills
    skills                 TEXT,
    -- Self-declared by candidate (comma-separated freetext).

    extracted_skills       TEXT,
    -- NLP pipeline output after resume processing.
    -- Stored as JSON array: '["Python","TensorFlow","SQL"]'
    -- NULL until resume is uploaded and processed.

    -- AI classification
    ai_classification      VARCHAR(100),
    -- Predicted research domain from SVM classifier.
    -- NULL until AI pipeline runs.

    ai_confidence_score    DECIMAL(5,4),
    -- SVM confidence: 0.0000 to 1.0000
    -- NULL until AI pipeline runs.

    -- Profile completeness
    profile_completion_pct DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    -- Recalculated on every profile save.

    -- Resume
    resume_url             VARCHAR(300),
    -- Path to current resume at /var/drdo_uploads/
    resume_uploaded_at     DATETIME      NULL,
    -- Timestamp of last upload (used for plagiarism ordering).

    -- External profiles
    linkedin_url           VARCHAR(300),
    github_url             VARCHAR(300),

    created_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- ============================================================
-- TABLE 6: internship_positions
-- Internship openings created by HR officers.
-- ============================================================
CREATE TABLE IF NOT EXISTS internship_positions (
    id               INT            AUTO_INCREMENT PRIMARY KEY,
    title            VARCHAR(200)   NOT NULL,

    -- Organisational links
    department_id    INT            NULL,
    lab_id           INT            NULL,

    location         VARCHAR(150)   DEFAULT 'DRDO HQ, New Delhi',
    description      TEXT,
    requirements     TEXT,
    -- Human-readable paragraph shown to candidates.

    required_skills  TEXT,
    -- Machine-readable comma-separated skill list for AI matching.
    -- e.g. "Python,TensorFlow,Signal Processing,MATLAB"

    -- Research domain
    research_area    ENUM('AI','Cyber Security',
                         'Embedded Systems','Radar','Aerospace')
                                    NULL,

    -- Logistics
    duration         VARCHAR(50),
    stipend          DECIMAL(10,2),
    total_seats      INT            NOT NULL DEFAULT 1,
    filled_seats     INT            NOT NULL DEFAULT 0,
    -- Incremented when application status set to 'Selected'.
    -- Apply button disabled when filled_seats = total_seats.

    deadline         DATE,

    -- Security
    clearance_required ENUM('None','Confidential','Secret')
                                    NOT NULL DEFAULT 'None',

    is_active        TINYINT(1)     NOT NULL DEFAULT 1,
    created_by       INT            NOT NULL,

    created_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (department_id)
        REFERENCES departments(id)
        ON DELETE SET NULL,
    FOREIGN KEY (lab_id)
        REFERENCES labs(id)
        ON DELETE SET NULL,
    FOREIGN KEY (created_by)
        REFERENCES users(id)
);

CREATE INDEX idx_positions_active   ON internship_positions(is_active);
CREATE INDEX idx_positions_research ON internship_positions(research_area);
CREATE INDEX idx_positions_deadline ON internship_positions(deadline);


-- ============================================================
-- TABLE 7: applications
-- One row per candidate-position pair.
-- UNIQUE constraint prevents duplicate applications.
-- ============================================================
CREATE TABLE IF NOT EXISTS applications (
    id                   INT           AUTO_INCREMENT PRIMARY KEY,
    candidate_id         INT           NOT NULL,
    position_id          INT           NOT NULL,
    cover_letter         TEXT,

    status               ENUM(
                           'Submitted',
                           'Under Review',
                           'Shortlisted',
                           'Interview Scheduled',
                           'Selected',
                           'Rejected'
                         ) NOT NULL DEFAULT 'Submitted',

    -- AI scoring (computed on submission, stored permanently)
    ai_match_score       DECIMAL(5,2)  NULL,
    -- 0.00 to 100.00. NULL until AI pipeline completes.

    ai_rank              INT           NULL,
    -- Rank within this position's applicant pool (1 = best).
    -- Recalculated when a new candidate applies.

    -- Resume snapshot at time of application
    resume_snapshot_url  VARCHAR(300)  NULL,
    -- Captures the exact resume submitted, even if candidate
    -- uploads a new one later.

    -- HR review
    hr_remarks           TEXT,
    reviewed_by          INT           NULL,
    reviewed_at          DATETIME      NULL,

    applied_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                       ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_candidate_position (candidate_id, position_id),

    FOREIGN KEY (candidate_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    FOREIGN KEY (position_id)
        REFERENCES internship_positions(id)
        ON DELETE CASCADE,
    FOREIGN KEY (reviewed_by)
        REFERENCES users(id)
        ON DELETE SET NULL
);

CREATE INDEX idx_apps_candidate ON applications(candidate_id);
CREATE INDEX idx_apps_position  ON applications(position_id);
CREATE INDEX idx_apps_status    ON applications(status);
CREATE INDEX idx_apps_score     ON applications(position_id, ai_match_score DESC);


-- ============================================================
-- TABLE 8: application_history
-- Immutable audit trail of every status change.
-- INSERT only — no UPDATE or DELETE at application level.
-- ============================================================
CREATE TABLE IF NOT EXISTS application_history (
    id               INT           AUTO_INCREMENT PRIMARY KEY,
    application_id   INT           NOT NULL,
    old_status       VARCHAR(50),
    -- NULL for the first entry (no previous status).
    new_status       VARCHAR(50)   NOT NULL,
    remarks          TEXT,
    changed_by       INT           NOT NULL,
    ip_address       VARCHAR(45),
    -- VARCHAR(45) supports both IPv4 and IPv6 addresses.
    action_type      VARCHAR(100)  NOT NULL DEFAULT 'status_change',
    -- e.g. 'status_change', 'remark_added', 'interview_scheduled'
    changed_at       DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE CASCADE,
    FOREIGN KEY (changed_by)
        REFERENCES users(id)
);

CREATE INDEX idx_history_application ON application_history(application_id);


-- ============================================================
-- TABLE 9: interview_schedules
-- Interview details when status = 'Interview Scheduled'.
-- One row per application. UPDATE on reschedule (not INSERT).
-- ============================================================
CREATE TABLE IF NOT EXISTS interview_schedules (
    id                  INT           AUTO_INCREMENT PRIMARY KEY,
    application_id      INT           NOT NULL UNIQUE,
    scheduled_by        INT           NOT NULL,
    interview_date      DATE          NOT NULL,
    interview_time      TIME          NOT NULL,
    mode                ENUM('Online','In-Person','Hybrid')
                                      NOT NULL DEFAULT 'Online',
    meeting_link        VARCHAR(500),
    venue               VARCHAR(300),
    interviewer_names   TEXT,
    notes               TEXT,
    candidate_confirmed TINYINT(1)    NOT NULL DEFAULT 0,
    created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                                      ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE CASCADE,
    FOREIGN KEY (scheduled_by)
        REFERENCES users(id)
);


-- ============================================================
-- TABLE 10: mentor_allocations
-- Mentor assignment after candidate is Selected.
-- One mentor per selected application.
-- ============================================================
CREATE TABLE IF NOT EXISTS mentor_allocations (
    id             INT       AUTO_INCREMENT PRIMARY KEY,
    application_id INT       NOT NULL UNIQUE,
    mentor_id      INT       NOT NULL,
    allocated_by   INT       NOT NULL,
    allocated_at   DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes          TEXT,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE CASCADE,
    FOREIGN KEY (mentor_id)
        REFERENCES users(id),
    FOREIGN KEY (allocated_by)
        REFERENCES users(id)
);


-- ============================================================
-- TABLE 11: notifications
-- In-app notifications for all user roles.
-- ============================================================
CREATE TABLE IF NOT EXISTS notifications (
    id                     INT           AUTO_INCREMENT PRIMARY KEY,
    user_id                INT           NOT NULL,
    title                  VARCHAR(200)  NOT NULL,
    message                TEXT          NOT NULL,
    type                   ENUM(
                             'status_update',
                             'interview',
                             'offer',
                             'rejection',
                             'system'
                           ) NOT NULL DEFAULT 'system',
    is_read                TINYINT(1)    NOT NULL DEFAULT 0,
    related_application_id INT           NULL,
    created_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    FOREIGN KEY (related_application_id)
        REFERENCES applications(id)
        ON DELETE SET NULL
);

CREATE INDEX idx_notifications_user ON notifications(user_id, is_read);


-- ============================================================
-- TABLE 12: audit_logs
-- System-wide append-only log of all HR and Admin actions.
-- Broader than application_history — covers logins, user
-- management, config changes, and position management.
-- INSERT only — no UPDATE or DELETE at application level.
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id          INT           AUTO_INCREMENT PRIMARY KEY,
    user_id     INT           NOT NULL,
    action      VARCHAR(100)  NOT NULL,
    -- e.g. 'login', 'position_created', 'candidate_shortlisted'
    entity_type VARCHAR(100),
    -- Type of record affected: 'user', 'application', etc.
    entity_id   INT,
    -- Primary key of the affected record.
    old_value   TEXT,
    -- JSON of values before the change. NULL for create actions.
    new_value   TEXT,
    -- JSON of values after the change. NULL for delete actions.
    ip_address  VARCHAR(45),
    user_agent  VARCHAR(500),
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)
        REFERENCES users(id)
);

CREATE INDEX idx_audit_user    ON audit_logs(user_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
CREATE INDEX idx_audit_action  ON audit_logs(action);


-- ============================================================
-- TABLE 13: certificates
-- Internship completion certificates issued by Admin.
-- ============================================================
CREATE TABLE IF NOT EXISTS certificates (
    id                    INT           AUTO_INCREMENT PRIMARY KEY,
    application_id        INT           NOT NULL UNIQUE,
    candidate_id          INT           NOT NULL,
    position_id           INT           NOT NULL,
    issued_by             INT           NOT NULL,
    certificate_number    VARCHAR(100)  NOT NULL UNIQUE,
    -- Format: DRDO-CERT-YYYY-NNNNNN (e.g. DRDO-CERT-2026-000001)
    file_url              VARCHAR(300)  NOT NULL,
    issued_at             DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    internship_start_date DATE,
    internship_end_date   DATE,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE RESTRICT,
    -- RESTRICT: cannot delete an application with a certificate.
    FOREIGN KEY (candidate_id)
        REFERENCES users(id),
    FOREIGN KEY (position_id)
        REFERENCES internship_positions(id),
    FOREIGN KEY (issued_by)
        REFERENCES users(id)
);


-- ============================================================
-- TABLE 14: plagiarism_reports
-- Resume similarity check results.
-- One row per (new_resume, existing_resume) pair above 0.50.
-- ============================================================
CREATE TABLE IF NOT EXISTS plagiarism_reports (
    id                   INT            AUTO_INCREMENT PRIMARY KEY,
    candidate_id         INT            NOT NULL,
    -- The candidate whose resume was just uploaded.
    compared_against     INT            NOT NULL,
    -- The existing candidate whose resume was compared.
    similarity_score     DECIMAL(5,4)   NOT NULL,
    -- 0.0000 to 1.0000.
    is_flagged           TINYINT(1)     NOT NULL DEFAULT 0,
    -- 1 = similarity exceeded threshold (default 0.85).
    hr_override_remarks  TEXT,
    -- HR can resolve a flag with an explanation.
    checked_at           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (candidate_id)
        REFERENCES users(id)
        ON DELETE CASCADE,
    FOREIGN KEY (compared_against)
        REFERENCES users(id)
        ON DELETE CASCADE
);


-- ============================================================
-- TABLE 15: skill_gap_reports
-- AI-computed skill gap per application.
-- One row per application, computed at submission time.
-- ============================================================
CREATE TABLE IF NOT EXISTS skill_gap_reports (
    id               INT       AUTO_INCREMENT PRIMARY KEY,
    application_id   INT       NOT NULL UNIQUE,
    matching_skills  TEXT,
    -- JSON array of skills candidate HAS that are required.
    -- e.g. '["Python","SQL","pandas"]'
    missing_skills   TEXT,
    -- JSON array of required skills the candidate does NOT have.
    -- e.g. '["FPGA","VHDL","Embedded C"]'
    computed_at      DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE CASCADE
);


-- ============================================================
-- TABLE 16: progress_logs
-- HR/Mentor progress updates for selected interns.
-- Multiple entries per application (one per weekly update).
-- ============================================================
CREATE TABLE IF NOT EXISTS progress_logs (
    id                   INT            AUTO_INCREMENT PRIMARY KEY,
    application_id       INT            NOT NULL,
    logged_by            INT            NOT NULL,
    progress_date        DATE           NOT NULL,
    title                VARCHAR(200)   NOT NULL,
    description          TEXT,
    percentage_complete  DECIMAL(5,2)   NOT NULL DEFAULT 0.00,
    -- 0.00 to 100.00. Last entry shown to candidate as overall %.
    created_at           DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (application_id)
        REFERENCES applications(id)
        ON DELETE CASCADE,
    FOREIGN KEY (logged_by)
        REFERENCES users(id)
);

CREATE INDEX idx_progress_application ON progress_logs(application_id);


-- ============================================================
-- TABLE 17: system_config
-- Admin-configurable key-value settings.
-- Seeded with defaults. Updated via Admin portal UI.
-- ============================================================
CREATE TABLE IF NOT EXISTS system_config (
    id           INT           AUTO_INCREMENT PRIMARY KEY,
    config_key   VARCHAR(100)  NOT NULL UNIQUE,
    config_value VARCHAR(500)  NOT NULL,
    description  TEXT,
    updated_by   INT           NULL,
    updated_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                               ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (updated_by)
        REFERENCES users(id)
        ON DELETE SET NULL
);


-- ============================================================
-- SEED DATA
-- All password hashes are real Werkzeug scrypt hashes.
-- They work correctly with werkzeug.security.check_password_hash
-- Credentials:
--   admin@drdo.in     → Admin@1234
--   hr@drdo.in        → Hr@1234
--   alice@example.com → Alice@1234
--   bob@example.com   → Bob@1234
-- ============================================================

-- Users
INSERT INTO users
    (full_name, email, password_hash, role, phone, is_active, is_approved)
VALUES
(
    'DRDO Admin',
    'admin@drdo.in',
    'scrypt:32768:8:1$kQO0pAll3Jc8POzb$cf7b166340d0a5a49ce326cb83323c76ba6443c89bdaa5a6d6a28931dfca2c889c06757bc13e56f09a5cc2728e14fb454fe809020a1c3ed08abb98e11bd32527',
    'admin', '9000000001', 1, 1
),
(
    'Dr. Ramesh Kumar',
    'hr@drdo.in',
    'scrypt:32768:8:1$5cp4tVuXom9f22Za$c7c279b921271e70c995f89d40c31601ac758413af0f13b2a0d1367b16737fb962244055ca7db2f14fc63103ffde13fc370afa70ebc1bcea3ac79fcbe3cb11f1',
    'hr', '9000000002', 1, 1
),
(
    'Alice Sharma',
    'alice@example.com',
    'scrypt:32768:8:1$RYqdUt9bhHBhjQ4y$daed629285b4d5724b0bcd9927c9ad4b3b2725a0e2cddc003e043b4040e3359e544b34553b19b9205501fcb3b820bf6d6447e14a8cd67a9dc80fad1e22ce03b7',
    'candidate', '9111111111', 1, 1
),
(
    'Bob Verma',
    'bob@example.com',
    'scrypt:32768:8:1$52XApyPcBBJ1Smvz$fed8d6540c064bc1030f5c8347b02ff950af94a47e0623e4c6495b0e674c6b0cc1b776f088c001efb042efb4f10709bb0cc08fe97a598b60196791627077e228',
    'candidate', '9222222222', 1, 1
);

-- Departments
INSERT INTO departments (name, code, description) VALUES
('Electronics & Radar',  'ELEC', 'Radar systems, signal processing, electronic warfare'),
('Armament Research',    'ARM',  'Weapons systems, explosives, ballistics'),
('Life Sciences',        'LIFE', 'Biomedical research, food tech, performance enhancement'),
('Information Systems',  'INFO', 'Cybersecurity, networks, information warfare'),
('Aerospace',            'AERO', 'Aeronautics, missiles, propulsion systems');

-- Labs
INSERT INTO labs (department_id, name, code, location) VALUES
(1, 'Radar Signal Processing Lab', 'ELEC-RSP', 'DRDO, Bangalore'),
(1, 'Electronic Warfare Lab',      'ELEC-EW',  'DRDO, Bangalore'),
(2, 'Armament Systems Lab',        'ARM-SYS',  'DRDO, Pune'),
(3, 'Biomedical Research Lab',     'LIFE-BIO', 'DRDO, Delhi'),
(4, 'Cyber Operations Lab',        'INFO-CYB', 'DRDO, Hyderabad'),
(5, 'Aerospace Propulsion Lab',    'AERO-PRO', 'DRDO, Bangalore');

-- HR profile for seed HR user (user id = 2)
INSERT INTO hr_profiles (user_id, designation, department_id, employee_id)
VALUES (2, 'Scientist-D', 1, 'DRDO-EMP-00002');

-- Candidate profiles (empty shells — candidates fill via portal)
INSERT INTO candidate_profiles (user_id) VALUES (3);
INSERT INTO candidate_profiles (user_id) VALUES (4);

-- Internship Positions
INSERT INTO internship_positions
    (title, department_id, lab_id, location, description,
     requirements, required_skills, research_area,
     duration, stipend, total_seats, deadline, is_active, created_by)
VALUES
(
    'AI/ML Research Intern',
    1, 1,
    'DRDO, Bangalore',
    'Work on AI-based radar signal processing algorithms using deep learning.',
    'B.Tech/M.Tech in CS/ECE. Strong foundation in mathematics. Experience with Python ML libraries.',
    'Python,TensorFlow,PyTorch,Signal Processing,NumPy,MATLAB',
    'AI',
    '2 Months', 8000.00, 5, '2026-08-31', 1, 2
),
(
    'Embedded Systems Intern',
    2, 3,
    'DRDO, Pune',
    'Design and test embedded firmware for weapon guidance systems.',
    'B.Tech in ECE/EEE. C/C++ proficiency required. ARM Cortex experience preferred.',
    'C,C++,ARM Cortex,RTOS,Embedded C,Keil MDK',
    'Embedded Systems',
    '3 Months', 10000.00, 3, '2026-09-15', 1, 2
),
(
    'Data Science Intern',
    3, 4,
    'DRDO, Delhi',
    'Data analysis and predictive modelling for biomedical defence research.',
    'B.Tech/B.Sc in CS or Statistics. Proficiency in Python data stack required.',
    'Python,SQL,pandas,scikit-learn,NumPy,Matplotlib,Statistics',
    'AI',
    '2 Months', 7500.00, 4, '2026-08-01', 1, 2
),
(
    'Cybersecurity Research Intern',
    4, 5,
    'DRDO, Hyderabad',
    'Research in network security protocols and applied cryptography.',
    'B.Tech in CS/IT. Networking fundamentals required. Ethical hacking basics preferred.',
    'Python,Network Security,Cryptography,Wireshark,Linux,TCP/IP',
    'Cyber Security',
    '3 Months', 9000.00, 2, '2026-09-30', 1, 2
);

-- System configuration defaults
INSERT INTO system_config (config_key, config_value, description) VALUES
('ai_weight_tfidf',         '0.40', 'Weight for TF-IDF text match in composite AI score'),
('ai_weight_skill_overlap', '0.25', 'Weight for skill overlap percentage in composite AI score'),
('ai_weight_cgpa',          '0.20', 'Weight for normalised CGPA in composite AI score'),
('ai_weight_confidence',    '0.15', 'Weight for SVM domain confidence in composite AI score'),
('plagiarism_threshold',    '0.85', 'Cosine similarity score above which a resume is flagged'),
('max_upload_size_mb',      '5',    'Maximum allowed resume file size in megabytes'),
('max_login_attempts',      '5',    'Failed login attempts before account is locked'),
('token_expiry_hours',      '24',   'JWT token validity period in hours');

-- ============================================================
-- END OF schema.sql v2.0
-- 17 tables | Real password hashes | Complete seed data
-- ============================================================ 