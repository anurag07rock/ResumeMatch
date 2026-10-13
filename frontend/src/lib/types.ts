/**
 * ResumeMatch — TypeScript Type Contracts
 * Strictly mirrors backend Pydantic v2 models (contract parity).
 * Canonical fields: skills_breakdown, experience_breakdown, education_breakdown, explanation.
 */

export interface ApiErrorDetail {
  field?: string;
  issue: string;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message: string;
    details?: ApiErrorDetail[];
  };
  timestamp?: string;
  request_id?: string;
}

// ==========================================
// Authentication Types
// ==========================================

export interface UserResponse {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in?: number | null;
  user?: UserResponse;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name?: string;
}

// ==========================================
// Resume Types
// ==========================================

export interface ResumeParsedData {
  skills: string[];
  experience_years: number;
  education_level: string;
  education_details?: string | null;
  sections_detected: string[];
  candidate_name?: string | null;
}

export interface ResumeUploadResponse {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  parsed_data?: Record<string, unknown>;
  skills_breakdown: Record<string, unknown>;
  experience_breakdown: Record<string, unknown>;
  education_breakdown: Record<string, unknown>;
  explanation: Record<string, unknown>;
  created_at: string;
}

export interface ResumeResponse {
  id: string;
  user_id?: string | null;
  original_filename: string;
  file_size_bytes: number;
  parsed_text?: string | null;
  structured_data: Record<string, unknown>;
  skills_breakdown: Record<string, unknown>;
  experience_breakdown: Record<string, unknown>;
  education_breakdown: Record<string, unknown>;
  explanation: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

export interface ResumeSummary {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  created_at: string;
  skills_count: number;
  experience_years?: number;
  education_level?: string;
}

export interface ResumeDetail {
  id: string;
  original_filename: string;
  file_size_bytes: number;
  parsed_data: ResumeParsedData;
  created_at: string;
}

// ==========================================
// Job Types
// ==========================================

export interface JobStructuredRequirements {
  required_skills: string[];
  preferred_skills: string[];
  minimum_experience_years?: number | null;
  minimum_education_level?: string | null;
}

export interface JobResponse {
  id: string;
  user_id?: string | null;
  title: string;
  company?: string | null;
  raw_text?: string | null;
  structured_data: Record<string, unknown>;
  structured_requirements?: JobStructuredRequirements | null;
  skills_breakdown: Record<string, unknown>;
  experience_breakdown: Record<string, unknown>;
  education_breakdown: Record<string, unknown>;
  explanation: Record<string, unknown>;
  created_at: string;
}

export interface JobSummary {
  id: string;
  title: string;
  company?: string | null;
  created_at: string;
  required_skills_count: number;
}

export interface JobDetail {
  id: string;
  title: string;
  company?: string | null;
  raw_text: string;
  structured_requirements: JobStructuredRequirements;
  created_at: string;
}

export interface JobCreateRequest {
  title: string;
  company?: string;
  raw_text: string;
}

// ==========================================
// Matching & Explainability Types
// ==========================================

export interface SkillsBreakdown {
  matched_required: string[];
  matched_preferred: string[];
  missing_critical: string[];
  missing_preferred: string[];
  match_rate_required?: number;
  match_rate_preferred?: number;
  coverage_percentage?: number;
}

export interface ExperienceBreakdown {
  candidate_years: number;
  required_years: number;
  delta_years?: number;
  ratio?: number;
  status: "MEETS_REQUIREMENT" | "EXCEEDS_REQUIREMENT" | "BELOW_REQUIREMENT" | "INSUFFICIENT" | string;
}

export interface EducationBreakdown {
  candidate_level: string;
  required_level: string;
  candidate_rank?: number;
  required_rank?: number;
  status: "FULLY_ALIGNED" | "MEETS_OR_EXCEEDS" | "BELOW_REQUIREMENT" | "NOT_SPECIFIED" | string;
}

export interface ExplanationDetails {
  summary: string;
  key_strengths?: string[];
  strengths?: string[];
  growth_areas?: string[];
  gaps?: string[];
  recommendations: string[];
}

export interface MatchSubScores {
  semantic_score: number;
  skills_score: number;
  experience_score: number;
  education_score: number;
}

export interface MatchScoreWeights {
  semantic: number;
  skills: number;
  experience: number;
  education: number;
}

export interface MatchResponse {
  id?: string;
  match_id?: string;
  resume_id?: string;
  job_id?: string;
  overall_score: number;
  final_score?: number;
  fit_category?: "STRONG_MATCH" | "GOOD_MATCH" | "MODERATE_MATCH" | "WEAK_MATCH" | string;
  semantic_score: number;
  skills_score: number;
  experience_score: number;
  education_score: number;
  sub_scores?: MatchSubScores;
  score_weights?: MatchScoreWeights;
  skills_breakdown: SkillsBreakdown;
  experience_breakdown: ExperienceBreakdown;
  education_breakdown: EducationBreakdown;
  explanation: ExplanationDetails;
  created_at?: string;
}

export interface MatchRequest {
  resume_id: string;
  job_id?: string;
  job_text?: string;
  job_title?: string;
  save_result?: boolean;
}

export interface MatchHistoryItem {
  id: string;
  resume_id: string;
  job_id: string;
  overall_score: number;
  fit_category: string;
  created_at: string;
  resume_name?: string;
  job_title?: string;
}
