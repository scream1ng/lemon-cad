# Google login and Engineering chat setup

Google login is implemented, but disabled until a client ID is configured. Existing
email/password login remains available. Migration 002 adds Google identities; it
has been applied to the local development database.

## Create the Google client

1. Select a Google Cloud project and open Google Auth Platform.
2. Configure Branding with LemonCAD, support email, homepage and privacy policy.
   Configure the audience; add your test accounts while in testing mode.
3. Create a client with application type **Web application**.
4. Add authorized JavaScript origins: `http://localhost`,
   `http://localhost:5178`, and your exact production origin, such as
   `https://cad.example.com`. Origins have no path or trailing slash.
5. Copy the client ID ending in `.apps.googleusercontent.com`.

This implementation uses the JavaScript popup callback; it does not need a redirect
URI or client secret. Authentication uses basic identity scopes, not Google Drive
access. Check the console's verification status before public launch.
See [Google's setup guide](https://developers.google.com/identity/gsi/web/guides/get-google-api-clientid).

## Local configuration

In the terminal that starts the API, set:

```sh
export GOOGLE_CLIENT_ID='YOUR_CLIENT_ID.apps.googleusercontent.com'
export APP_ORIGIN='http://localhost:5178'
export COOKIE_SECURE=false
uv run python -m backend.migrate
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8048
```

Stop the existing API process first if port 8048 is occupied. Open the frontend at
`http://localhost:5178` for this configuration. `.env.example` is a reference;
the API does not automatically load it. No frontend rebuild is needed for client-ID
changes: the sign-in component reads the public ID from the API.

## Railway configuration

Set these variables on the API service, then redeploy:

| Variable | Value |
| --- | --- |
| `GOOGLE_CLIENT_ID` | Your web client ID |
| `APP_ORIGIN` | Exact HTTPS origin users visit |
| `COOKIE_SECURE` | `true` |

Keep the existing database and storage variables. The pre-deploy migration command
applies migration 002. Add the same public origin in Google's authorized JavaScript
origins. These authentication variables are not needed on the CAD worker.

## Check sign-in

- New email: Continue with Google creates an account, then opens a normal session.
- Existing password account: sign in with your password first, select **Connect
  Google**, and choose the Google account with the same email.
- Sign out and sign back in with Google; verify the same folders are present.
- Email/password sign-in remains available for existing password accounts.

The backend verifies the token and nonce and links accounts using Google's stable
subject ID. Matching email alone does not link an existing account. See
[Google's verification guide](https://developers.google.com/identity/gsi/web/guides/verify-google-id-token).
Automated tests mock Google's verifier; a real sign-in still needs testing with
your configured client. Google-only accounts currently have no password recovery flow.

If Google reports an origin mismatch, compare scheme, hostname and port exactly.
If a popup fails, check browser popup settings and the deployment's CSP/COOP headers
against Google's setup guide. Do not paste secrets into chat or commit them.

## Optional Claude connection

Set `ANTHROPIC_API_KEY` and `ANTHROPIC_MODEL` on the API service, using a model
available to your Anthropic account. Restart/redeploy. These stay server-side;
never use `VITE_` variables for API secrets. The integration uses the
[Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create).

Chat requires a signed-in user with the selected engineering entitlement. For local
testing, use the existing grant command:

```sh
uv run python -m scripts.grant YOUR_EMAIL fixture
uv run python -m scripts.grant YOUR_EMAIL costing
```

The chat currently sends conversation text and attached file metadata, not CAD
geometry. It supports planning and explanation; it does not generate verified
fixtures or inspect the actual shape. Existing calculator and fixture-brief tools
remain in the right-hand workspace. Completed exchanges and token usage are stored
as jobs. The current limit is 60 completed chat requests per user per day, with
1,600 output tokens per request; failed provider calls can still incur provider cost.
Credit purchases, wallet deductions and resumable chat history are not implemented.

Without credentials, the interface shows an explicit unavailable state. Live Google
and Claude calls have not been verified in this workspace.
