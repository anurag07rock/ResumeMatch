"use client";

import React, { useState, useEffect, useCallback } from "react";
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
  IconFileText,
  IconBriefcase,
  IconSparkles,
  IconUpload,
  IconShieldCheck,
  IconArrowRight,
} from "../../../components/ui/icons";
import {
  ResumeResponse,
  JobResponse,
  MatchResponse,
} from "../../../lib/types";
import { useAuth } from "../../../lib/auth-context";

export default function DashboardPage() {
  const { user } = useAuth();

  // Data states
  const [resumes, setResumes] = useState<ResumeResponse[]>([]);
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [matches, setMatches] = useState<MatchResponse[]>([]);

  // Loading & Error states per resource for independent failure handling
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [errors, setErrors] = useState<{
    resumes?: string;
    jobs?: string;
    matches?: string;
  }>({});

  const loadDashboardData = useCallback(async () => {
    setIsLoading(true);
    setErrors({});

    const [resumesResult, jobsResult, matchesResult] = await Promise.allSettled([
      fetch("/api/resumes?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      }),
      fetch("/api/jobs?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      }),
      fetch("/api/match/history?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      }),
    ]);

    const newErrors: { resumes?: string; jobs?: string; matches?: string } = {};

    // 1. Process Resumes
    if (resumesResult.status === "fulfilled") {
      const res = resumesResult.value;
      if (res.ok) {
        const data = await res.json().catch(() => []);
        if (Array.isArray(data)) setResumes(data);
      } else {
        const err = await res.json().catch(() => ({}));
        newErrors.resumes = err?.error?.message || `Failed to load resumes (HTTP ${res.status})`;
      }
    } else {
      newErrors.resumes = "Network failure loading resumes";
    }

    // 2. Process Jobs
    if (jobsResult.status === "fulfilled") {
      const res = jobsResult.value;
      if (res.ok) {
        const data = await res.json().catch(() => []);
        if (Array.isArray(data)) setJobs(data);
      } else {
        const err = await res.json().catch(() => ({}));
        newErrors.jobs = err?.error?.message || `Failed to load job descriptions (HTTP ${res.status})`;
      }
    } else {
      newErrors.jobs = "Network failure loading job descriptions";
    }

    // 3. Process Matches
    if (matchesResult.status === "fulfilled") {
      const res = matchesResult.value;
      if (res.ok) {
        const data = await res.json().catch(() => []);
        if (Array.isArray(data)) setMatches(data);
      } else {
        const err = await res.json().catch(() => ({}));
        newErrors.matches = err?.error?.message || `Failed to load match evaluations (HTTP ${res.status})`;
      }
    } else {
      newErrors.matches = "Network failure loading match evaluations";
    }

    setErrors(newErrors);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function init() {
      if (isMounted) {
        await loadDashboardData();
      }
    }

    init();

    return () => {
      isMounted = false;
    };
  }, [loadDashboardData]);

  // Derived metrics
  const resumeCount = resumes.length;
  const isResumeCapped = resumeCount === 50;

  const jobCount = jobs.length;
  const isJobCapped = jobCount === 50;

  const matchCount = matches.length;
  const isMatchCapped = matchCount === 50;

  const averageCompatibility =
    matchCount > 0
      ? (
          matches.reduce(
            (sum, m) => sum + (m.overall_score ?? m.final_score ?? 0),
            0
          ) / matchCount
        ).toFixed(1)
      : null;

  const recentMatches = matches.slice(0, 5);

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

  const hasAnyErrors = Object.keys(errors).length > 0;

  return (
    <div className="space-y-8">
      {/* Welcome & Quick Action Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Workspace Overview
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Welcome back{user?.full_name ? `, ${user.full_name}` : ""}. Explainable AI matching platform with deterministic taxonomy extraction.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2.5">
          <Link href="/resumes">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<IconUpload size={16} />}
            >
              Upload Resume
            </Button>
          </Link>
          <Link href="/jobs">
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<IconBriefcase size={16} />}
            >
              Add Job
            </Button>
          </Link>
          <Link href="/matches">
            <Button
              variant="primary"
              size="sm"
              leftIcon={<IconSparkles size={16} />}
            >
              New AI Match
            </Button>
          </Link>
        </div>
      </div>

      {/* Partial Errors Banner */}
      {hasAnyErrors && (
        <div className="space-y-2">
          {errors.resumes && (
            <ErrorAlert
              title="Resumes Synchronization Notice"
              message={errors.resumes}
            />
          )}
          {errors.jobs && (
            <ErrorAlert
              title="Jobs Synchronization Notice"
              message={errors.jobs}
            />
          )}
          {errors.matches && (
            <ErrorAlert
              title="Matches Synchronization Notice"
              message={errors.matches}
            />
          )}
          <div className="flex justify-end pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={loadDashboardData}
              disabled={isLoading}
            >
              {isLoading ? "Retrying..." : "Retry Dashboard Sync"}
            </Button>
          </div>
        </div>
      )}

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Resumes */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Resumes Uploaded
            </CardTitle>
            <div className="rounded-md bg-slate-800/80 p-2 text-indigo-400">
              <IconFileText size={18} />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-2">
                <LoadingSpinner size="sm" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold text-white">
                  {resumeCount}
                  {isResumeCapped && <span className="text-sm text-slate-400 font-normal">+</span>}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {isResumeCapped ? "50 records retrieved" : "Stored with 384-d dense vectors"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Jobs */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Jobs Ingested
            </CardTitle>
            <div className="rounded-md bg-slate-800/80 p-2 text-sky-400">
              <IconBriefcase size={18} />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-2">
                <LoadingSpinner size="sm" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold text-white">
                  {jobCount}
                  {isJobCapped && <span className="text-sm text-slate-400 font-normal">+</span>}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {isJobCapped ? "50 records retrieved" : "Extracted required & preferred skills"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Matches */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Match Evaluations
            </CardTitle>
            <div className="rounded-md bg-slate-800/80 p-2 text-indigo-400">
              <IconSparkles size={18} />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-2">
                <LoadingSpinner size="sm" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold text-white">
                  {matchCount}
                  {isMatchCapped && <span className="text-sm text-slate-400 font-normal">+</span>}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {isMatchCapped ? "50 recent evaluations" : "Multi-dimensional hybrid scores"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Average Compatibility */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium text-slate-400">
              Average Compatibility
            </CardTitle>
            <div className="rounded-md bg-slate-800/80 p-2 text-emerald-400">
              <IconShieldCheck size={18} />
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="py-2">
                <LoadingSpinner size="sm" />
              </div>
            ) : (
              <>
                <div className="text-2xl font-bold text-white">
                  {averageCompatibility !== null ? `${averageCompatibility}%` : "--%"}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {averageCompatibility !== null
                    ? `Mean score across ${matchCount} runs`
                    : "Awaiting first evaluation"}
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Recent Activity & Architecture Engine */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column (2 Cols): Recent Matches Feed */}
        <div className="lg:col-span-2">
          <Card className="h-full flex flex-col">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle>Recent Evaluations</CardTitle>
                <CardDescription>
                  Explainable matching records with breakdown diagnostics
                </CardDescription>
              </div>
              <Link
                href="/matches"
                className="text-xs text-indigo-400 hover:text-indigo-300 font-medium inline-flex items-center gap-1 focus-ring rounded"
              >
                View all ({matchCount}) <IconArrowRight size={14} />
              </Link>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col justify-center">
              {isLoading ? (
                <div className="flex items-center justify-center py-12">
                  <LoadingSpinner size="md" />
                  <span className="ml-3 text-sm text-slate-400">
                    Loading recent evaluation records...
                  </span>
                </div>
              ) : recentMatches.length === 0 ? (
                <EmptyState
                  icon={<IconSparkles size={24} className="text-slate-500" />}
                  title="No match evaluations yet"
                  description="Upload a candidate resume PDF and supply a job posting to compute multi-dimensional compatibility."
                  action={
                    <Link href="/matches">
                      <Button size="sm" variant="primary">
                        Execute First Match
                      </Button>
                    </Link>
                  }
                />
              ) : (
                <div className="divide-y divide-slate-800/60 overflow-hidden">
                  {recentMatches.map((m) => {
                    const matchId = m.match_id || m.id || "eval";
                    const score = m.overall_score ?? m.final_score ?? 0;
                    return (
                      <div
                        key={matchId}
                        className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-slate-900/30 -mx-4 px-4 transition-colors rounded-lg"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-xs text-slate-400">
                              {matchId.slice(0, 8)}...
                            </span>
                            <Badge
                              variant={getFitBadgeVariant(m.fit_category)}
                              size="sm"
                            >
                              {getFitBadgeLabel(m.fit_category)}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-3 text-xs text-slate-400">
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
                        </div>

                        <div className="flex items-center gap-3 justify-between sm:justify-end">
                          <span className="text-lg font-bold text-white">
                            {score.toFixed(1)}%
                          </span>
                          <Link href="/matches">
                            <Button variant="ghost" size="sm">
                              Inspect
                            </Button>
                          </Link>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Right Column: AI Architecture Status */}
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Scoring Engine Spec</CardTitle>
                <Badge variant="indigo" size="sm">
                  Active
                </Badge>
              </div>
              <CardDescription>
                Calibrated multi-dimensional weights
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3.5 text-xs">
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-300">Semantic Similarity (Embedding)</span>
                <span className="font-mono font-semibold text-sky-300">50%</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-300">Skills Alignment (Ontology)</span>
                <span className="font-mono font-semibold text-indigo-300">30%</span>
              </div>
              <div className="flex items-center justify-between border-b border-slate-800/60 pb-2">
                <span className="text-slate-300">Experience Timeline</span>
                <span className="font-mono font-semibold text-amber-300">10%</span>
              </div>
              <div className="flex items-center justify-between pb-1">
                <span className="text-slate-300">Education Credentials</span>
                <span className="font-mono font-semibold text-emerald-300">10%</span>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">System Diagnostics</CardTitle>
              <CardDescription>
                Verified AI models & runtime components
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Embedding Model</span>
                <span className="font-mono text-slate-200">all-MiniLM-L6-v2 (384d)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Chunking</span>
                <span className="font-mono text-slate-200">Sliding Window (512 tokens)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Skill Taxonomy</span>
                <span className="font-mono text-slate-200">1,200+ Canonical terms</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-400">Explainability</span>
                <Badge variant="success" size="sm">
                  Zero Fabrication
                </Badge>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
