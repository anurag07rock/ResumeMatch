"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { ErrorAlert } from "../../components/ui/error-alert";
import { IconShieldCheck, IconArrowRight, IconCheckCircle } from "../../components/ui/icons";
import { useAuth } from "../../lib/auth-context";
import { validateEmail, validatePassword, sanitizeReturnUrl } from "../../lib/auth-utils";

function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { register } = useAuth();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Live password validation
  const pwdCheck = validatePassword(password);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);

    const errors: { email?: string; password?: string } = {};
    const emailCheck = validateEmail(email);
    if (!emailCheck.isValid) {
      errors.email = emailCheck.error;
    }

    if (!pwdCheck.isValid) {
      errors.password = pwdCheck.errors[0] || "Password does not meet complexity criteria.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsLoading(true);

    try {
      const result = await register(email, password, fullName.trim() || undefined);
      if (result.success) {
        const fromParam = searchParams.get("from");
        const destination = sanitizeReturnUrl(fromParam, "/dashboard");
        router.push(destination);
      } else {
        setServerError(result.error || "Registration failed.");
      }
    } catch {
      setServerError("An unexpected error occurred during account creation.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col items-center justify-center px-4 py-12 sm:px-6 lg:px-8 bg-slate-950">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2.5 font-bold text-white text-lg tracking-tight focus-ring rounded-lg p-1"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white font-black text-sm shadow-sm border border-indigo-500/40">
              RM
            </div>
            <span>ResumeMatch</span>
          </Link>
          <h2 className="mt-4 text-2xl font-bold tracking-tight text-white">
            Create your account
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Start matching resumes against job descriptions with complete attribution
          </p>
        </div>

        {/* Register Card */}
        <Card className="border-slate-800 bg-slate-900/80 shadow-xl">
          <form onSubmit={handleSubmit} noValidate>
            <CardHeader>
              <CardTitle className="text-base">Candidate / Recruiter Registration</CardTitle>
              <CardDescription>
                Fill in your details below to set up your workspace
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {serverError && (
                <ErrorAlert
                  title="Registration Failed"
                  message={serverError}
                  onDismiss={() => setServerError(null)}
                />
              )}

              <Input
                label="Full name (Optional)"
                type="text"
                autoComplete="name"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={isLoading}
              />

              <Input
                label="Email address"
                type="email"
                autoComplete="email"
                required
                placeholder="candidate@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={fieldErrors.email}
                disabled={isLoading}
              />

              <Input
                label="Password"
                type="password"
                autoComplete="new-password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={fieldErrors.password}
                disabled={isLoading}
              />

              {/* Password Complexity Checklist */}
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3 space-y-1.5 text-[11px]">
                <span className="font-semibold text-slate-300 block mb-1">
                  Password Requirements:
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 text-slate-400">
                  <div className={`flex items-center gap-1.5 ${pwdCheck.rules.minLength ? "text-emerald-400" : ""}`}>
                    <IconCheckCircle size={12} className={pwdCheck.rules.minLength ? "text-emerald-400" : "text-slate-600"} />
                    <span>&ge; 8 characters</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${pwdCheck.rules.hasUppercase ? "text-emerald-400" : ""}`}>
                    <IconCheckCircle size={12} className={pwdCheck.rules.hasUppercase ? "text-emerald-400" : "text-slate-600"} />
                    <span>1 uppercase letter</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${pwdCheck.rules.hasDigit ? "text-emerald-400" : ""}`}>
                    <IconCheckCircle size={12} className={pwdCheck.rules.hasDigit ? "text-emerald-400" : "text-slate-600"} />
                    <span>1 numeric digit</span>
                  </div>
                  <div className={`flex items-center gap-1.5 ${pwdCheck.rules.hasSpecial ? "text-emerald-400" : ""}`}>
                    <IconCheckCircle size={12} className={pwdCheck.rules.hasSpecial ? "text-emerald-400" : "text-slate-600"} />
                    <span>1 special symbol</span>
                  </div>
                </div>
              </div>

              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full mt-2"
                isLoading={isLoading}
                rightIcon={<IconArrowRight size={16} />}
              >
                Create Account
              </Button>
            </CardContent>

            <CardFooter className="justify-between text-xs text-slate-400">
              <span>Already registered?</span>
              <Link
                href={`/login${searchParams.get("from") ? `?from=${encodeURIComponent(searchParams.get("from")!)}` : ""}`}
                className="font-semibold text-indigo-400 hover:text-indigo-300 focus-ring rounded px-1"
              >
                Sign in
              </Link>
            </CardFooter>
          </form>
        </Card>

        {/* Security Guarantee Note */}
        <div className="flex items-center justify-center gap-2 text-center text-xs text-slate-400">
          <IconShieldCheck size={14} className="text-emerald-400 shrink-0" />
          <span>Tenant-isolated records • Instant GDPR hard-deletion</span>
        </div>
      </div>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
          Loading registration form...
        </div>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}
