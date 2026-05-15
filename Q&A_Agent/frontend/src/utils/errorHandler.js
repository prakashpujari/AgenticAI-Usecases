/**
 * errorHandler.js
 * ────────────────
 * Maps backend error_code values to user-friendly messages and extracts
 * retry_after / debug_id from structured API error responses.
 *
 * All backend errors conform to:
 *   { error_code, message, retry_after_seconds, debug_id }
 */

const ERROR_MESSAGES = {
  RATE_LIMIT_EXCEEDED:     "You've reached the 10-request hourly limit.",
  SPIKE_ARREST:            "Too many requests at once — please wait a moment.",
  GLOBAL_CAPACITY:         "Service is busy. Please retry in about a minute.",
  FILE_TOO_LARGE:          "File exceeds the 50 MB limit.",
  INVALID_FILE_TYPE:       "Unsupported file type. Accepted: PDF, DOCX, TXT, CSV, XLSX, PNG, JPG, MP3, MP4.",
  INVALID_URL:             "The URL is invalid or unreachable.",
  SSRF_BLOCKED:            "Requests to private/internal addresses are not allowed.",
  INVALID_YOUTUBE_URL:     "Only YouTube URLs (youtube.com / youtu.be) are accepted.",
  YOUTUBE_UNAVAILABLE:     "Could not fetch the YouTube transcript. Try uploading the video file directly.",
  WAF_BLOCKED:             "Input contains disallowed content.",
  LLM_UNAVAILABLE:         "AI service is temporarily unavailable. Please retry in 30 seconds.",
  PIPELINE_FAILED:         "Processing failed. Please try again.",
  SERVER_MISCONFIGURATION: "Server configuration error. Contact support.",
  JOB_NOT_FOUND:           "Job not found.",
  INVALID_PARAM:           "Invalid request parameters.",
};

/**
 * Parse an Axios error into a structured error object safe to display.
 *
 * @param {unknown} err - The caught error (Axios error or generic Error)
 * @returns {{ message: string, retryAfter: number|null, debugId: string|null, errorCode: string|null }}
 */
export function parseApiError(err) {
  if (err?.response?.data) {
    const data = err.response.data;
    const code = data.error_code ?? null;
    return {
      errorCode:   code,
      message:     ERROR_MESSAGES[code] ?? data.message ?? "Something went wrong.",
      retryAfter:  typeof data.retry_after_seconds === "number" ? data.retry_after_seconds : null,
      debugId:     data.debug_id ?? null,
    };
  }

  if (err?.message?.toLowerCase().includes("network")) {
    return { errorCode: null, message: "Network error — check your connection.", retryAfter: null, debugId: null };
  }

  return { errorCode: null, message: "An unexpected error occurred.", retryAfter: null, debugId: null };
}

/**
 * Generate a SHA-256 device fingerprint from stable browser properties.
 * Sent as X-Device-Fingerprint header; never stored raw (HMAC-hashed server-side).
 *
 * @returns {Promise<string>} 64-char hex string
 */
export async function getDeviceFingerprint() {
  try {
    const raw = [
      navigator.userAgent,
      `${screen.width}x${screen.height}`,
      screen.colorDepth,
      new Date().getTimezoneOffset(),
      navigator.language,
      navigator.hardwareConcurrency ?? 0,
    ].join("|");

    const encoded = new TextEncoder().encode(raw);
    const hashBuffer = await crypto.subtle.digest("SHA-256", encoded);
    return Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");
  } catch {
    return "0".repeat(64); // fallback if Web Crypto unavailable
  }
}
