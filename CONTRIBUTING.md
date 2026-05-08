# Developer Guide

## Adding new Python packages

If you need to install a new package for the backend (e.g., `pip install flask`), you must update the requirements file so the rest of the team can install it.

After installing the package, run:
```bash
pip freeze > requirements.txt
```

## Manual launch instructions

*If you need to run the frontend or backend in isolation for debugging purposes:*

### Running only the frontend
- Navigate to the frontend folder: `cd project/frontend/venture-app`
- Run the local dev server: `npm run dev`
- Available at `http://localhost:5173/`

### Running only the backend
- Ensure your virtual environment is activated from the project root.
- Navigate into the backend directory: `cd project/backend`
- Start the local server: `flask run`
- Available at `http://127.0.0.1:5000`.