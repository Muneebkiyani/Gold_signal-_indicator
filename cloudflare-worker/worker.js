/**
 * Cloudflare Worker: Telegram Bot API Reverse Proxy
 * 
 * This worker securely forwards all incoming requests to api.telegram.org.
 * Since Cloudflare is completely unblocked worldwide (including Pakistan),
 * requests sent through this worker reach Telegram instantly with zero blocks.
 */

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    // Build destination URL on Telegram's official API
    const targetUrl = `https://api.telegram.org${url.pathname}${url.search}`;

    // Clone headers and update Host
    const headers = new Headers(request.headers);
    headers.set("Host", "api.telegram.org");

    // Forward the request
    const response = await fetch(targetUrl, {
      method: request.method,
      headers: headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : null,
      redirect: "follow",
    });

    return response;
  },
};
