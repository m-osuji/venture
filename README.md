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
3. Run the master launcher:
```bash
   npm run dev
```
4. Open your browser and navigate to: **`http://localhost:5173/`**

*(Note: To hard-refresh the browser and clear the cache, use `Ctrl + Shift + R`).*

## Testing
To verify the game state management and data extraction logic, navigate into the project root and run the state helper file directly:
```bash
python -m backend.helpers.game_state_helpers
```

This will initialise a mock game, save it to `game_state.json` and print the sanitised frontend view to terminal. This is to remove all sensitive information that could give players an unfair advantage from the frontend game state.

For now, all other automated tests can be found in `project/backend/tests` and run individually using the `pytest` command.