"use client";

import React, { useState, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "../../components/ui/card";
import { Input } from "../../components/ui/input";
import { Button } from "../../components/ui/button";
import { ErrorAlert } from "../../components/ui/error-alert";
import { IconShieldCheck, IconArrowRight } from "../../components/ui/icons";
import { useAuth } from "../../lib/auth-context";
import { validateEmail, sanitizeReturnUrl } from "../../lib/auth-utils";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { login } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<{ email?: string; password?: string }>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError(null);

    const errors: { email?: string; password?: string } = {};
    const emailCheck = validateEmail(email);
    if (!emailCheck.isValid) {
      errors.email = emailCheck.error;
    }
    if (!password) {
      errors.password = "Password is required.";
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setFieldErrors({});
    setIsLoading(true);

    try {
      const result = await login(email, password);
      if (result.success) {
        const fromParam = searchParams.get("from");
        const destination = sanitizeReturnUrl(fromParam, "/dashboard");
        router.push(destination);
      } else {
        setServerError(result.error || "Authentication failed.");
      }
    } catch {
      setServerError("An unexpected connection error occurred.");
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
            Sign in to your account
          </h2>
          <p className="mt-1 text-xs text-slate-400">
            Access your explainable resume matching dashboard
          </p>
        </div>

        {/* Login Card */}
        <Card className="border-slate-800 bg-slate-900/80 shadow-xl">
          <form onSubmit={handleSubmit} noValidate>
            <CardHeader>
              <CardTitle className="text-base">Authentication</CardTitle>
              <CardDescription>
                Enter your registered credentials below
              </CardDescription>
            </CardHeader>

            <CardContent className="space-y-4">
              {serverError && (
                <ErrorAlert
                  title="Sign In Failed"
                  message={serverError}
                  onDismiss={() => setServerError(null)}
                />
              )}

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
                autoComplete="current-password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                error={fieldErrors.password}
                disabled={isLoading}
              />

              <Button
                type="submit"
                variant="primary"
                size="md"
                className="w-full mt-2"
                isLoading={isLoading}
                rightIcon={<IconArrowRight size={16} />}
              >
                Sign In
              </Button>
            </CardContent>

            <CardFooter className="justify-between text-xs text-slate-400">
              <span>Don&apos;t have an account?</span>
              <Link
                href={`/register${searchParams.get("from") ? `?from=${encodeURIComponent(searchParams.get("from")!)}` : ""}`}
                className="font-semibold text-indigo-400 hover:text-indigo-300 focus-ring rounded px-1"
              >
                Create an account
              </Link>
            </CardFooter>
          </form>
        </Card>

        {/* Security Guarantee Note */}
        <div className="flex items-center justify-center gap-2 text-center text-xs text-slate-400">
          <IconShieldCheck size={14} className="text-emerald-400 shrink-0" />
          <span>Encrypted with bcrypt • HttpOnly session cookies</span>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-400">
          Loading authentication form...
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
