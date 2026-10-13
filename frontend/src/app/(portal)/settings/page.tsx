import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "../../../components/ui/card";
import { Badge } from "../../../components/ui/badge";
import { Input } from "../../../components/ui/input";
import { IconShieldCheck } from "../../../components/ui/icons";

export const metadata = {
  title: "Settings — ResumeMatch",
  description: "Platform governance, scoring weights, and security parameters.",
};

export default function SettingsPage() {
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white sm:text-3xl">
            Platform Settings & Governance
          </h2>
          <p className="mt-1 text-sm text-slate-400">
            Audit scoring weights, privacy controls, and API endpoint configuration.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="indigo" size="md">
            Environment: Local Dev
          </Badge>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Scoring Weights Calibration */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Scoring Engine Weights</CardTitle>
              <Badge variant="success" size="sm">
                Locked & Calibrated
              </Badge>
            </div>
            <CardDescription>
              Weights sum strictly to 1.0 (100%) for mathematical determinism
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between text-slate-300 font-medium mb-1">
                  <span>Semantic Similarity (weight_semantic)</span>
                  <span className="font-mono text-sky-400">0.50 (50%)</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-sky-500 rounded-full" style={{ width: "50%" }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-300 font-medium mb-1">
                  <span>Skills Alignment (weight_skills)</span>
                  <span className="font-mono text-indigo-400">0.30 (30%)</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full" style={{ width: "30%" }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-300 font-medium mb-1">
                  <span>Experience Duration (weight_experience)</span>
                  <span className="font-mono text-amber-400">0.10 (10%)</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: "10%" }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-slate-300 font-medium mb-1">
                  <span>Education Credentials (weight_education)</span>
                  <span className="font-mono text-emerald-400">0.10 (10%)</span>
                </div>
                <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: "10%" }} />
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 pt-2 border-t border-slate-800/60 leading-relaxed">
              Weights reflect Phase 2 AI/ML benchmark optimization ($P \ge 0.90$, Spearman $\rho \ge 0.85$).
            </p>
          </CardContent>
        </Card>

        {/* Security & GDPR Hard Deletion */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Data Governance & GDPR</CardTitle>
              <Badge variant="indigo" size="sm">
                Strict Compliance
              </Badge>
            </div>
            <CardDescription>
              Zero candidate data retention beyond explicit user lifespan
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-xs">
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-semibold">
                <IconShieldCheck size={16} className="text-emerald-400" />
                <span>Instant Cascading Purge</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                Deleting a resume immediately purges parsed text, 384-d vector embeddings, and all matching records via database foreign key cascading (<code className="font-mono text-slate-300">ON DELETE CASCADE</code>).
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-semibold">
                <IconShieldCheck size={16} className="text-emerald-400" />
                <span>Zero External LLM Leakage</span>
              </div>
              <p className="text-slate-400 leading-relaxed">
                All inference runs locally on the host server. Resumes and job descriptions are never sent to third-party commercial AI APIs.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* API Client Configuration */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>API Connection & Diagnostics</CardTitle>
            <CardDescription>
              Backend endpoint target and environment variables
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Input
                label="API Base URL (NEXT_PUBLIC_API_BASE_URL)"
                defaultValue={process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"}
                disabled
                helperText="Configured via environment variable. Falls back to local FastAPI development server."
              />
              <Input
                label="JWT Authorization Header Mode"
                defaultValue="Bearer <token> (HS256)"
                disabled
                helperText="Enforced on all /api/v1 protected endpoints."
              />
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
