# Free Telegram Cloudflare Worker Proxy

This free Cloudflare Worker acts as a reverse proxy for `api.telegram.org`. It allows your trading indicator system to send signals to Telegram without needing any VPN or local proxy.

---

## 🚀 60-Second Setup Instructions

### Step 1: Log in to Cloudflare
1. Go to [dash.cloudflare.com](https://dash.cloudflare.com/) and sign in (or create a free account).

### Step 2: Create a Worker
1. In the left sidebar, click **Compute (Workers & Pages)**.
2. Click the blue **Create application** (or **Create Worker**) button.
3. Click **Create Worker**.
4. Give it a name (e.g. `telegram-proxy`) and click **Deploy**.

### Step 3: Paste the Proxy Code
1. On the confirmation screen, click **Edit code**.
2. Replace all the existing code in the editor with the contents of [`worker.js`](worker.js):
   ```javascript
   export default {
     async fetch(request, env, ctx) {
       const url = new URL(request.url);
       const targetUrl = `https://api.telegram.org${url.pathname}${url.search}`;
       const headers = new Headers(request.headers);
       headers.set("Host", "api.telegram.org");

       return fetch(targetUrl, {
         method: request.method,
         headers: headers,
         body: request.method !== "GET" && request.method !== "HEAD" ? request.body : null,
         redirect: "follow",
       });
     },
   };
   ```
3. Click **Save and Deploy** in the top right.

### Step 4: Copy Your Worker URL
- Cloudflare will show your Worker URL at the top, which looks like:
  ```text
  https://telegram-proxy.<your-subdomain>.workers.dev
  ```

### Step 5: Update Your System `.env`
In your `gold-signal-system/backend/.env` file, add or update:
```bash
TELEGRAM_API_BASE_URL="https://telegram-proxy.<your-subdomain>.workers.dev"
```

### Step 6: Test!
Run:
```bash
cd gold-signal-system/backend
.venv/bin/python test_telegram_connection.py
```
Your test signal will be delivered to Telegram immediately!
