export interface Env {
  API_BASE_URL: string;
  ASSETS: { fetch(request: Request): Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/")) {
      const upstream = new URL(url.pathname + url.search, env.API_BASE_URL);
      const headers: Record<string, string> = { "Accept": "application/json" };
      const contentType = request.headers.get("Content-Type");
      if (contentType) {
        headers["Content-Type"] = contentType;
      }
      const response = await fetch(upstream.toString(), {
        method: request.method,
        headers,
        body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
      });
      const responseHeaders: Record<string, string> = {
        "Content-Type": response.headers.get("Content-Type") || "application/json",
      };
      if (request.method === "GET") {
        responseHeaders["Cache-Control"] = "public, max-age=60";
      }
      return new Response(response.body, {
        status: response.status,
        headers: responseHeaders,
      });
    }

    return env.ASSETS.fetch(request);
  },
};
