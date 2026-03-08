export interface Env {
  API_BASE_URL: string;
  ASSETS: { fetch(request: Request): Promise<Response> };
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname.startsWith("/api/")) {
      const upstream = new URL(url.pathname + url.search, env.API_BASE_URL);
      const response = await fetch(upstream.toString(), {
        method: request.method,
        headers: { "Accept": "application/json" },
      });
      return new Response(response.body, {
        status: response.status,
        headers: {
          "Content-Type": response.headers.get("Content-Type") || "application/json",
          "Cache-Control": "public, max-age=60",
        },
      });
    }

    return env.ASSETS.fetch(request);
  },
};
