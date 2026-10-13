"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Badge } from "../../../components/ui/badge";
import { EmptyState } from "../../../components/ui/empty-state";
import { ErrorAlert } from "../../../components/ui/error-alert";
import { LoadingSpinner } from "../../../components/ui/loading-spinner";
import {
  IconSparkles,
  IconShieldCheck,
  IconFileText,
  IconBriefcase,
  IconCheckCircle,
  IconAlertTriangle,
  IconTrash,
  IconEye,
  IconX,
  IconArrowRight,
} from "../../../components/ui/icons";
import {
  MatchResponse,
  ResumeResponse,
  JobResponse,
} from "../../../lib/types";

export default function MatchesPage() {
  // Option selection state
  const [resumes, setResumes] = useState<ResumeResponse[]>([]);
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [isLoadingOptions, setIsLoadingOptions] = useState<boolean>(true);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [selectedResumeId, setSelectedResumeId] = useState<string>("");
  const [selectedJobId, setSelectedJobId] = useState<string>("");

  // Matching execution state
  const [isMatching, setIsMatching] = useState<boolean>(false);
  const [matchError, setMatchError] = useState<{
    code?: string;
    message: string;
    details?: Array<{ field?: string; issue: string }>;
  } | null>(null);
  const [activeMatch, setActiveMatch] = useState<MatchResponse | null>(null);

  // History state
  const [history, setHistory] = useState<MatchResponse[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState<boolean>(true);
  const [historyError, setHistoryError] = useState<string | null>(null);

  // Detail Modal state
  const [viewingMatch, setViewingMatch] = useState<MatchResponse | null>(null);

  // Delete Confirmation state
  const [deletingMatch, setDeletingMatch] = useState<MatchResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteSuccess, setDeleteSuccess] = useState<string | null>(null);

  // Load resumes and jobs on mount
  useEffect(() => {
    let isMounted = true;

    async function loadSelectOptions() {
      setIsLoadingOptions(true);
      setOptionsError(null);
      try {
        const [resumesRes, jobsRes] = await Promise.all([
          fetch("/api/resumes?skip=0&limit=100", {
            method: "GET",
            headers: { "Cache-Control": "no-store" },
          }),
          fetch("/api/jobs?skip=0&limit=100", {
            method: "GET",
            headers: { "Cache-Control": "no-store" },
          }),
        ]);

        if (!isMounted) return;

        if (resumesRes.ok) {
          const resumesData = await resumesRes.json();
          if (Array.isArray(resumesData)) {
            setResumes(resumesData);
            if (resumesData.length > 0) {
              setSelectedResumeId((prev) => prev || resumesData[0].id);
            }
          }
        } else {
          const err = await resumesRes.json().catch(() => ({}));
          setOptionsError(err?.error?.message || "Failed to load candidate resumes");
        }

        if (jobsRes.ok) {
          const jobsData = await jobsRes.json();
          if (Array.isArray(jobsData)) {
            setJobs(jobsData);
            if (jobsData.length > 0) {
              setSelectedJobId((prev) => prev || jobsData[0].id);
            }
          }
        } else {
          const err = await jobsRes.json().catch(() => ({}));
          setOptionsError((prev) =>
            prev ? `${prev} & ${err?.error?.message || "Failed to load job listings"}` : (err?.error?.message || "Failed to load job listings")
          );
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Error loading matching options";
        setOptionsError(msg);
      } finally {
        if (isMounted) {
          setIsLoadingOptions(false);
        }
      }
    }

    loadSelectOptions();

    return () => {
      isMounted = false;
    };
  }, []);

  // Load match history
  const loadHistory = async () => {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const res = await fetch("/api/match/history?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `Failed to load match history (HTTP ${res.status})`);
      }

      const data = await res.json();
      if (Array.isArray(data)) {
        setHistory(data);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error retrieving match history";
      setHistoryError(msg);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    async function fetchInitialHistory() {
      setIsLoadingHistory(true);
      setHistoryError(null);
      try {
        const res = await fetch("/api/match/history?skip=0&limit=50", {
          method: "GET",
          headers: { "Cache-Control": "no-store" },
        });

        if (!isMounted) return;

        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err?.error?.message || `Failed to load match history (HTTP ${res.status})`);
        }

        const data = await res.json();
        if (isMounted && Array.isArray(data)) {
          setHistory(data);
        }
      } catch (err: unknown) {
        if (!isMounted) return;
        const msg = err instanceof Error ? err.message : "Error retrieving match history";
        setHistoryError(msg);
      } finally {
        if (isMounted) {
          setIsLoadingHistory(false);
        }
      }
    }

    fetchInitialHistory();

    return () => {
      isMounted = false;
    };
  }, []);

  // Handle Match Execution
  const handleExecuteMatch = async () => {
    if (!selectedResumeId || !selectedJobId) return;

    setIsMatching(true);
    setMatchError(null);

    try {
      const res = await fetch("/api/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resume_id: selectedResumeId,
          job_id: selectedJobId,
          save_result: true,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setMatchError({
          code: data?.error?.code || `HTTP_${res.status}`,
          message: data?.error?.message || "Scoring evaluation failed. Please verify resume and job inputs.",
          details: data?.error?.details,
        });
        return;
      }

      setActiveMatch(data);
      loadHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unexpected network error during match execution";
      setMatchError({
        code: "NETWORK_ERROR",
        message: msg,
      });
    } finally {
      setIsMatching(false);
    }
  };

  // Handle Match Deletion
  const handleDeleteMatch = async () => {
    if (!deletingMatch) return;
    const matchId = deletingMatch.match_id || deletingMatch.id;
    if (!matchId) return;

    setIsDeleting(true);
    setDeleteError(null);

    try {
      const res = await fetch(`/api/match/${matchId}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err?.error?.message || `Deletion failed with status ${res.status}`);
      }

      setDeleteSuccess("Match evaluation record permanently deleted.");
      if (activeMatch && (activeMatch.match_id === matchId || activeMatch.id === matchId)) {
        setActiveMatch(null);
      }
      setDeletingMatch(null);
      await loadHistory();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete match record";
      setDeleteError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  const getFitBadgeVariant = (category?: string) => {
    switch (category) {
      case "STRONG_MATCH":
        return "success";
      case "GOOD_MATCH":
        return "indigo";
      case "MODERATE_MATCH":
        return "warning";
      case "LOW_MATCH":
      case "WEAK_MATCH":
      case "NO_MATCH":
        return "danger";
      default:
        return "default";
    }
  };

  const getFitBadgeLabel = (category?: string) => {
    switch (category) {
      case "STRONG_MATCH":
        return "Strong Fit";
      case "GOOD_MATCH":
        return "Good Fit";
      case "MODERATE_MATCH":
        return "Moderate Fit";
      case "LOW_MATCH":
        return "Low Fit";
      case "WEAK_MATCH":
        return "Weak Fit";
      case "NO_MATCH":
        return "No Match";
      default:
        return category || "Evaluated";
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Real-Time Matching & Explainable Diagnostics
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Multi-dimensional neural scoring combining dense embeddings, deterministic ontology intersection, and verified gap attribution.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="success" size="md">
            Zero Black-Box Scoring
          </Badge>
          <Badge variant="default" size="md">
            Deterministic Weights
          </Badge>
        </div>
      </div>

      {/* Global Alerts */}
      {deleteSuccess && (
        <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-950/20 px-4 py-3 text-sm text-emerald-400">
          <div className="flex items-center gap-2">
            <IconCheckCircle size={16} />
            <span>{deleteSuccess}</span>
          </div>
          <button
            onClick={() => setDeleteSuccess(null)}
            className="text-slate-400 hover:text-white"
            aria-label="Dismiss message"
          >
            <IconX size={16} />
          </button>
        </div>
      )}

      {optionsError && (
        <ErrorAlert
          title="Data Ingestion Notice"
          message={optionsError}
        />
      )}

      {/* Scoring Architecture Callout */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-sky-500/20 bg-sky-950/20 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-sky-300">
              Semantic Similarity
            </span>
            <Badge variant="default" size="sm">
              50%
            </Badge>
          </div>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            Cosine distance over 384-d sliding window pooled embeddings. Captures implicit contextual role alignment.
          </p>
        </div>

        <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-indigo-300">
              Skills Alignment
            </span>
            <Badge variant="indigo" size="sm">
              30%
            </Badge>
          </div>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            Deterministic taxonomy intersection. Matched required, matched preferred, and missing critical skill badges.
          </p>
        </div>

        <div className="rounded-xl border border-amber-500/20 bg-amber-950/20 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-300">
              Experience Duration
            </span>
            <Badge variant="warning" size="sm">
              10%
            </Badge>
          </div>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            Ratio of candidate verified years vs minimum job requirements. Capped at 1.0 with graceful penalty curves.
          </p>
        </div>

        <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-300">
              Education Level
            </span>
            <Badge variant="success" size="sm">
              10%
            </Badge>
          </div>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            Hierarchical ordinal credentials (Bachelor&apos;s, Master&apos;s, PhD). Verifies degree tier alignment.
          </p>
        </div>
      </div>

      {/* Match Trigger Pane */}
      <Card>
        <CardHeader>
          <CardTitle>Execute New Match</CardTitle>
          <CardDescription>
            Select an uploaded resume and an analyzed job description to execute calibrated hybrid scoring
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingOptions ? (
            <div className="flex items-center justify-center py-8">
              <LoadingSpinner size="md" />
              <span className="ml-3 text-sm text-slate-400">Loading candidate resumes and job listings...</span>
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                {/* Resume Selector */}
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <label
                      htmlFor="resume-select"
                      className="text-xs font-semibold text-slate-300 flex items-center gap-2"
                    >
                      <IconFileText size={16} className="text-sky-400" />
                      <span>Candidate Resume</span>
                    </label>
                    <span className="text-xs text-slate-500">
                      {resumes.length} available
                    </span>
                  </div>

                  {resumes.length === 0 ? (
                    <div className="p-4 rounded-md border border-dashed border-slate-800 text-center">
                      <p className="text-xs text-slate-400">No parsed resumes found in library.</p>
                      <Link
                        href="/resumes"
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-sky-400 hover:text-sky-300"
                      >
                        Upload a resume <IconArrowRight size={12} />
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <select
                        id="resume-select"
                        value={selectedResumeId}
                        onChange={(e) => setSelectedResumeId(e.target.value)}
                        className="w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-white focus:border-sky-500 focus:outline-none"
                      >
                        {resumes.map((r) => {
                          const skillsCount = Array.isArray(r.structured_data?.skills)
                            ? (r.structured_data.skills as unknown[]).length
                            : 0;
                          const expYears = typeof r.structured_data?.experience_years === "number"
                            ? r.structured_data.experience_years
                            : 0;
                          return (
                            <option key={r.id} value={r.id}>
                              {r.original_filename} ({skillsCount} skills, {expYears} yrs)
                            </option>
                          );
                        })}
                      </select>
                      {selectedResumeId && (
                        <div className="text-xs text-slate-500">
                          ID: <span className="font-mono text-slate-400">{selectedResumeId}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Job Selector */}
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <label
                      htmlFor="job-select"
                      className="text-xs font-semibold text-slate-300 flex items-center gap-2"
                    >
                      <IconBriefcase size={16} className="text-indigo-400" />
                      <span>Analyzed Job Listing</span>
                    </label>
                    <span className="text-xs text-slate-500">
                      {jobs.length} available
                    </span>
                  </div>

                  {jobs.length === 0 ? (
                    <div className="p-4 rounded-md border border-dashed border-slate-800 text-center">
                      <p className="text-xs text-slate-400">No analyzed job descriptions found.</p>
                      <Link
                        href="/jobs"
                        className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300"
                      >
                        Analyze a job description <IconArrowRight size={12} />
                      </Link>
                    </div>
                  ) : (
                    <div className="space-y-2">
                      <select
                        id="job-select"
                        value={selectedJobId}
                        onChange={(e) => setSelectedJobId(e.target.value)}
                        className="w-full rounded-md border border-slate-800 bg-slate-900 px-3 py-2 text-sm text-white focus:border-indigo-500 focus:outline-none"
                      >
                        {jobs.map((j) => (
                          <option key={j.id} value={j.id}>
                            {j.title} {j.company ? `— ${j.company}` : ""} ({j.structured_requirements?.required_skills?.length ?? 0} req skills)
                          </option>
                        ))}
                      </select>
                      {selectedJobId && (
                        <div className="text-xs text-slate-500">
                          ID: <span className="font-mono text-slate-400">{selectedJobId}</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {matchError && (
                <ErrorAlert
                  title={`Evaluation Failed (${matchError.code || "MATCH_ERROR"})`}
                  message={matchError.message}
                  details={matchError.details}
                />
              )}

              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-slate-800/60 pt-4">
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <IconShieldCheck size={14} className="text-emerald-400" />
                  <span>Canonical output: skills, experience, education, and verifiable recommendations</span>
                </div>
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={isMatching ? <LoadingSpinner size="sm" /> : <IconSparkles size={16} />}
                  onClick={handleExecuteMatch}
                  disabled={isMatching || !selectedResumeId || !selectedJobId}
                >
                  {isMatching ? "Calculating Score Breakdown..." : "Run Match Evaluation"}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Active Match Breakdown View */}
      {activeMatch && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-white flex items-center gap-2">
              <IconSparkles className="text-amber-400" size={20} />
              Evaluation Results & Explainable Attribution
            </h3>
            <Badge variant="default" size="sm">
              Live Evaluation
            </Badge>
          </div>

          <MatchDetailCard match={activeMatch} />
        </div>
      )}

      {/* Match History Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Historical Match Evaluations</CardTitle>
              <CardDescription>
                Chronological evaluations and canonical breakdown diagnostic records
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadHistory}
              disabled={isLoadingHistory}
            >
              {isLoadingHistory ? "Refreshing..." : "Refresh History"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {historyError && (
            <div className="mb-4">
              <ErrorAlert
                title="Failed to Load History"
                message={historyError}
              />
            </div>
          )}

          {isLoadingHistory ? (
            <div className="flex items-center justify-center py-12">
              <LoadingSpinner size="md" />
              <span className="ml-3 text-sm text-slate-400">Loading evaluation records...</span>
            </div>
          ) : history.length === 0 ? (
            <EmptyState
              icon={<IconSparkles size={24} className="text-slate-500" />}
              title="No evaluation history found"
              description="Execute your first match evaluation above to inspect overall compatibility percentage, fit category, and detailed attribution."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-400 bg-slate-900/50">
                  <tr>
                    <th className="py-3 px-4">Evaluation ID & Date</th>
                    <th className="py-3 px-4">Composite Score</th>
                    <th className="py-3 px-4">Fit Category</th>
                    <th className="py-3 px-4">Component Contributions</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {history.map((m) => {
                    const matchId = m.match_id || m.id || "transient";
                    const score = m.overall_score ?? m.final_score ?? 0;
                    return (
                      <tr key={matchId} className="hover:bg-slate-900/30 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-mono text-xs text-slate-400">
                            {matchId.slice(0, 8)}...
                          </div>
                          <div className="text-xs text-slate-500 mt-0.5">
                            {m.created_at
                              ? new Date(m.created_at).toLocaleString()
                              : "Recently evaluated"}
                          </div>
                        </td>
                        <td className="py-3 px-4">
                          <span className="text-base font-bold text-white">
                            {score.toFixed(1)}%
                          </span>
                        </td>
                        <td className="py-3 px-4">
                          <Badge variant={getFitBadgeVariant(m.fit_category)} size="sm">
                            {getFitBadgeLabel(m.fit_category)}
                          </Badge>
                        </td>
                        <td className="py-3 px-4 text-xs text-slate-400">
                          <div className="flex items-center gap-3">
                            <span title="Semantic similarity (50%)">
                              Sem: <span className="text-slate-200">{m.semantic_score?.toFixed(0)}%</span>
                            </span>
                            <span title="Skills alignment (30%)">
                              Skills: <span className="text-slate-200">{m.skills_score?.toFixed(0)}%</span>
                            </span>
                            <span title="Experience duration (10%)">
                              Exp: <span className="text-slate-200">{m.experience_score?.toFixed(0)}%</span>
                            </span>
                            <span title="Education hierarchy (10%)">
                              Edu: <span className="text-slate-200">{m.education_score?.toFixed(0)}%</span>
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              leftIcon={<IconEye size={14} />}
                              onClick={() => setViewingMatch(m)}
                            >
                              Inspect
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-rose-400 hover:text-rose-300 hover:bg-rose-950/20"
                              leftIcon={<IconTrash size={14} />}
                              onClick={() => setDeletingMatch(m)}
                            >
                              Delete
                            </Button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Match Detail Modal */}
      {viewingMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto">
          <div className="relative w-full max-w-4xl max-h-[90vh] overflow-y-auto rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div>
                <h3 className="text-lg font-bold text-white">
                  Match Diagnostic Breakdown
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  ID: <span className="font-mono">{viewingMatch.match_id || viewingMatch.id}</span> • Evaluated:{" "}
                  {viewingMatch.created_at
                    ? new Date(viewingMatch.created_at).toLocaleString()
                    : "Timestamp recorded"}
                </p>
              </div>
              <button
                onClick={() => setViewingMatch(null)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white"
                aria-label="Close dialog"
              >
                <IconX size={20} />
              </button>
            </div>

            <div className="mt-6">
              <MatchDetailCard match={viewingMatch} />
            </div>

            <div className="mt-6 flex justify-end pt-4 border-t border-slate-800">
              <Button
                variant="outline"
                size="md"
                onClick={() => setViewingMatch(null)}
              >
                Close Breakdown
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingMatch && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="relative w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center gap-3 text-rose-400">
              <IconAlertTriangle size={24} />
              <h3 className="text-lg font-bold text-white">Delete Match Evaluation</h3>
            </div>
            <p className="mt-3 text-sm text-slate-300">
              Are you sure you want to permanently delete match evaluation{" "}
              <span className="font-mono text-slate-200">
                {(deletingMatch.match_id || deletingMatch.id || "").slice(0, 8)}...
              </span>
              ? This action complies with GDPR hard deletion rules and cannot be undone.
            </p>

            {deleteError && (
              <div className="mt-4">
                <ErrorAlert title="Delete Failed" message={deleteError} />
              </div>
            )}

            <div className="mt-6 flex items-center justify-end gap-3">
              <Button
                variant="outline"
                size="md"
                onClick={() => {
                  setDeletingMatch(null);
                  setDeleteError(null);
                }}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="md"
                leftIcon={isDeleting ? <LoadingSpinner size="sm" /> : <IconTrash size={16} />}
                onClick={handleDeleteMatch}
                disabled={isDeleting}
              >
                {isDeleting ? "Deleting..." : "Permanently Delete"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Reusable Match Breakdown & Diagnostics Card
// ---------------------------------------------------------------------------
interface MatchDetailCardProps {
  match: MatchResponse;
}

function MatchDetailCard({ match }: MatchDetailCardProps) {
  const overallScore = match.overall_score ?? match.final_score ?? 0;

  const weights = match.score_weights || {
    semantic: 0.50,
    skills: 0.30,
    experience: 0.10,
    education: 0.10,
  };

  const getFitBadgeVariant = (category?: string) => {
    switch (category) {
      case "STRONG_MATCH":
        return "success";
      case "GOOD_MATCH":
        return "indigo";
      case "MODERATE_MATCH":
        return "warning";
      case "LOW_MATCH":
      case "WEAK_MATCH":
      case "NO_MATCH":
        return "danger";
      default:
        return "default";
    }
  };

  const getFitBadgeLabel = (category?: string) => {
    switch (category) {
      case "STRONG_MATCH":
        return "Strong Fit";
      case "GOOD_MATCH":
        return "Good Fit";
      case "MODERATE_MATCH":
        return "Moderate Fit";
      case "LOW_MATCH":
        return "Low Fit";
      case "WEAK_MATCH":
        return "Weak Fit";
      case "NO_MATCH":
        return "No Match";
      default:
        return category || "Evaluated";
    }
  };

  const skillsBd = match.skills_breakdown || {
    matched_required: [],
    matched_preferred: [],
    missing_critical: [],
    missing_preferred: [],
  };

  const expBd = match.experience_breakdown || {
    candidate_years: 0,
    required_years: 0,
    delta_years: 0,
    status: "NOT_SPECIFIED",
  };

  const eduBd = match.education_breakdown || {
    candidate_level: "Unspecified",
    required_level: "Unspecified",
    status: "NOT_SPECIFIED",
  };

  const expl = match.explanation || {
    summary: "No narrative generated for this evaluation.",
    key_strengths: [],
    strengths: [],
    growth_areas: [],
    gaps: [],
    recommendations: [],
  };

  const keyStrengths = expl.key_strengths || expl.strengths || [];
  const growthAreas = expl.growth_areas || expl.gaps || [];
  const recommendations = expl.recommendations || [];

  return (
    <div className="space-y-6">
      {/* Top Banner: Composite Score & Categorization */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-6 flex flex-col justify-center items-center text-center">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Overall Match Score
          </span>
          <div className="mt-2 text-4xl font-extrabold tracking-tight text-white">
            {overallScore.toFixed(1)}
            <span className="text-xl font-normal text-slate-400"> / 100</span>
          </div>
          <div className="mt-3">
            <Badge variant={getFitBadgeVariant(match.fit_category)} size="md">
              {getFitBadgeLabel(match.fit_category)}
            </Badge>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">
            Calibrated weighted composite score
          </p>
        </div>

        <div className="md:col-span-2 rounded-xl border border-slate-800 bg-slate-950/70 p-6">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300 mb-4">
            Component Contributions & Canonical Weights
          </h4>
          <div className="space-y-3">
            {/* Semantic */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-sky-400" />
                  Semantic Similarity ({Math.round(weights.semantic * 100)}% weight)
                </span>
                <span className="font-semibold text-white">
                  {match.semantic_score?.toFixed(1)} / 100{" "}
                  <span className="text-slate-500 font-normal">
                    (+{(match.semantic_score * weights.semantic).toFixed(1)} pts)
                  </span>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-sky-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, match.semantic_score || 0))}%` }}
                />
              </div>
            </div>

            {/* Skills */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-indigo-400" />
                  Skills Alignment ({Math.round(weights.skills * 100)}% weight)
                </span>
                <span className="font-semibold text-white">
                  {match.skills_score?.toFixed(1)} / 100{" "}
                  <span className="text-slate-500 font-normal">
                    (+{(match.skills_score * weights.skills).toFixed(1)} pts)
                  </span>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-indigo-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, match.skills_score || 0))}%` }}
                />
              </div>
            </div>

            {/* Experience */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-amber-400" />
                  Experience Duration ({Math.round(weights.experience * 100)}% weight)
                </span>
                <span className="font-semibold text-white">
                  {match.experience_score?.toFixed(1)} / 100{" "}
                  <span className="text-slate-500 font-normal">
                    (+{(match.experience_score * weights.experience).toFixed(1)} pts)
                  </span>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-amber-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, match.experience_score || 0))}%` }}
                />
              </div>
            </div>

            {/* Education */}
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-slate-300 flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full bg-emerald-400" />
                  Education Level ({Math.round(weights.education * 100)}% weight)
                </span>
                <span className="font-semibold text-white">
                  {match.education_score?.toFixed(1)} / 100{" "}
                  <span className="text-slate-500 font-normal">
                    (+{(match.education_score * weights.education).toFixed(1)} pts)
                  </span>
                </span>
              </div>
              <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                <div
                  className="h-full bg-emerald-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, match.education_score || 0))}%` }}
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Skill Gaps & Attribution Matrix */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h4 className="text-sm font-bold text-white">
              Skills Alignment Breakdown
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Deterministic skill ontology matches and unmet job criteria
            </p>
          </div>
          <Badge variant="indigo" size="sm">
            Deterministic Extraction
          </Badge>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {/* Matched Required */}
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-950/10 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-emerald-300">
                Matched Required Skills ({skillsBd.matched_required?.length ?? 0})
              </span>
              <IconCheckCircle size={14} className="text-emerald-400" />
            </div>
            {skillsBd.matched_required && skillsBd.matched_required.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {skillsBd.matched_required.map((skill) => (
                  <Badge key={skill} variant="success" size="sm">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No required skills matched</p>
            )}
          </div>

          {/* Matched Preferred */}
          <div className="rounded-lg border border-sky-500/20 bg-sky-950/10 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-sky-300">
                Matched Preferred Skills ({skillsBd.matched_preferred?.length ?? 0})
              </span>
              <IconCheckCircle size={14} className="text-sky-400" />
            </div>
            {skillsBd.matched_preferred && skillsBd.matched_preferred.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {skillsBd.matched_preferred.map((skill) => (
                  <Badge key={skill} variant="default" size="sm">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No preferred skills matched</p>
            )}
          </div>

          {/* Missing Critical */}
          <div className="rounded-lg border border-rose-500/20 bg-rose-950/10 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-rose-300">
                Missing Critical Skills ({skillsBd.missing_critical?.length ?? 0})
              </span>
              <IconAlertTriangle size={14} className="text-rose-400" />
            </div>
            {skillsBd.missing_critical && skillsBd.missing_critical.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {skillsBd.missing_critical.map((skill) => (
                  <Badge key={skill} variant="danger" size="sm">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No critical skill gaps identified</p>
            )}
          </div>

          {/* Missing Preferred */}
          <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-amber-300">
                Missing Preferred Skills ({skillsBd.missing_preferred?.length ?? 0})
              </span>
              <IconAlertTriangle size={14} className="text-amber-400" />
            </div>
            {skillsBd.missing_preferred && skillsBd.missing_preferred.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {skillsBd.missing_preferred.map((skill) => (
                  <Badge key={skill} variant="warning" size="sm">
                    {skill}
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No preferred skill gaps identified</p>
            )}
          </div>
        </div>
      </div>

      {/* Experience and Education Diagnostics */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
        {/* Experience Breakdown */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-5">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Experience Duration Alignment
            </h4>
            <Badge variant="warning" size="sm">
              {expBd.status || "Evaluated"}
            </Badge>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Candidate Experience:</span>
              <span className="font-semibold text-white">
                {expBd.candidate_years?.toFixed(1) ?? "0.0"} years
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Job Requirement:</span>
              <span className="font-semibold text-white">
                {expBd.required_years?.toFixed(1) ?? "0.0"} years
              </span>
            </div>
            <div className="flex justify-between pt-1">
              <span className="text-slate-400">Delta:</span>
              <span
                className={`font-semibold ${
                  (expBd.delta_years ?? 0) >= 0 ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {(expBd.delta_years ?? 0) >= 0 ? `+${expBd.delta_years?.toFixed(1)}` : expBd.delta_years?.toFixed(1)} years
              </span>
            </div>
          </div>
        </div>

        {/* Education Breakdown */}
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-5">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
              Education Hierarchy Tier
            </h4>
            <Badge variant="success" size="sm">
              {eduBd.status || "Evaluated"}
            </Badge>
          </div>
          <div className="space-y-2 text-xs">
            <div className="flex justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Candidate Credential:</span>
              <span className="font-semibold text-white">
                {eduBd.candidate_level || "Unspecified"}
              </span>
            </div>
            <div className="flex justify-between border-b border-slate-800/60 pb-2">
              <span className="text-slate-400">Job Requirement:</span>
              <span className="font-semibold text-white">
                {eduBd.required_level || "Unspecified"}
              </span>
            </div>
            <div className="flex justify-between pt-1">
              <span className="text-slate-400">Credential Status:</span>
              <span className="font-semibold text-emerald-400">
                {eduBd.status || "Aligned"}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Explanation Narrative & Recommendations */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-6 space-y-4">
        <div>
          <h4 className="text-sm font-bold text-white">
            Verifiable Explanation & Recommendations
          </h4>
          <p className="mt-1 text-xs text-slate-300 leading-relaxed">
            {expl.summary || "Scoring evaluation completed based on verified profile intersections."}
          </p>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 pt-2 border-t border-slate-800/60">
          {/* Key Strengths */}
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400 block mb-2">
              Verified Strengths ({keyStrengths.length})
            </span>
            {keyStrengths.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-300">
                {keyStrengths.map((str, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <IconCheckCircle size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                    <span>{str}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500 italic">No specific strengths listed</p>
            )}
          </div>

          {/* Growth Areas */}
          <div>
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-400 block mb-2">
              Growth Areas ({growthAreas.length})
            </span>
            {growthAreas.length > 0 ? (
              <ul className="space-y-1.5 text-xs text-slate-300">
                {growthAreas.map((area, idx) => (
                  <li key={idx} className="flex items-start gap-2">
                    <IconAlertTriangle size={14} className="text-amber-400 mt-0.5 shrink-0" />
                    <span>{area}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-slate-500 italic">No critical growth gaps flagged</p>
            )}
          </div>
        </div>

        {/* Actionable Recommendations */}
        {recommendations.length > 0 && (
          <div className="pt-3 border-t border-slate-800/60">
            <span className="text-xs font-semibold uppercase tracking-wider text-sky-400 block mb-2">
              Actionable Recommendations
            </span>
            <ul className="space-y-1.5 text-xs text-slate-300">
              {recommendations.map((rec, idx) => (
                <li key={idx} className="flex items-start gap-2">
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-sky-950 text-[10px] font-bold text-sky-400 border border-sky-800">
                    {idx + 1}
                  </span>
                  <span>{rec}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
