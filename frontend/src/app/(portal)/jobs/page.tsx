"use client";

import React, { useState, useEffect } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Badge } from "../../../components/ui/badge";
import { EmptyState } from "../../../components/ui/empty-state";
import { Input } from "../../../components/ui/input";
import { Textarea } from "../../../components/ui/textarea";
import { ErrorAlert } from "../../../components/ui/error-alert";
import { LoadingSpinner } from "../../../components/ui/loading-spinner";
import {
  IconBriefcase,
  IconSparkles,
  IconTrash,
  IconEye,
  IconX,
  IconCheckCircle,
  IconSearch,
} from "../../../components/ui/icons";
import { JobResponse, JobStructuredRequirements } from "../../../lib/types";

const samplePresets = [
  {
    title: "Senior Backend Engineer",
    company: "CloudScale Systems",
    description:
      "We are seeking a Senior Backend Engineer with 5+ years of experience in Python and FastAPI. Required qualifications include deep expertise in PostgreSQL, relational database schema design, and Docker containerization. Preferred skills include Kubernetes, Redis caching, and AWS cloud architecture. A Bachelor's degree in Computer Science or equivalent engineering experience is required.",
  },
  {
    title: "Machine Learning Engineer",
    company: "NeuralDynamics",
    description:
      "Looking for a Machine Learning Engineer to deploy deep neural NLP models. Must have 3+ years experience in Python, PyTorch, and Hugging Face transformer architectures. Required competencies include vector search embeddings, model optimization, and REST API development. Preferred skills: Docker, Ray Serve, and Kubernetes. Master's degree in CS, Data Science, or AI preferred.",
  },
  {
    title: "Full Stack Developer",
    company: "FinTech Prime",
    description:
      "FinTech Prime is hiring a Full Stack Developer with 4+ years of professional software engineering experience. Core requirements include TypeScript, Next.js, React, Node.js, and SQL database design. Preferred qualifications: Tailwind CSS, Docker, and CI/CD pipelines. Must hold a Bachelor's degree in Computer Science, Software Engineering, or related discipline.",
  },
];

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [isLoadingJobs, setIsLoadingJobs] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Form state
  const [title, setTitle] = useState<string>("");
  const [company, setCompany] = useState<string>("");
  const [rawText, setRawText] = useState<string>("");
  const [fieldErrors, setFieldErrors] = useState<{ title?: string; rawText?: string }>({});
  const [isAnalyzing, setIsAnalyzing] = useState<boolean>(false);
  const [formError, setFormError] = useState<{
    code?: string;
    message: string;
    details?: Array<{ field?: string; issue: string }>;
  } | null>(null);
  const [lastAnalyzedJob, setLastAnalyzedJob] = useState<JobResponse | null>(null);
  const [actionSuccessMessage, setActionSuccessMessage] = useState<string | null>(null);

  // Search filter
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Detail Modal state
  const [viewingJob, setViewingJob] = useState<JobResponse | null>(null);

  // Delete Confirmation state
  const [deletingJob, setDeletingJob] = useState<JobResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);

  // Fetch jobs from server proxy
  const loadJobs = async () => {
    setIsLoadingJobs(true);
    setFetchError(null);
    try {
      const res = await fetch("/api/jobs?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.error?.message || data?.detail || "Failed to load job postings.";
        setFetchError(msg);
        setJobs([]);
      } else {
        setJobs(Array.isArray(data) ? data : []);
      }
    } catch {
      setFetchError("Network connection error while fetching jobs.");
      setJobs([]);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    fetch("/api/jobs?skip=0&limit=50", {
      method: "GET",
      headers: { "Cache-Control": "no-store" },
    })
      .then(async (res) => {
        const data = await res.json();
        return { ok: res.ok, data };
      })
      .then(({ ok, data }) => {
        if (!isMounted) return;
        if (!ok) {
          const msg = data?.error?.message || data?.detail || "Failed to load job postings.";
          setFetchError(msg);
          setJobs([]);
        } else {
          setJobs(Array.isArray(data) ? data : []);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setFetchError("Network connection error while fetching jobs.");
        setJobs([]);
      })
      .finally(() => {
        if (isMounted) setIsLoadingJobs(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Form submission
  const handleAnalyzeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    setActionSuccessMessage(null);

    const errors: { title?: string; rawText?: string } = {};
    if (!title.trim()) {
      errors.title = "Job title is required.";
    }
    if (!rawText.trim()) {
      errors.rawText = "Job description text is required.";
    } else if (rawText.trim().length < 10) {
      errors.rawText = "Job description must be at least 10 characters long.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsAnalyzing(true);

    try {
      const res = await fetch("/api/jobs/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: title.trim(),
          company: company.trim() || undefined,
          raw_text: rawText.trim(),
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setFormError({
          code: data?.error?.code || `HTTP_${res.status}`,
          message: data?.error?.message || data?.detail || "Job analysis failed.",
          details: data?.error?.details,
        });
      } else {
        setLastAnalyzedJob(data);
        setActionSuccessMessage(`Successfully parsed requirements for '${data.title}'.`);
        setTitle("");
        setCompany("");
        setRawText("");
        await loadJobs();
      }
    } catch {
      setFormError({
        code: "NETWORK_ERROR",
        message: "Failed to communicate with job analysis server.",
      });
    } finally {
      setIsAnalyzing(false);
    }
  };

  // Preset selection
  const handleSelectPreset = (preset: (typeof samplePresets)[0]) => {
    setTitle(preset.title);
    setCompany(preset.company);
    setRawText(preset.description);
    setFieldErrors({});
    setFormError(null);
  };

  // Delete Job
  const handleDeleteConfirm = async () => {
    if (!deletingJob) return;

    setIsDeleting(true);
    setActionSuccessMessage(null);

    try {
      const res = await fetch(`/api/jobs/${deletingJob.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const data = await res.json();
        setFormError({
          code: data?.error?.code || `HTTP_${res.status}`,
          message: data?.error?.message || data?.detail || "Failed to delete job.",
        });
      } else {
        setActionSuccessMessage(`Job '${deletingJob.title}' permanently deleted.`);
        if (lastAnalyzedJob?.id === deletingJob.id) {
          setLastAnalyzedJob(null);
        }
        setDeletingJob(null);
        await loadJobs();
      }
    } catch {
      setFormError({
        code: "NETWORK_ERROR",
        message: "Network error occurred during job deletion request.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Structured Requirements Extractor helper
  const getRequirements = (job: JobResponse): JobStructuredRequirements => {
    if (job.structured_requirements) return job.structured_requirements;
    const sd = (job.structured_data || {}) as Record<string, unknown>;
    const sr = (sd.structured_requirements || {}) as Record<string, unknown>;
    return {
      required_skills: Array.isArray(sr.required_skills) ? (sr.required_skills as string[]) : [],
      preferred_skills: Array.isArray(sr.preferred_skills) ? (sr.preferred_skills as string[]) : [],
      minimum_experience_years: typeof sr.minimum_experience_years === "number" ? sr.minimum_experience_years : null,
      minimum_education_level: typeof sr.minimum_education_level === "string" ? sr.minimum_education_level : null,
    };
  };

  // Search filter
  const filteredJobs = jobs.filter((j) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const titleMatch = j.title.toLowerCase().includes(q);
    const companyMatch = Boolean(j.company && j.company.toLowerCase().includes(q));
    const reqs = getRequirements(j);
    const skillMatch =
      reqs.required_skills.some((s) => s.toLowerCase().includes(q)) ||
      reqs.preferred_skills.some((s) => s.toLowerCase().includes(q));
    return titleMatch || companyMatch || skillMatch;
  });

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Job Requirements Analysis
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Parse job descriptions to extract required skills, preferred qualifications, and experience thresholds with boundary-guarded NLP.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="indigo" size="md">
            1,200+ Canonical Skills
          </Badge>
          <Badge variant="success" size="md">
            AI Rate Limited
          </Badge>
        </div>
      </div>

      {/* Global Alerts */}
      {actionSuccessMessage && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-3.5 text-xs text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IconCheckCircle size={16} className="text-emerald-400 shrink-0" />
            <span>{actionSuccessMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionSuccessMessage(null)}
            className="text-emerald-400 hover:text-emerald-200 p-1"
          >
            <IconX size={14} />
          </button>
        </div>
      )}

      {formError && (
        <ErrorAlert
          title="Analysis / Action Error"
          code={formError.code}
          message={formError.message}
          details={formError.details}
          onDismiss={() => setFormError(null)}
        />
      )}

      {/* Preset Pills */}
      <div>
        <p className="text-xs font-semibold text-slate-400 mb-2.5 uppercase tracking-wider">
          Sample Job Presets for Demonstration
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {samplePresets.map((preset, idx) => (
            <div
              key={idx}
              className="group cursor-pointer rounded-lg border border-slate-800 bg-slate-900/60 p-3.5 hover:border-indigo-500/50 hover:bg-slate-900 transition-colors focus-ring"
              tabIndex={0}
              role="button"
              aria-label={`Select preset: ${preset.title}`}
              onClick={() => handleSelectPreset(preset)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  handleSelectPreset(preset);
                }
              }}
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white group-hover:text-indigo-300">
                  {preset.title}
                </span>
                <Badge variant="default" size="sm">
                  Preset
                </Badge>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">{preset.company}</p>
              <p className="text-xs text-slate-400 mt-2 line-clamp-2 leading-relaxed">
                {preset.description}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Job Description Input Form & Requirements Preview */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <form onSubmit={handleAnalyzeSubmit} noValidate>
            <CardHeader>
              <CardTitle>Job Posting Details</CardTitle>
              <CardDescription>
                Enter the target job title and raw posting text for automated NLP extraction
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Input
                  label="Job Title *"
                  placeholder="e.g. Senior Backend Engineer"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  error={fieldErrors.title}
                  disabled={isAnalyzing}
                  required
                />
                <Input
                  label="Company Name (Optional)"
                  placeholder="e.g. Acme Corporation"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  disabled={isAnalyzing}
                />
              </div>

              <div>
                <Textarea
                  label="Raw Job Description Text *"
                  placeholder="Paste the full job posting text here including responsibilities, required qualifications, and preferred tech stack..."
                  rows={8}
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  error={fieldErrors.rawText}
                  disabled={isAnalyzing}
                  required
                />
                <div className="flex justify-between items-center text-[11px] text-slate-500 mt-1">
                  <span>Minimum 10 characters</span>
                  <span>{rawText.length} characters</span>
                </div>
              </div>

              <div className="pt-2 flex items-center justify-between">
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  isLoading={isAnalyzing}
                  disabled={isAnalyzing}
                  leftIcon={<IconSparkles size={16} />}
                >
                  Extract Requirements
                </Button>
                <span className="text-[11px] text-slate-400 font-mono">
                  Endpoint: /jobs/analyze
                </span>
              </div>
            </CardContent>
          </form>
        </Card>

        {/* Requirements Preview Pane */}
        <Card className="flex flex-col">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Extracted Requirements</CardTitle>
              {lastAnalyzedJob && (
                <Badge variant="success" size="sm">
                  Parsed Just Now
                </Badge>
              )}
            </div>
            <CardDescription>
              {lastAnalyzedJob
                ? `Structured extraction for '${lastAnalyzedJob.title}'`
                : "Structured entities extracted via boundary-guarded NLP"}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col justify-center">
            {lastAnalyzedJob ? (
              <div className="space-y-4 text-xs">
                {/* Meta stats */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                    <span className="text-slate-500 block mb-0.5">Experience Minimum</span>
                    <span className="font-semibold text-amber-300">
                      {getRequirements(lastAnalyzedJob).minimum_experience_years !== null
                        ? `${getRequirements(lastAnalyzedJob).minimum_experience_years} yrs`
                        : "Not specified"}
                    </span>
                  </div>
                  <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                    <span className="text-slate-500 block mb-0.5">Education Minimum</span>
                    <span className="font-semibold text-emerald-300">
                      {getRequirements(lastAnalyzedJob).minimum_education_level || "Not specified"}
                    </span>
                  </div>
                </div>

                {/* Required skills */}
                <div className="space-y-1.5">
                  <span className="font-semibold text-indigo-300 block">
                    Required Skills ({getRequirements(lastAnalyzedJob).required_skills.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5 p-3 rounded-lg border border-slate-800 bg-slate-950/60">
                    {getRequirements(lastAnalyzedJob).required_skills.length > 0 ? (
                      getRequirements(lastAnalyzedJob).required_skills.map((s, idx) => (
                        <Badge key={idx} variant="indigo" size="sm" className="font-mono text-xs">
                          {s}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-slate-500">None detected</span>
                    )}
                  </div>
                </div>

                {/* Preferred skills */}
                <div className="space-y-1.5">
                  <span className="font-semibold text-sky-300 block">
                    Preferred Skills ({getRequirements(lastAnalyzedJob).preferred_skills.length})
                  </span>
                  <div className="flex flex-wrap gap-1.5 p-3 rounded-lg border border-slate-800 bg-slate-950/60">
                    {getRequirements(lastAnalyzedJob).preferred_skills.length > 0 ? (
                      getRequirements(lastAnalyzedJob).preferred_skills.map((s, idx) => (
                        <Badge key={idx} variant="default" size="sm" className="font-mono text-xs">
                          {s}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-slate-500">None detected</span>
                    )}
                  </div>
                </div>

                <div className="pt-2 flex justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setViewingJob(lastAnalyzedJob)}
                  >
                    View Full Job Details
                  </Button>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={<IconBriefcase size={24} className="text-slate-500" />}
                title="No job description analyzed yet"
                description="Input a job posting on the left or select a sample preset to view parsed required skills, preferred competencies, and experience thresholds."
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* Analyzed Jobs Library */}
      <div className="space-y-4 pt-4 border-t border-slate-800/80">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="text-lg font-bold text-white">Analyzed Job Postings</h3>
            <p className="text-xs text-slate-400">
              Browse previously indexed jobs available for candidate matching
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-center gap-3">
            <div className="w-full sm:w-64 relative">
              <Input
                placeholder="Filter jobs by title or skill..."
                className="h-9 pl-8"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <div className="absolute left-2.5 top-2.5 text-slate-500 pointer-events-none">
                <IconSearch size={15} />
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadJobs}
              isLoading={isLoadingJobs}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Jobs List Content */}
        {isLoadingJobs ? (
          <Card>
            <CardContent className="p-12 flex justify-center items-center">
              <LoadingSpinner size="lg" label="Loading analyzed job descriptions..." />
            </CardContent>
          </Card>
        ) : fetchError ? (
          <Card>
            <CardContent className="p-8 text-center space-y-4">
              <ErrorAlert title="Failed to Fetch Jobs" message={fetchError} />
              <Button variant="secondary" size="sm" onClick={loadJobs}>
                Retry Fetch
              </Button>
            </CardContent>
          </Card>
        ) : jobs.length === 0 ? (
          <Card>
            <CardContent className="p-6">
              <EmptyState
                icon={<IconBriefcase size={24} className="text-slate-500" />}
                title="No job descriptions analyzed yet"
                description="Your job repository is currently empty. Analyze your first job posting using the form above to begin multi-dimensional matching."
              />
            </CardContent>
          </Card>
        ) : filteredJobs.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-slate-400 text-sm">
              No jobs match &quot;{searchQuery}&quot;. Try adjusting your search query.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredJobs.map((job) => {
              const reqs = getRequirements(job);
              const formattedDate = new Date(job.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              });

              return (
                <Card
                  key={job.id}
                  className="hover:border-slate-700 transition-colors bg-slate-900/60"
                >
                  <CardContent className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <IconBriefcase size={18} className="text-sky-400 shrink-0" />
                        <h4 className="font-semibold text-white text-sm truncate max-w-sm">
                          {job.title}
                        </h4>
                        {job.company && (
                          <Badge variant="default" size="sm">
                            {job.company}
                          </Badge>
                        )}
                        <Badge variant="indigo" size="sm">
                          {formattedDate}
                        </Badge>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 pt-1">
                        <span>
                          <strong className="text-slate-300">Min Exp:</strong>{" "}
                          {reqs.minimum_experience_years !== null
                            ? `${reqs.minimum_experience_years} yrs`
                            : "N/A"}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-slate-300">Min Edu:</strong>{" "}
                          {reqs.minimum_education_level || "N/A"}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-slate-300">Required Skills ({reqs.required_skills.length}):</strong>
                        </span>
                      </div>

                      {/* Required Skills Badges */}
                      {reqs.required_skills.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1.5">
                          {reqs.required_skills.slice(0, 5).map((skill, sIdx) => (
                            <Badge key={sIdx} variant="indigo" size="sm" className="font-mono text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                          {reqs.required_skills.length > 5 && (
                            <span className="text-[11px] text-slate-500 font-medium">
                              +{reqs.required_skills.length - 5} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      <Button
                        variant="secondary"
                        size="sm"
                        leftIcon={<IconEye size={15} />}
                        onClick={() => setViewingJob(job)}
                      >
                        Details
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-slate-400 hover:text-rose-400 hover:bg-rose-950/20"
                        leftIcon={<IconTrash size={15} />}
                        onClick={() => setDeletingJob(job)}
                      >
                        Delete
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Job Details Modal */}
      {viewingJob && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Job Details"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs"
            onClick={() => setViewingJob(null)}
            aria-hidden="true"
          />

          <Card className="relative z-10 w-full max-w-2xl max-h-[85vh] flex flex-col border-slate-700 bg-slate-900 shadow-2xl overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <CardTitle className="text-base truncate max-w-md">
                  {viewingJob.title}
                </CardTitle>
                <CardDescription className="text-xs">
                  {viewingJob.company ? `${viewingJob.company} • ` : ""}
                  ID: <span className="font-mono text-slate-300">{viewingJob.id}</span>
                </CardDescription>
              </div>
              <button
                type="button"
                onClick={() => setViewingJob(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors focus-ring"
                aria-label="Close details"
              >
                <IconX size={20} />
              </button>
            </CardHeader>

            <CardContent className="overflow-y-auto space-y-6 py-5">
              {/* Meta Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Created Date</span>
                  <span className="font-semibold text-slate-200">
                    {new Date(viewingJob.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Experience Threshold</span>
                  <span className="font-semibold text-amber-300">
                    {getRequirements(viewingJob).minimum_experience_years !== null
                      ? `${getRequirements(viewingJob).minimum_experience_years} yrs`
                      : "None"}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Education Credential</span>
                  <span className="font-semibold text-emerald-300">
                    {getRequirements(viewingJob).minimum_education_level || "None"}
                  </span>
                </div>
              </div>

              {/* Required Skills */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-indigo-300 uppercase tracking-wider">
                  Required Technical Skills ({getRequirements(viewingJob).required_skills.length})
                </h4>
                <div className="flex flex-wrap gap-1.5 p-3.5 rounded-lg border border-slate-800 bg-slate-950/60">
                  {getRequirements(viewingJob).required_skills.length > 0 ? (
                    getRequirements(viewingJob).required_skills.map((skill, idx) => (
                      <Badge key={idx} variant="indigo" size="sm" className="font-mono text-xs">
                        {skill}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">
                      No mandatory required skills explicitly specified.
                    </span>
                  )}
                </div>
              </div>

              {/* Preferred Skills */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-sky-300 uppercase tracking-wider">
                  Preferred / Secondary Skills ({getRequirements(viewingJob).preferred_skills.length})
                </h4>
                <div className="flex flex-wrap gap-1.5 p-3.5 rounded-lg border border-slate-800 bg-slate-950/60">
                  {getRequirements(viewingJob).preferred_skills.length > 0 ? (
                    getRequirements(viewingJob).preferred_skills.map((skill, idx) => (
                      <Badge key={idx} variant="default" size="sm" className="font-mono text-xs">
                        {skill}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">
                      No secondary preferred skills specified.
                    </span>
                  )}
                </div>
              </div>

              {/* Raw Job Description Text */}
              {Boolean(viewingJob.raw_text) && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Raw Job Description Text
                  </h4>
                  <div className="max-h-48 overflow-y-auto text-xs text-slate-400 bg-slate-950/60 p-3.5 rounded-lg border border-slate-800 leading-relaxed whitespace-pre-wrap font-sans">
                    {viewingJob.raw_text}
                  </div>
                </div>
              )}
            </CardContent>

            <div className="p-4 border-t border-slate-800 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setViewingJob(null)}>
                Close
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingJob && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm Job Deletion"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs"
            onClick={() => !isDeleting && setDeletingJob(null)}
            aria-hidden="true"
          />

          <Card className="relative z-10 w-full max-w-md border-rose-500/30 bg-slate-900 shadow-2xl">
            <CardHeader>
              <CardTitle className="text-rose-400 flex items-center gap-2">
                <IconTrash size={18} />
                Confirm Job Deletion
              </CardTitle>
              <CardDescription className="text-slate-300 text-xs">
                Are you sure you want to delete <strong className="text-white">&apos;{deletingJob.title}&apos;</strong>?
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-slate-400 leading-relaxed">
                Deleting this job posting will permanently remove its extracted skill requirements, 384-d semantic embedding, and will <strong className="text-rose-300">cascade-delete all associated match evaluations</strong> linked to this job record. This operation cannot be undone.
              </p>
            </CardContent>
            <div className="p-4 border-t border-slate-800 flex items-center justify-end gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeletingJob(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={handleDeleteConfirm}
                isLoading={isDeleting}
                disabled={isDeleting}
              >
                Permanently Delete
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
