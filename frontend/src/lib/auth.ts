export let nativeBackend = false;
export let transport = "poll";
export let boundBuyerId = "";
export let csrf = "";
export async function detectBackend() {
  const h = await fetch("/api/health").then(r => r.json());
  nativeBackend = h.backend === "native-dotnet";
  return nativeBackend;
}
export async function session() {
 const r = await fetch("/api/auth/session");
 if (!r.ok) throw new Error("Sign in required");
 const s = await r.json(); boundBuyerId = s.buyer_id || ""; csrf = s.csrf || ""; transport = s.transport || "poll"; return s;
}
export async function request(url: string, init: RequestInit = {}) {
 const headers = new Headers(init.headers);
 if (nativeBackend && init.method && init.method !== "GET") headers.set("X-CSRF-Token", csrf);
 const r = await fetch(url, {...init, headers, credentials: "same-origin"});
 if (nativeBackend && r.status === 401) window.dispatchEvent(new Event("auth-expired"));
 return r;
}
