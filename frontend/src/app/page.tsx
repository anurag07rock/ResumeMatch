import React from "react";
import Link from "next/link";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription } from "../components/ui/card";
import {
  IconSparkles,
  IconFileText,
  IconArrowRight,
  IconCheckCircle,
} from "../components/ui/icons";

export const metadata = {
  title: "ResumeMatch — Explainable AI Resume Matching",
  description:
    "Deterministic skill ontology matching and neural semantic embeddings with zero hallucination.",
};

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Navigation Header */}
      <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5 focus-ring rounded-lg p-1">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-white font-black text-sm shadow-sm border border-indigo-500/40">
              RM
            </div>
            <span className="text-base font-bold text-white tracking-tight">
              ResumeMatch
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-6 text-sm font-medium text-slate-400">
            <Link href="/dashboard" className="hover:text-slate-100 transition-colors focus-ring rounded px-2 py-1">
              Dashboard
            </Link>
            <Link href="/resumes" className="hover:text-slate-100 transition-colors focus-ring rounded px-2 py-1">
              Resumes
            </Link>
            <Link href="/jobs" className="hover:text-slate-100 transition-colors focus-ring rounded px-2 py-1">
              Jobs
            </Link>
            <Link href="/matches" className="hover:text-slate-100 transition-colors focus-ring rounded px-2 py-1">
              Matches
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="text-xs font-semibold text-slate-300 hover:text-white px-2.5 py-1.5 rounded-lg hover:bg-slate-900 transition-colors focus-ring"
            >
              Sign In
            </Link>
            <Link href="/dashboard">
              <Button variant="primary" size="sm" rightIcon={<IconArrowRight size={14} />}>
                Launch App
              </Button>
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="flex-1">
        <section className="relative overflow-hidden py-16 sm:py-24 lg:py-28 px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-4xl text-center">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-950/40 px-3.5 py-1 text-xs font-medium text-indigo-300">
              <IconSparkles size={14} className="text-indigo-400" />
              <span>Phase 4 • Secure Session Authentication</span>
              <span className="text-slate-600">•</span>
              <span className="text-emerald-400">FastAPI v1 Ready</span>
            </div>

            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-5xl lg:text-6xl leading-tight">
              Explainable AI-Powered <br className="hidden sm:inline" />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 via-sky-300 to-indigo-300">
                Resume-to-Job Matching
              </span>
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-base sm:text-lg text-slate-300 leading-relaxed">
              Eliminate black-box scoring with deterministic skill ontology matching, 384-dimensional dense semantic embeddings, and verifiable attribution breakdowns.
            </p>

            <div className="mt-8 flex flex-wrap items-center justify-center gap-4">
              <Link href="/dashboard">
                <Button variant="primary" size="lg" rightIcon={<IconArrowRight size={16} />}>
                  Enter Dashboard
                </Button>
              </Link>
              <Link href="/resumes">
                <Button variant="outline" size="lg" leftIcon={<IconFileText size={16} />}>
                  Explore Resumes
                </Button>
              </Link>
            </div>

            {/* Verification & Guarantees */}
            <div className="mt-12 flex flex-wrap items-center justify-center gap-6 text-xs text-slate-400">
              <span className="flex items-center gap-1.5">
                <IconCheckCircle size={15} className="text-emerald-400" />
                <span>Zero Hallucination</span>
              </span>
              <span className="flex items-center gap-1.5">
                <IconCheckCircle size={15} className="text-emerald-400" />
                <span>100% Deterministic Reproducibility</span>
              </span>
              <span className="flex items-center gap-1.5">
                <IconCheckCircle size={15} className="text-emerald-400" />
                <span>Sliding Window Chunking (Zero Truncation)</span>
              </span>
              <span className="flex items-center gap-1.5">
                <IconCheckCircle size={15} className="text-emerald-400" />
                <span>GDPR Instant Purge</span>
              </span>
            </div>
          </div>
        </section>

        {/* Core Architectural Pillars */}
        <section className="border-t border-slate-800/80 bg-slate-900/30 py-16 sm:py-20 px-4 sm:px-6 lg:px-8">
          <div className="mx-auto max-w-7xl">
            <div className="text-center max-w-2xl mx-auto mb-12">
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                Engineered for Total Attribution
              </h2>
              <p className="mt-2 text-sm text-slate-400">
                Four calibrated dimensions evaluate candidates comprehensively without hidden bias.
              </p>
            </div>

            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-sky-400 font-mono text-xs font-bold">DIMENSION 01</span>
                    <Badge variant="default" size="sm">50% Weight</Badge>
                  </div>
                  <CardTitle className="text-base mt-2">Semantic Similarity</CardTitle>
                  <CardDescription>
                    Dense 384-dimensional sentence transformer embeddings using mean-pooled sliding windows.
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-indigo-400 font-mono text-xs font-bold">DIMENSION 02</span>
                    <Badge variant="indigo" size="sm">30% Weight</Badge>
                  </div>
                  <CardTitle className="text-base mt-2">Skills Alignment</CardTitle>
                  <CardDescription>
                    Deterministic intersection against 1,200+ canonical taxonomy entities with boundary guards.
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-amber-400 font-mono text-xs font-bold">DIMENSION 03</span>
                    <Badge variant="warning" size="sm">10% Weight</Badge>
                  </div>
                  <CardTitle className="text-base mt-2">Experience Timeline</CardTitle>
                  <CardDescription>
                    Verification of candidate professional tenure against job minimum thresholds.
                  </CardDescription>
                </CardHeader>
              </Card>

              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <span className="text-emerald-400 font-mono text-xs font-bold">DIMENSION 04</span>
                    <Badge variant="success" size="sm">10% Weight</Badge>
                  </div>
                  <CardTitle className="text-base mt-2">Education Credentials</CardTitle>
                  <CardDescription>
                    Ordinal hierarchy matching (Bachelor&apos;s, Master&apos;s, Doctorate) with grace scaling.
                  </CardDescription>
                </CardHeader>
              </Card>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-950 py-8 px-4 sm:px-6 lg:px-8 text-xs text-slate-400">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-300">ResumeMatch</span>
            <span>—</span>
            <span>Explainable AI Career-Tech Platform</span>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/dashboard" className="hover:text-slate-200 transition-colors focus-ring rounded">
              Dashboard
            </Link>
            <Link href="/resumes" className="hover:text-slate-200 transition-colors focus-ring rounded">
              Resumes
            </Link>
            <Link href="/jobs" className="hover:text-slate-200 transition-colors focus-ring rounded">
              Jobs
            </Link>
            <Link href="/matches" className="hover:text-slate-200 transition-colors focus-ring rounded">
              Matches
            </Link>
            <Link href="/settings" className="hover:text-slate-200 transition-colors focus-ring rounded">
              Settings
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
