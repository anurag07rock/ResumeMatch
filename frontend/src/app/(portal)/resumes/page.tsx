"use client";

import React, { useState, useEffect, useRef } from "react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../../components/ui/card";
import { Button } from "../../../components/ui/button";
import { Badge } from "../../../components/ui/badge";
import { EmptyState } from "../../../components/ui/empty-state";
import { Input } from "../../../components/ui/input";
import { ErrorAlert } from "../../../components/ui/error-alert";
import { LoadingSpinner } from "../../../components/ui/loading-spinner";
import {
  IconFileText,
  IconUpload,
  IconShieldCheck,
  IconTrash,
  IconEye,
  IconX,
  IconCheckCircle,
  IconSearch,
} from "../../../components/ui/icons";
import { ResumeResponse } from "../../../lib/types";

const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5 MB

export default function ResumesPage() {
  const [resumes, setResumes] = useState<ResumeResponse[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // File upload state
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<{
    code?: string;
    message: string;
    details?: Array<{ field?: string; issue: string }>;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Search filter
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Detail Modal state
  const [viewingResume, setViewingResume] = useState<ResumeResponse | null>(null);

  // Delete Confirmation state
  const [deletingResume, setDeletingResume] = useState<ResumeResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteFeedback, setDeleteFeedback] = useState<string | null>(null);

  // Fetch resumes from server proxy
  const loadResumes = async () => {
    setIsLoading(true);
    setFetchError(null);
    try {
      const res = await fetch("/api/resumes?skip=0&limit=50", {
        method: "GET",
        headers: { "Cache-Control": "no-store" },
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = data?.error?.message || data?.detail || "Failed to load resumes.";
        setFetchError(msg);
        setResumes([]);
      } else {
        setResumes(Array.isArray(data) ? data : []);
      }
    } catch {
      setFetchError("Network connection error while fetching resume repository.");
      setResumes([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    let isMounted = true;

    fetch("/api/resumes?skip=0&limit=50", {
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
          const msg = data?.error?.message || data?.detail || "Failed to load resumes.";
          setFetchError(msg);
          setResumes([]);
        } else {
          setResumes(Array.isArray(data) ? data : []);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setFetchError("Network connection error while fetching resume repository.");
        setResumes([]);
      })
      .finally(() => {
        if (isMounted) setIsLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  // Handle file selection & client validation
  const handleFileChange = (file: File | null) => {
    setUploadError(null);
    setUploadSuccessMessage(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError({
        code: "INVALID_FILE_TYPE",
        message: "Only PDF documents (.pdf) are supported.",
      });
      setSelectedFile(null);
      return;
    }

    if (file.size === 0) {
      setUploadError({
        code: "EMPTY_FILE",
        message: "The selected file is empty (0 bytes).",
      });
      setSelectedFile(null);
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError({
        code: "PAYLOAD_TOO_LARGE",
        message: `File exceeds the 5 MB limit (${(file.size / (1024 * 1024)).toFixed(2)} MB).`,
      });
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  // Drag and drop event handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  // Submit file upload
  const handleUploadSubmit = async () => {
    if (!selectedFile) return;

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccessMessage(null);

    const formData = new FormData();
    formData.append("file", selectedFile, selectedFile.name);

    try {
      const res = await fetch("/api/resumes/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        setUploadError({
          code: data?.error?.code || `HTTP_${res.status}`,
          message: data?.error?.message || data?.detail || "Upload rejected by the server.",
          details: data?.error?.details,
        });
      } else {
        setUploadSuccessMessage(`Successfully processed and indexed '${data.original_filename}'.`);
        setSelectedFile(null);
        if (fileInputRef.current) {
          fileInputRef.current.value = "";
        }
        await loadResumes();
      }
    } catch {
      setUploadError({
        code: "NETWORK_ERROR",
        message: "Failed to communicate with upload server.",
      });
    } finally {
      setIsUploading(false);
    }
  };

  // Handle resume deletion
  const handleDeleteConfirm = async () => {
    if (!deletingResume) return;

    setIsDeleting(true);
    setDeleteFeedback(null);

    try {
      const res = await fetch(`/api/resumes/${deletingResume.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        const data = await res.json();
        setUploadError({
          code: data?.error?.code || `HTTP_${res.status}`,
          message: data?.error?.message || data?.detail || "Failed to delete resume.",
        });
      } else {
        setDeleteFeedback(`Resume '${deletingResume.original_filename}' permanently deleted.`);
        setDeletingResume(null);
        await loadResumes();
      }
    } catch {
      setUploadError({
        code: "NETWORK_ERROR",
        message: "Network error occurred during deletion request.",
      });
    } finally {
      setIsDeleting(false);
    }
  };

  // Search filter
  const filteredResumes = resumes.filter((r) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    const nameMatch = r.original_filename.toLowerCase().includes(q);
    const sd = (r.structured_data || {}) as Record<string, unknown>;
    const skills = Array.isArray(sd.skills) ? (sd.skills as string[]) : [];
    const skillMatch = skills.some((s) => String(s).toLowerCase().includes(q));
    return nameMatch || skillMatch;
  });

  // Helpers to extract structured fields safely
  const getSkillsList = (r: ResumeResponse): string[] => {
    const sd = (r.structured_data || {}) as Record<string, unknown>;
    if (Array.isArray(sd.skills)) return sd.skills as string[];
    const sb = (r.skills_breakdown || {}) as Record<string, unknown>;
    if (Array.isArray(sb.extracted_skills)) return sb.extracted_skills as string[];
    return [];
  };

  const getExperienceYears = (r: ResumeResponse): string => {
    const sd = (r.structured_data || {}) as Record<string, unknown>;
    if (typeof sd.experience_years === "number") return `${sd.experience_years} yrs`;
    const eb = (r.experience_breakdown || {}) as Record<string, unknown>;
    if (typeof eb.candidate_years === "number") return `${eb.candidate_years} yrs`;
    return "Not specified";
  };

  const getEducationLevel = (r: ResumeResponse): string => {
    const sd = (r.structured_data || {}) as Record<string, unknown>;
    if (typeof sd.education_level === "string") return sd.education_level;
    const edb = (r.education_breakdown || {}) as Record<string, unknown>;
    if (typeof edb.candidate_level === "string") return edb.candidate_level;
    return "Not specified";
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Resume Library
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Upload candidate resumes to extract layout sections, skills, work history, and compute 384-d embeddings.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="indigo" size="md">
            PDF Only (&le; 5 MB)
          </Badge>
          <Badge variant="success" size="md">
            384-d Vectors
          </Badge>
        </div>
      </div>

      {/* Global Alerts */}
      {deleteFeedback && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-3.5 text-xs text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IconCheckCircle size={16} className="text-emerald-400 shrink-0" />
            <span>{deleteFeedback}</span>
          </div>
          <button
            type="button"
            onClick={() => setDeleteFeedback(null)}
            className="text-emerald-400 hover:text-emerald-200 p-1"
          >
            <IconX size={14} />
          </button>
        </div>
      )}

      {uploadSuccessMessage && (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/30 p-3.5 text-xs text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <IconCheckCircle size={16} className="text-emerald-400 shrink-0" />
            <span>{uploadSuccessMessage}</span>
          </div>
          <button
            type="button"
            onClick={() => setUploadSuccessMessage(null)}
            className="text-emerald-400 hover:text-emerald-200 p-1"
          >
            <IconX size={14} />
          </button>
        </div>
      )}

      {uploadError && (
        <ErrorAlert
          title="Upload / Action Error"
          code={uploadError.code}
          message={uploadError.message}
          details={uploadError.details}
          onDismiss={() => setUploadError(null)}
        />
      )}

      {/* Upload Zone */}
      <Card
        className={`border-dashed border-2 transition-colors ${
          isDragging
            ? "border-indigo-500 bg-indigo-950/20"
            : "border-slate-700/80 bg-slate-900/40"
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <CardContent className="p-8 sm:p-10 flex flex-col items-center justify-center text-center">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            className="sr-only"
            id="resume-file-input"
            onChange={(e) => {
              if (e.target.files && e.target.files.length > 0) {
                handleFileChange(e.target.files[0]);
              }
            }}
            disabled={isUploading}
          />

          <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-indigo-600/15 border border-indigo-500/30 text-indigo-400">
            <IconUpload size={26} />
          </div>

          <h3 className="text-base font-semibold text-white">
            Upload Candidate Resume
          </h3>
          <p className="mt-1.5 max-w-md text-xs sm:text-sm text-slate-400">
            Drag and drop a PDF file here, or click to browse. Magic bytes (<code className="text-slate-300 font-mono">%PDF-</code>) and size limits (5 MB) are strictly enforced.
          </p>

          {/* Selected File Feedback */}
          {selectedFile ? (
            <div className="mt-5 w-full max-w-md rounded-lg border border-slate-700 bg-slate-950/80 p-3.5 flex items-center justify-between">
              <div className="flex items-center gap-2.5 min-w-0">
                <IconFileText size={20} className="text-indigo-400 shrink-0" />
                <div className="text-left truncate">
                  <p className="text-xs font-semibold text-slate-200 truncate">
                    {selectedFile.name}
                  </p>
                  <p className="text-[11px] text-slate-400 font-mono">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleUploadSubmit}
                  isLoading={isUploading}
                  disabled={isUploading}
                >
                  Upload & Process
                </Button>
                <button
                  type="button"
                  onClick={() => handleFileChange(null)}
                  disabled={isUploading}
                  className="rounded p-1 text-slate-400 hover:text-rose-400 hover:bg-slate-900 transition-colors"
                  aria-label="Clear selected file"
                >
                  <IconX size={16} />
                </button>
              </div>
            </div>
          ) : (
            <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
              <label htmlFor="resume-file-input">
                <Button
                  variant="primary"
                  size="md"
                  leftIcon={<IconUpload size={16} />}
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                >
                  Select PDF File
                </Button>
              </label>
            </div>
          )}

          <div className="mt-4 flex items-center gap-2 text-[11px] text-slate-400">
            <IconShieldCheck size={14} className="text-emerald-400 shrink-0" />
            <span>GDPR Hard-Delete supported • In-memory PII sanitization enabled</span>
          </div>
        </CardContent>
      </Card>

      {/* Resume Management & Search Pane */}
      <div className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="w-full sm:max-w-xs relative">
            <Input
              placeholder="Filter resumes by name or skill..."
              className="h-9 pl-8"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="absolute left-2.5 top-2.5 text-slate-500 pointer-events-none">
              <IconSearch size={15} />
            </div>
          </div>
          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span>
              Showing {filteredResumes.length} of {resumes.length} resumes
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={loadResumes}
              isLoading={isLoading}
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Content Area */}
        {isLoading ? (
          <Card>
            <CardContent className="p-12 flex justify-center items-center">
              <LoadingSpinner size="lg" label="Loading candidate resumes..." />
            </CardContent>
          </Card>
        ) : fetchError ? (
          <Card>
            <CardContent className="p-8 text-center space-y-4">
              <ErrorAlert title="Failed to Fetch Resumes" message={fetchError} />
              <Button variant="secondary" size="sm" onClick={loadResumes}>
                Retry Fetch
              </Button>
            </CardContent>
          </Card>
        ) : resumes.length === 0 ? (
          <Card>
            <CardContent className="p-6">
              <EmptyState
                icon={<IconFileText size={24} className="text-slate-500" />}
                title="No resumes uploaded yet"
                description="Your resume repository is currently empty. Upload your first PDF resume above to extract skills, experience duration, and compute 384-d neural embeddings."
                action={
                  <Button
                    variant="secondary"
                    size="sm"
                    leftIcon={<IconUpload size={16} />}
                    onClick={() => fileInputRef.current?.click()}
                  >
                    Select PDF File
                  </Button>
                }
              />
            </CardContent>
          </Card>
        ) : filteredResumes.length === 0 ? (
          <Card>
            <CardContent className="p-8 text-center text-slate-400 text-sm">
              No resumes match &quot;{searchQuery}&quot;. Try adjusting your search query.
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 gap-4">
            {filteredResumes.map((resume) => {
              const skills = getSkillsList(resume);
              const expYears = getExperienceYears(resume);
              const eduLevel = getEducationLevel(resume);
              const formattedDate = new Date(resume.created_at).toLocaleDateString(undefined, {
                year: "numeric",
                month: "short",
                day: "numeric",
              });

              return (
                <Card
                  key={resume.id}
                  className="hover:border-slate-700 transition-colors bg-slate-900/60"
                >
                  <CardContent className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <IconFileText size={18} className="text-indigo-400 shrink-0" />
                        <h4 className="font-semibold text-white text-sm truncate max-w-sm">
                          {resume.original_filename}
                        </h4>
                        <Badge variant="default" size="sm">
                          {(resume.file_size_bytes / 1024).toFixed(0)} KB
                        </Badge>
                        <Badge variant="indigo" size="sm">
                          {formattedDate}
                        </Badge>
                      </div>

                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 pt-1">
                        <span>
                          <strong className="text-slate-300">Experience:</strong> {expYears}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-slate-300">Education:</strong> {eduLevel}
                        </span>
                        <span>•</span>
                        <span>
                          <strong className="text-slate-300">Skills ({skills.length}):</strong>
                        </span>
                      </div>

                      {/* Top Skills Badges */}
                      {skills.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1.5 pt-1.5">
                          {skills.slice(0, 6).map((skill, sIdx) => (
                            <Badge key={sIdx} variant="outline" size="sm" className="font-mono text-[11px]">
                              {skill}
                            </Badge>
                          ))}
                          {skills.length > 6 && (
                            <span className="text-[11px] text-slate-500 font-medium">
                              +{skills.length - 6} more
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
                        onClick={() => setViewingResume(resume)}
                      >
                        Details
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-slate-400 hover:text-rose-400 hover:bg-rose-950/20"
                        leftIcon={<IconTrash size={15} />}
                        onClick={() => setDeletingResume(resume)}
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

      {/* Resume Details Modal */}
      {viewingResume && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Resume Details"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs"
            onClick={() => setViewingResume(null)}
            aria-hidden="true"
          />

          <Card className="relative z-10 w-full max-w-2xl max-h-[85vh] flex flex-col border-slate-700 bg-slate-900 shadow-2xl overflow-hidden">
            <CardHeader className="flex flex-row items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <CardTitle className="text-base truncate max-w-md">
                  {viewingResume.original_filename}
                </CardTitle>
                <CardDescription className="text-xs">
                  ID: <span className="font-mono text-slate-300">{viewingResume.id}</span>
                </CardDescription>
              </div>
              <button
                type="button"
                onClick={() => setViewingResume(null)}
                className="rounded-lg p-1 text-slate-400 hover:text-white hover:bg-slate-800 transition-colors focus-ring"
                aria-label="Close details"
              >
                <IconX size={20} />
              </button>
            </CardHeader>

            <CardContent className="overflow-y-auto space-y-6 py-5">
              {/* Meta Grid */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">File Size</span>
                  <span className="font-semibold text-slate-200">
                    {(viewingResume.file_size_bytes / 1024).toFixed(1)} KB
                  </span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Uploaded</span>
                  <span className="font-semibold text-slate-200">
                    {new Date(viewingResume.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Experience</span>
                  <span className="font-semibold text-amber-300">
                    {getExperienceYears(viewingResume)}
                  </span>
                </div>
                <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                  <span className="text-slate-500 block mb-0.5">Education</span>
                  <span className="font-semibold text-emerald-300">
                    {getEducationLevel(viewingResume)}
                  </span>
                </div>
              </div>

              {/* Skills Breakdown */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Extracted Taxonomy Skills ({getSkillsList(viewingResume).length})
                </h4>
                <div className="flex flex-wrap gap-1.5 p-3.5 rounded-lg border border-slate-800 bg-slate-950/60">
                  {getSkillsList(viewingResume).length > 0 ? (
                    getSkillsList(viewingResume).map((skill, idx) => (
                      <Badge key={idx} variant="indigo" size="sm" className="font-mono text-xs">
                        {skill}
                      </Badge>
                    ))
                  ) : (
                    <span className="text-xs text-slate-500">
                      No explicit canonical skills extracted from this resume.
                    </span>
                  )}
                </div>
              </div>

              {/* Layout Sections */}
              {Array.isArray((viewingResume.structured_data || {}).sections_detected) && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Detected Document Sections
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {((viewingResume.structured_data || {}).sections_detected as string[]).map(
                      (sec, idx) => (
                        <Badge key={idx} variant="default" size="sm">
                          {sec}
                        </Badge>
                      )
                    )}
                  </div>
                </div>
              )}

              {/* Structured Explanation / Attribution */}
              {Boolean((viewingResume.explanation || {}).summary) && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Parser Explanation
                  </h4>
                  <p className="text-xs text-slate-400 bg-slate-950/60 p-3 rounded-lg border border-slate-800 leading-relaxed">
                    {String((viewingResume.explanation || {}).summary)}
                  </p>
                </div>
              )}
            </CardContent>

            <div className="p-4 border-t border-slate-800 flex justify-end">
              <Button variant="outline" size="sm" onClick={() => setViewingResume(null)}>
                Close
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deletingResume && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Confirm Resume Deletion"
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
        >
          <div
            className="fixed inset-0 bg-slate-950/80 backdrop-blur-xs"
            onClick={() => !isDeleting && setDeletingResume(null)}
            aria-hidden="true"
          />

          <Card className="relative z-10 w-full max-w-md border-rose-500/30 bg-slate-900 shadow-2xl">
            <CardHeader>
              <CardTitle className="text-rose-400 flex items-center gap-2">
                <IconTrash size={18} />
                Confirm Permanent Deletion
              </CardTitle>
              <CardDescription className="text-slate-300 text-xs">
                Are you sure you want to delete{" "}
                <strong className="text-white">&apos;{deletingResume.original_filename}&apos;</strong>?
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-slate-400 leading-relaxed">
                In strict compliance with GDPR Right to Be Forgotten, this action permanently purges parsed text, 384-dimensional vector embeddings, and all associated match evaluations with cascading delete. This operation cannot be undone.
              </p>
            </CardContent>
            <div className="p-4 border-t border-slate-800 flex items-center justify-end gap-2.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setDeletingResume(null)}
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
