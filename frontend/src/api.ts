import type { User } from "./types";

const BASE = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");
let token = sessionStorage.getItem("sicoa-token") || "";
export const hasSession = () => Boolean(token);
export function clearSession() {
  token = "";
  sessionStorage.removeItem("sicoa-token");
}
export class ApiError extends Error {
  status: number;
  current: unknown;
  constructor(status: number, message: string, current?: unknown) {
    super(message);
    this.status = status;
    this.current = current;
  }
}
async function response(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const result = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });
  if (!result.ok) {
    const body = await result
      .json()
      .catch(() => ({ detail: "No se pudo completar la solicitud." }));
    const detail = body.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message ||
          (Array.isArray(detail)
            ? detail.map((e: { msg: string }) => e.msg).join(". ")
            : "Error de validación.");
    if (result.status === 401 && path !== "/auth/login") {
      clearSession();
      window.dispatchEvent(new Event("sicoa-session-expired"));
    }
    throw new ApiError(result.status, message, detail?.current);
  }
  return result;
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  return (await response(path, options)).json();
}
export async function login(username: string, password: string) {
  const data = await api<{ access_token: string; user: User }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  token = data.access_token;
  sessionStorage.setItem("sicoa-token", token);
  return data.user;
}
export async function download(path: string, name: string) {
  const result = await response(path);
  const url = URL.createObjectURL(await result.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function errorMessage(error: unknown) {
  return error instanceof Error
    ? error.message
    : "No se pudo completar la operación.";
}
