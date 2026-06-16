// 后端 API 客户端（含 SSE）。

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

// MVP：浏览器端持久化一个匿名用户 id，作为 X-User-Id。生产换成真正的登录态。
export function userId(): string {
  if (typeof window === "undefined") return "default";
  let id = window.localStorage.getItem("wewrite_uid");
  if (!id) {
    id = "u_" + Math.random().toString(36).slice(2, 10);
    window.localStorage.setItem("wewrite_uid", id);
  }
  return id;
}

function headers(): HeadersInit {
  return { "Content-Type": "application/json", "X-User-Id": userId() };
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, { headers: headers() });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export async function apiSend<T>(
  path: string,
  method: "POST" | "PUT" | "DELETE",
  body?: unknown
): Promise<T> {
  const r = await fetch(`${API_BASE}${path}`, {
    method,
    headers: headers(),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export type CatalogItem = { id: string; label: string; description: string };
export type AccountState = {
  account_name: string;
  writing_persona: string;
  theme: string;
  audience: string;
  tone: string;
  wechat_bound: boolean;
  wechat_author: string;
};
export type JobSummary = {
  id: string;
  status: "queued" | "running" | "done" | "error";
  prompt: string;
  created_at: number;
  completion?: string | null;
  kind?: "generate" | "distribute";
};
export type PlatformVersion = {
  platform: string;
  label: string;
  output_kind: string;
  title: string;
  markdown: string;
  images: string[];
  tags: string[];
  humanness: number | null;
  max_similarity: number | null;
  passed: boolean;
  warning: string;
  status: string;
};

export type JobDetail = JobSummary & {
  error?: string | null;
  title?: string | null;
  article_markdown?: string | null;
  preview_html?: string | null;
  images?: string[];
  events: JobEvent[];
  platform_versions?: PlatformVersion[];
};

// 产物 URL：后端返回相对 /artifacts/...，前端按需补上 API_BASE。
export function artifactUrl(p: string): string {
  return p.startsWith("/") ? `${API_BASE}${p}` : p;
}
export type JobEvent = {
  seq: number;
  ts: number;
  type: string;
  [k: string]: unknown;
};

export const getHealth = () => apiGet<Record<string, unknown>>("/api/health");
export const getPersonas = () => apiGet<CatalogItem[]>("/api/catalog/personas");
export const getThemes = () => apiGet<CatalogItem[]>("/api/catalog/themes");
export const getAccount = () => apiGet<AccountState>("/api/account");
export const saveStyle = (s: Partial<AccountState>) =>
  apiSend<AccountState>("/api/account/style", "PUT", s);
export const bindWeChat = (b: { appid: string; secret: string; author: string }) =>
  apiSend<AccountState>("/api/account/wechat", "PUT", b);
export const unbindWeChat = () => apiSend<AccountState>("/api/account/wechat", "DELETE");

export const createJob = (req: {
  prompt: string;
  interactive?: boolean;
  theme?: string | null;
  persona?: string | null;
  publish_draft?: boolean;
}) => apiSend<JobSummary>("/api/jobs", "POST", req);

export const getJob = (id: string) => apiGet<JobDetail>(`/api/jobs/${id}`);

// ---- 多平台发布 ----
export type PlatformStatus = {
  id: string;
  label: string;
  login_kind: "api_key" | "qrcode" | "none";
  supports_text: boolean;
  supports_image: boolean;
  supports_video: boolean;
  available: boolean;
  note: string;
  logged_in: boolean;
  user_name: string;
};
export type LoginChallenge = {
  kind: string;
  qrcode_image?: string | null;
  challenge_id: string;
  detail: string;
};
export type LoginStatusResp = { logged_in: boolean; detail: string; user_name: string };
export type PublishResponse = { ok: boolean; platform: string; url: string; detail: string };
export type NoteInput = {
  title?: string;
  content?: string;
  images?: string[];
  tags?: string[];
  video?: string | null;
};

export const getPlatforms = () => apiGet<PlatformStatus[]>("/api/publish/platforms");
export const startLogin = (platform: string) =>
  apiSend<LoginChallenge>(`/api/publish/${platform}/login/start`, "POST");
export const loginStatus = (platform: string) =>
  apiGet<LoginStatusResp>(`/api/publish/${platform}/status`);
export const logoutPlatform = (platform: string) =>
  apiSend<LoginStatusResp>(`/api/publish/${platform}/login`, "DELETE");
export const publishTo = (
  platform: string,
  payload: { job_id?: string; note?: NoteInput }
) => apiSend<PublishResponse>(`/api/publish/${platform}`, "POST", payload);

// ---- 多平台改写分发 ----
export const fetchPlatforms = () =>
  apiGet<{ id: string; label: string; description: string }[]>("/api/catalog/platforms");

export async function startDistribute(body: {
  source_job_id?: string;
  source_text?: string;
  source_url?: string;
  platforms: string[];
  persona?: string;
  theme?: string;
}) {
  return apiSend<JobSummary>("/api/distribute", "POST", body);
}

// 订阅任务进度。返回取消函数。
export function streamJob(
  id: string,
  onEvent: (e: JobEvent) => void,
  onEnd: () => void
): () => void {
  const url = `${API_BASE}/api/jobs/${id}/stream?user_id=${encodeURIComponent(userId())}`;
  const es = new EventSource(url);
  es.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data));
    } catch {
      /* ignore non-JSON keepalive */
    }
  };
  es.addEventListener("end", () => {
    es.close();
    onEnd();
  });
  es.onerror = () => {
    es.close();
    onEnd();
  };
  return () => es.close();
}
