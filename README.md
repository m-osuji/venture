# 📈 Venture: A Market Strategy Game for Business Students

Venture is a browser-based strategy game for business student hackathon teams, inspired by RISK and Diplomacy but with luck removed in favour of knowledge-based progression. Teams compete in head-to-head IBM SkillsBuild quizzes to gain tactical advantages, working with or against each other across two game modes: a 20-minute speedrun or a 1-hour full experience. Only a single laptop is required, passed between teams between turns. An optional AI player can join multiplayer games to put your knowledge to the test, against IBM Granite 4.0.

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
3. **Important**: Switch *from* `main` to the specific branch currently linked to the deployed site: `git checkout granite/demo-integration`
4. **If needed:** Delete any pre-existing `game_state.json` files from the `backend/` directory, so as to forget the previous game state.
5. Run the master launcher:
```bash
   npm run dev
```
6. Open your browser and navigate to: **`http://localhost:5173/`**

- Equally, you can launch the site via the searchable **[game url](https://venture-game.netlify.app/)**. However, note that because we use the *free* tier for deployment (Netlify, Render), there is a chance our free tier limit is reached, and you might face issues loading pages. If so, please fallback to the steps outlined above.

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

- For more see `TESTING.md` in the project root, and/or the Testing document in our team Google Drive.