<div align="center">
<img width="1200" height="475" alt="GHBanner" src="https://ai.google.dev/static/site-assets/images/share-ais-513315318.png" />
</div>

# Run and deploy your AI Studio app

This contains everything you need to run your app locally.

View your app in AI Studio: https://ai.studio/apps/42bec242-62e0-4db3-881f-ffa9e17a3881

## Run Locally

**Prerequisites:**  Node.js


1. Install dependencies:
   `npm install`
2. Set the `GEMINI_API_KEY` in [.env.local](.env.local) to your Gemini API key
3. Run the app:
   `npm run dev`

## Production API endpoint

The demo control API configured by `VITE_DEMO_API_URL` is an HTTPS API Gateway
endpoint for `/demo/start`, `/demo/stop`, and `/demo/status`. It is not a proxy
for repository search or analysis. `/demo/status` currently returns the
ephemeral EC2 application's `http://<public-ip>` URL; an HTTPS Amplify page
cannot call that HTTP URL because browsers block mixed content.

Terraform provisions an AWS Lambda Function URL as the stable HTTPS endpoint
for `/health`, `/search`, `/analyze`, and `/api/repositories/{id}`. AWS provides
the hostname and TLS certificate; no custom domain or public EC2 IP is needed.
The proxy resolves the currently running demo instance from its lifecycle tags
on each request and forwards to the existing Traefik HTTP listener on port 80.
Its allowlist does not expose the lifecycle API or arbitrary EC2 paths.

Set `VITE_API_BASE_URL` in **AWS Amplify > App settings > Environment
variables** to the Terraform `backend_api_endpoint` output. Keep
`VITE_DEMO_API_URL` set to the separate Terraform `demo_api_endpoint` output;
it continues to handle `/demo/start`, `/demo/stop`, and `/demo/status`. The
backend base takes precedence over the runtime HTTP URL returned by
`/demo/status`. The frontend's mixed-content guard remains enabled.

The Lambda Function URL has no separate endpoint fee. The proxy is billed at
standard Lambda rates: approximately $0.20 per million requests plus
$0.0000166667 per GB-second. At 128 MB, that is about $0.62 per million
200 ms requests, or $125 per million 60-second analyses, before data transfer
and CloudWatch Logs charges. Actual costs depend on request duration, traffic,
response size, region, and any applicable free tier. No load balancer, API
Gateway routes, or always-on proxy instance is added.

Keep `https://main.d20r18yhh140ff.amplifyapp.com` allowed in backend CORS and
the Terraform `frontend_origin` setting. Verify `/health` and
`/search?q=healthcare%20platforms` through `backend_api_endpoint` while the
demo server is running before considering the production deployment live.
