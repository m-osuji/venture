# Getting Started

## Frontend

To run the frontend:
- Make sure you are in the `project\frontend` folder:
```bash
cd .\project\frontend\venture-app
```

- Run the following command so it runs locally:
```bash
npm run dev
```

- In your browser navigate to the relevant page, the one it gives, most likely:
```bash
http://localhost:5173/
```

- If you want to refresh use the command:
```bash
Ctrl + Shift + r
```

## Backend

To run the backend:
- Ensure you are in the `project\backend` folder:
```bash
cd .\project\backend
```

- **(First-time running/once only!)** Create a virtual environment:
```bash
python -m venv venv
```

- Activate the virtual environment:
```bash
.\venv\Scripts\activate
```
*(Note: If on Mac/Linux, use `source venv/bin/activate` instead)*

- Install dependencies:
```bash
pip install -r requirements.txt
```
- Create your local environment file using `cp .env.example .env`, then add your [HF_TOKEN](https://huggingface.co/settings/tokens)

- Start the local server (first navigate into `\project\backend`):
 ```bash
 flask run
```
which will be available at `http://127.0.0.1:5000`.

## Testing

To verify the game state management and data extraction logic, navigate into the project root and run the state helper file directly:
```bash
python -m backend.helpers.game_state_helpers
```

This will initialise a mock game, save it to `game_state.json` and print the sanitised frontend view to terminal. This is to remove all sensitive information that could give players an unfair advantage from the frontend game state.