-- =============================================================================
-- Job Search & Recommendation App - Database Schema
-- Database: job_recommendation_db
-- Target: MySQL Server 8.0+ / MySQL Workbench
-- Engine: InnoDB | Character Set: utf8mb4 | Collation: utf8mb4_unicode_ci
-- =============================================================================

CREATE DATABASE IF NOT EXISTS job_recommendation_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE job_recommendation_db;

-- -----------------------------------------------------------------------------
-- 1. users: Stores candidate profiles for student project demo
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 2. searches: Records each distinct search submitted by a user
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS searches (
    search_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    skill_query VARCHAR(500) NULL,
    location VARCHAR(150) NULL,
    remote_only BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    INDEX idx_searches_user (user_id),
    INDEX idx_searches_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 3. jobs: Canonical repository of normalized job listings from external APIs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    job_id INT AUTO_INCREMENT PRIMARY KEY,
    external_job_id VARCHAR(150) NOT NULL UNIQUE,
    title VARCHAR(255) NOT NULL,
    company VARCHAR(255) NULL,
    location VARCHAR(255) NULL,
    remote BOOLEAN DEFAULT FALSE,
    category VARCHAR(100) NULL,
    salary VARCHAR(255) NULL,
    url TEXT NULL,
    description MEDIUMTEXT NULL,
    posted_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_jobs_company (company),
    INDEX idx_jobs_location (location),
    INDEX idx_jobs_remote (remote),
    INDEX idx_jobs_posted (posted_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 4. skills: Master list of distinct skills/tags recognized across job listings
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skills (
    skill_id INT AUTO_INCREMENT PRIMARY KEY,
    skill_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_skills_name (skill_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 5. job_skills: Many-to-many association between jobs and detected skills
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_skills (
    job_skill_id INT AUTO_INCREMENT PRIMARY KEY,
    job_id INT NOT NULL,
    skill_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_job_skill (job_id, skill_id),
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(skill_id) ON DELETE CASCADE,
    INDEX idx_job_skills_job (job_id),
    INDEX idx_job_skills_skill (skill_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 6. search_results: Preserves ranked job listings linked to a specific search
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS search_results (
    search_result_id INT AUTO_INCREMENT PRIMARY KEY,
    search_id INT NOT NULL,
    job_id INT NOT NULL,
    relevance_score DECIMAL(6,2) NOT NULL,
    rank_position INT NOT NULL,
    UNIQUE KEY uq_search_job (search_id, job_id),
    FOREIGN KEY (search_id) REFERENCES searches(search_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    INDEX idx_search_results_search (search_id),
    INDEX idx_search_results_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- -----------------------------------------------------------------------------
-- 7. saved_jobs: Persistent user bookmarks for favorited job opportunities
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS saved_jobs (
    saved_job_id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    job_id INT NOT NULL,
    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uq_user_job_saved (user_id, job_id),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE,
    INDEX idx_saved_jobs_user (user_id),
    INDEX idx_saved_jobs_job (job_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
