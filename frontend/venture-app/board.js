import * as Phaser from 'phaser';

let game = null;

// Temporary gamestate dictionary
// TODO: Adapt this with the database and backend logic
let gameState = {
    currentStage: 0
};

// Store the full backend data here so we can use it later (like updating territories)
let currentBackendState = null;

// The Bridge to Python: Fetches the latest state and updates the UI
export async function fetchGameState() {
    try {
        const response = await fetch('http://localhost:5000/api/game/state');
        if (!response.ok) throw new Error("No active game found on backend");

        const data = await response.json();
        currentBackendState = data;

        // Python sends the stage as an integer (1 = Plan, 2 = Negotiate, etc.)
        // JS arrays start at 0, so we subtract 1 to match your STAGE_LABELS array!
        gameState.currentStage = data.current_stage - 1;

        // Update the visual dots on the screen
        updateStageIndicator();

        console.log("📥 Backend State Synced:", data);
    } catch (error) {
        console.error("Failed to sync game state:", error);
    }
}

export function startGame() {

    // Prevent multiple instances
    if (game) return;

    const container = document.getElementById('board-container');

    // Safety check (important for SPA routing)
    if (!container) {
        console.warn("No #board-container found. Phaser not started.");
        return;
    }

    initLeaderboardUI(container);
    initTerritoryUI(container);
    initStageProgressButton(container);

    // Define the game configuration
    const config = {
        type: Phaser.AUTO,
        width: window.innerWidth,
        height: window.innerHeight,
        parent: container,
        backgroundColor: '#ffffff',
        scale: {
            mode: Phaser.Scale.RESIZE,
            autoCenter: Phaser.Scale.CENTER_BOTH
        },
        input: {
            mouse: {
                target: document.getElementById('board-container')
            },
            touch: {
                target: document.getElementById('board-container')
            }
        },
        scene: {
            preload,
            create,
            update
        }
    };

    setTimeout(() => {
        game = new Phaser.Game(config);
    }, 50);
    console.log("Phaser game started");
}

// Called when leaving /game
export function stopGame() {

    if (game) {
        game.destroy(true); // true = remove canvas from DOM
        game = null;
        console.log("Phaser game destroyed");
    }
}

function initLeaderboardUI(container) {

    const button = document.getElementById('leaderboard-button');
    const overlay = document.getElementById('leaderboard-overlay');

    if (!button || !overlay) return;

    container.style.position = container.style.position || 'relative';

    button.addEventListener('click', () => {
        overlay.style.display = 'flex';
    });

    const closeButton = overlay.querySelector('.leaderboard-close');

    closeButton.addEventListener('click', () => {
        overlay.style.display = 'none';
    });

    overlay.addEventListener('click', (event) => {
        if (event.target === overlay) {
            overlay.style.display = 'none';
        }
    });
}

function initTerritoryUI(container) {

    const buttons = document.querySelectorAll('.territory-button');

    if (!buttons.length) return;

    container.style.position = container.style.position || 'relative';

    buttons.forEach((button) => {
        const overlay = button.nextElementSibling;
        if (!overlay || !overlay.classList.contains('territory-overlay')) return;

        button.addEventListener('click', () => {
            overlay.style.display = 'flex';
        });

        const closeButton = overlay.querySelector('.territory-close');
        if (closeButton) {
            closeButton.addEventListener('click', () => {
                overlay.style.display = 'none';
            });
        }

        overlay.addEventListener('click', (event) => {
            if (event.target === overlay) {
                overlay.style.display = 'none';
            }
        });
    });
}

function initStageProgressButton(container) {
    const button = document.getElementById('stage-progresser');
    if (!button) return;

    button.addEventListener('click', async () => {
        try {
            // Prevent spam-clicking while the AI is thinking
            button.style.pointerEvents = 'none';
            button.style.opacity = '0.5';

            // 1. Tell Python to push the clock forward (and trigger the AI)
            const response = await fetch('http://localhost:5000/api/game/advance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            console.log("⏩ Advanced Stage:", result);

            // 2. Fetch the fresh state from the backend to update our UI
            if (response.ok) {
                await fetchGameState();
            }

        } catch (error) {
            console.error("Error advancing stage:", error);
        } finally {
            // Re-enable the button
            button.style.pointerEvents = 'auto';
            button.style.opacity = '1';
        }
    });
}

const STAGE_LABELS = [
    'Planning',
    'Negotiating',
    'Ordering',
    'Resolving',
    'Updating'
];

// Update the stage indicator based on the current stage
function updateStageIndicator() {

    const dots = document.querySelectorAll('.stage-dot');
    const lines = document.querySelectorAll('.stage-line');
    const stageText = document.querySelector('#current-stage-display p');

    if (stageText) {
        stageText.textContent = STAGE_LABELS[gameState.currentStage] || 'Undefined';
    }

    dots.forEach((dot, index) => {
        if (index <= gameState.currentStage) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });

    lines.forEach((line, index) => {
        if (index < gameState.currentStage) {
            line.classList.add('active');
        } else {
            line.classList.remove('active');
        }
    });
}

// Reference dimensions for board scaling
const BOARD_REFERENCE_WIDTH = 7016;
const BOARD_REFERENCE_HEIGHT = 4961;

// Update territory button positions based on board scale
function updateTerritoryButtonPositions(boardScale) {

    const territoryButtons = document.querySelectorAll('.territory-button');

    territoryButtons.forEach((territoryButton) => {
        const baseLeft = parseFloat(territoryButton.dataset.adjustedPositionLeft);
        const baseTop = parseFloat(territoryButton.dataset.adjustedPositionTop);

        if (Number.isNaN(baseLeft) || Number.isNaN(baseTop)) return;

        territoryButton.style.left = `${baseLeft * boardScale}px`;
        territoryButton.style.top = `${baseTop * boardScale}px`;
    });
}

// Preload assets
function preload() {

    this.load.image('board', '/images/game_board.png');
    this.load.on('filecomplete-image-board', () => {
        console.log('Board image loaded successfully');
    });
    this.load.on('loaderror', (file) => {
        console.error('FAILED TO LOAD:', file.src);
    });
}

// Create the map
function create() {

    const board = this.add.image(0, 0, 'board');

    const resize = (width, height) => {

        console.log("Resizing to:", width, height);

        board.setPosition(width / 2, height / 2);

        const scaleX = width / board.width;
        const scaleY = height / board.height;
        const scale = Math.max(scaleX, scaleY);

        board.setScale(scale);

        // Update territory button positions based on board scale
        updateTerritoryButtonPositions(scale);
    };

    resize(this.scale.width, this.scale.height);

    this.scale.on('resize', (gameSize) => {
        resize(gameSize.width, gameSize.height);
    });

    // Enables scrolling when cursor is hovering over the game canvas
    this.input.on('wheel', (pointer, gameObjects, deltaX, deltaY) => {
        window.scrollBy(0, deltaY);
    });

    this.input.on('pointerdown', (pointer) => {
        console.log(`Clicked at: ${pointer.x}, ${pointer.y}`);
    });

    fetchGameState();
}

// Update the game loop
function update() {
    // Add any information to update or any animations here
}