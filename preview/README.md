# SALAR redesign preview

This directory is an isolated preview. It does not import from or modify the production `frontend/` application.

## Launch

Double-click `start-preview.bat`, or run:

```powershell
cd "C:\Users\JD\Documents\SALAR AI\preview"
npm install
npm run dev
```

Open <http://127.0.0.1:4174>. Fixture mode is the default and does not require the backend.

## Verify

```powershell
npm run verify
```

The verification command runs TypeScript checking, the Vitest suite, a production preview build, and the Playwright fixture smoke tests.

## Optional live mode

Copy `.env.example` to `.env.local`, set the preview API URL and access values, then restart the preview server. Keep secrets in `.env.local`; it is ignored by Git.
