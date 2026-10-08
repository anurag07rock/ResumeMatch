export default function Home() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-slate-950 px-6 text-slate-100 antialiased">
      <main className="flex max-w-2xl flex-col items-center text-center">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-400">
          <span>Phase 1 Scaffolding</span>
          <span>•</span>
          <span>Active Development</span>
        </div>
        
        <h1 className="text-4xl font-extrabold tracking-tight sm:text-5xl text-white">
          ResumeMatch
        </h1>
        
        <p className="mt-4 text-lg text-slate-300">
          Explainable AI-Powered Resume-to-Job Matching Platform.
        </p>

        <p className="mt-2 text-sm text-slate-400 max-w-lg">
          An intelligent platform combining dense semantic embeddings, deterministic skill ontology matching, experience timeline verification, and transparent attribution to match resumes with job descriptions.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-xs text-slate-400">
          <span className="rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1">FastAPI Backend: Ready</span>
          <span className="rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1">Next.js 15: Ready</span>
          <span className="rounded-md border border-slate-800 bg-slate-900/80 px-2.5 py-1">TypeScript Strict: Enabled</span>
        </div>
      </main>
    </div>
  );
}
