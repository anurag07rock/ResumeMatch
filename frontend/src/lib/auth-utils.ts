/**
 * ResumeMatch — Authentication & Security Utilities
 * Implements client-side validation rules strictly mirroring backend security policies
 * and sanitization against open redirects.
 */

export const EMAIL_REGEX = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
export const SPECIAL_CHAR_REGEX = /[!@#$%^&*(),.?":{}|<>\-_=+[\]\\/`~]/;

export interface PasswordValidationResult {
  isValid: boolean;
  errors: string[];
  rules: {
    minLength: boolean;
    hasUppercase: boolean;
    hasDigit: boolean;
    hasSpecial: boolean;
    maxLength: boolean;
  };
}

/**
 * Validates password strength matching backend `validate_password_strength` in security.py
 */
export function validatePassword(password: string): PasswordValidationResult {
  const minLength = password.length >= 8;
  const maxLength = new TextEncoder().encode(password).length <= 72;
  const hasUppercase = /[A-Z]/.test(password);
  const hasDigit = /[0-9]/.test(password);
  const hasSpecial = SPECIAL_CHAR_REGEX.test(password);

  const errors: string[] = [];
  if (!minLength) errors.push("Password must be at least 8 characters long.");
  if (!maxLength) errors.push("Password must not exceed 72 bytes.");
  if (!hasUppercase) errors.push("Password must contain at least one uppercase letter.");
  if (!hasDigit) errors.push("Password must contain at least one numeric digit.");
  if (!hasSpecial) errors.push("Password must contain at least one special symbol.");

  return {
    isValid: errors.length === 0,
    errors,
    rules: {
      minLength,
      hasUppercase,
      hasDigit,
      hasSpecial,
      maxLength,
    },
  };
}

/**
 * Validates email address format matching backend Pydantic field_validator
 */
export function validateEmail(email: string): { isValid: boolean; error?: string } {
  const trimmed = email.trim().toLowerCase();
  if (!trimmed) {
    return { isValid: false, error: "Email address is required." };
  }
  if (!EMAIL_REGEX.test(trimmed)) {
    return { isValid: false, error: "Please enter a valid email address (e.g. name@example.com)." };
  }
  return { isValid: true };
}

/**
 * Sanitizes return URL to prevent open redirect vulnerabilities.
 * Disallows absolute URLs, protocol-relative URLs (//evil.com), and backslash tricks (/\evil.com).
 */
export function sanitizeReturnUrl(returnUrl: string | null | undefined, fallback: string = "/dashboard"): string {
  if (!returnUrl) return fallback;

  // Must begin with a single forward slash and not followed by another slash or backslash
  if (returnUrl.startsWith("/") && !returnUrl.startsWith("//") && !returnUrl.startsWith("/\\")) {
    // Disallow control characters
    try {
      const parsed = new URL(returnUrl, "http://localhost");
      if (parsed.origin === "http://localhost") {
        return `${parsed.pathname}${parsed.search}`;
      }
    } catch {
      return fallback;
    }
  }

  return fallback;
}
