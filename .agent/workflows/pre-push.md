---
description: Pre-push checklist — run the app and explain changes before pushing to main
---

Before running `git push origin main`, always complete these steps:

1. **Start the backend dev server**
   ```bash
   cd /Users/kirti/hackhers/backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000
   ```
   Verify the server starts without import errors or crashes.

2. **Start the frontend dev server**
   ```bash
   cd /Users/kirti/hackhers/frontend && npm run dev
   ```
   Verify Vite compiles without errors.

3. **Verify in browser**
   - Open the frontend URL (usually http://localhost:5173)
   - Check that the app loads, navigation works, and new pages render
   - Hit any new API endpoints to confirm they respond

4. **Explain changes to the user**
   - Summarize what was changed and why
   - Show terminal output confirming the app runs
   - Note any warnings or issues found

5. **Only after verification passes**, run:
   ```bash
   git push origin main
   ```

If there are errors at any step, fix them before pushing.
