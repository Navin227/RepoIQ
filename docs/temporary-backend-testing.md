# Temporary backend testing from the deployed Amplify frontend

This workflow points the existing Amplify frontend at a backend running on your
Windows machine. It does not change the Amplify build setting, AWS resources,
the EC2 instance, or K3s. The machine running the backend and tunnel must stay
online while you test.

During this inspection period, Analyze navigates to the repository analysis
view immediately, and search/analysis are not gated on EC2/K3s readiness. The
analysis view shows a running state, then a result or an explicit error with
its correlation ID. The backend API is still required to retrieve evidence;
this change does not fabricate an analysis when the endpoint is unavailable.
After the backend issue is resolved, restore the infrastructure readiness gate
in `Frontend/src/App.tsx` where the temporary bypass is marked, and change the
three component `apiAvailable` props back to the intended readiness condition
if product behavior should again require the demo server to be online.

## 1. Start the backend locally

Open PowerShell in the repository root. Use a separate SQLite database and
clone directory for this test session so your configured PostgreSQL database
and other local data are not replaced:

```powershell
Set-Location .\backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DATABASE_URL = "sqlite:///./repoiq-dev-testing.db"
$env:CLONE_BASE_DIR = (Join-Path (Get-Location) ".repoiq-dev-clones")
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Set any required provider or GitHub credentials in this PowerShell session
according to the backend's existing configuration. Do not put credentials in
the frontend, browser storage, this document, or source control. Provider
selection is unchanged. Check `http://127.0.0.1:8000/health` locally; expect
`{"status":"ok"}`.

## 2. Expose the backend through an authenticated HTTPS tunnel

Install and authenticate the ngrok agent using your account's normal setup.
Create a temporary policy file outside the repository, replacing the email
placeholder with the exact Google account you will use:

```yaml
on_http_request:
  - actions:
      - type: oauth
        config:
          provider: google
          options_passthrough: true
  - expressions:
      - "actions.ngrok.oauth.identity.email != 'YOUR_GOOGLE_EMAIL'"
    actions:
      - type: deny
```

Do not use a broad domain allowlist for this temporary endpoint. Start the tunnel in a second
PowerShell window, using the path where you saved the policy:

```powershell
ngrok http 8000 --traffic-policy-file "$env:TEMP\repoiq-ngrok-policy.yml"
```

Copy the HTTPS forwarding URL printed by ngrok. Before using the Amplify app,
open that URL in the same browser and complete Google OAuth. This establishes
the ngrok auth session; the tunnel allows CORS preflight `OPTIONS` through and
requires authentication for other requests. Do not use an unprotected public
tunnel. Confirm the ngrok OAuth policy and account features support these
settings before sending repository requests.

## 3. Point this browser at the temporary endpoint

In the Amplify app's browser DevTools Console, set the tunnel URL (origin only,
no `/analyze` path):

```js
localStorage.setItem('repoiq.devApiBase', 'https://YOUR-TUNNEL.ngrok.app');
location.reload();
```

Search and analysis then use the local backend even if the EC2/K3s demo reports
offline. The Analyze/Search controls stay disabled when no API URL is
configured. The browser-local override is explicitly temporary, takes
precedence over production configuration, and sends credentials only for
requests using that override. The backend CORS configuration already permits
the deployed Amplify origin.

Use the application normally to search and analyze repositories. Check the
backend terminal for request and analysis lifecycle logs and the browser
console for correlated frontend diagnostics. Requests are processed by your
local backend; its database and repository clones are on your machine.

## 4. Restore the normal Amplify API

In the same browser DevTools Console:

```js
localStorage.removeItem('repoiq.devApiBase');
location.reload();
```

The frontend immediately returns to the API endpoint configured in the
Amplify build. Close the ngrok process and stop the local backend when finished.
The browser override does not start or restore EC2/K3s. To return the demo
infrastructure to service, use the existing infrastructure controls, then
verify the EC2 instance, K3s readiness, backend health, and demo status
independently. No AWS endpoint setting or infrastructure resource is changed by
this workflow.

## Reversal

No deployment or infrastructure edits are needed to undo this testing mode.
Remove the browser key, stop the two local processes, and optionally delete
`backend/repoiq-dev-testing.db` and `backend/.repoiq-dev-clones` after confirming
you do not need their test data.
