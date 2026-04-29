# Developer Guide

## Adding new Python packages

If you need to install a new package for the backend (e.g., `pip install flask`), you must update the requirements file so the rest of the team can install it.

After installing the package, run:
```bash
pip freeze > requirements.txt
```