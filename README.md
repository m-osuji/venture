# 📈 Venture: A Market Strategy Game for Business Students

## First-Time Setup
Before launching the app, you need to set up both the Python backend environment and the Vite frontend environment.

1. **Set up the Python Virtual Environment**
   Ensure you are in the root `project` folder and run:
```bash
   python -m venv venv
```

Activate the virtual environment:
- Windows: `.\venv\Scripts\activate`
- Mac/Linux: `source venv/bin/activate`
- Git Bash: `. venv/Scripts/activate`

2. **Install Backend Dependencies**
```bash
   pip install -r requirements.txt
```

3. **Environment Variables**
Create your local environment file:
```bash
   cp .env.example .env
```
Or `copy .env.example .env` if you're working in a native Windows command prompt. Then open the .env file and add your [HF_TOKEN](https://huggingface.co/settings/tokens).

4. **Install Frontend & Launcher Dependencies**
```bash
   npm install
```
Navigate to the frontend folder and install the UI packages:
```bash
   cd frontend/venture-app
   npm install
   cd ../..
```

## Launching Project
Once setup is complete, you can launch both the backend and frontend simultaneously with a single command.

1. Open a terminal in the root `project` folder.
2. Ensure your virtual environment is activated (see the Python setup bullet point [above](#first-time-setup))
3. **If needed:** Delete any pre-existing `game_state.json` files from the `backend/` directory, so as to forget the previous game state.
4. Run the master launcher:
```bash
   npm run dev
```
4. Open your browser and navigate to: **`http://localhost:5173/`**

*(Note: To hard-refresh the browser and clear the cache, use `Ctrl + Shift + R`).*

## Backend Testing 
All automated tests can be found in `project/backend/tests` and run from **root** using `python -m pytest backend/tests/ -m "not slow" -v`.

For coverage, run `python -m pytest backend/tests/ -m "not slow" -v --cov=backend --cov-report=term-missing`

## Frontend Testing
To run the Jest unit tests on the app, enter the following code into your terminal:

Within the `project/frontend/venture-app/` folder, you can run:
```bash
   npm test
```

To run a specific unit test, run:
```bash
   npm test -- <file_name>
```