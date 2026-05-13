import * as Phaser from 'phaser';

let game = null;

// Temporary gamestate dictionary
// TODO: Adapt this with the database and backend logic
let gameState = {
    currentStage: 0,
    teamModeActive: false,
    currentTeamIndex: 0,
    tournamentRankings: []
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

        console.log("📥 Backend Data:", data);

        // This map handles BOTH the string name and the Enum integer
        // It converts them all to the 0-4 index JS needs for the UI
        const stageMap = {
            "PLAN": 0, 1: 0,
            "NEGOTIATE": 1, 2: 1,
            "ORDERS": 2, 3: 2,
            "RESOLVE": 3, 4: 3,
            "UPDATE": 4, 5: 4
        };

        const rawStage = data.current_stage;
        
        // If rawStage is "PLAN", lookup "PLAN". If it's 1, lookup 1.
        const mappedIndex = stageMap[rawStage];

        if (mappedIndex !== undefined) {
            gameState.currentStage = mappedIndex;
        } else {
            console.warn("Unknown stage received from Python:", rawStage);
            gameState.currentStage = 0; // Default to Plan
        }

        updateStageIndicator();

    } catch (error) {
        console.error("❌ Sync Failed:", error);
        // Ensure UI doesn't show "Undefined" even if the API fails
        gameState.currentStage = 0; 
        updateStageIndicator();
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
    initTeamIndicatorDisplay(container);
    initStageIndicator(container);
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

    // Hide leaderboard button initially (until tournament finishes)
    button.style.display = 'none';

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

function initTeamIndicatorDisplay(container) {
    // Team indicator display will be shown/hidden by initTeamIndicator
    // based on whether team mode is active
}

function initStageProgressButton(container) {
    const button = document.getElementById('stage-progresser');
    if (!button) return;

    button.style.display = 'none'; // Initially hidden until game starts

    const maxStage = STAGE_LABELS.length - 1;

    button.addEventListener('click', async () => {
        try {
            // Prevent spam-clicking
            button.style.pointerEvents = 'none';
            button.style.opacity = '0.5';

            // CASE 1: We are switching between teams in the SAME stage (Local Logic)
            if (gameState.teamModeActive && gameState.tournamentRankings.length > 0) {
                const isLastTeam = gameState.currentTeamIndex >= gameState.tournamentRankings.length - 1;

                if (!isLastTeam) {
                    gameState.currentTeamIndex++;
                    updateTeamIndicator();
                    return; // Stop here, don't talk to Python yet
                }
            }

            // CASE 2: We are moving to the NEXT stage (Backend Logic)
            // This runs if teamMode is off OR if it was the last team's turn
            const response = await fetch('http://localhost:5000/api/game/advance', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const result = await response.json();
                console.log("⏩ Advanced Stage:", result);
                
                // Reset team tracking for the new stage
                gameState.currentTeamIndex = 0;
                
                // Sync the UI with Python's new state
                await fetchGameState();
            }

        } catch (error) {
            console.error("Error advancing stage:", error);
        } finally {
            // Re-enable the button
            button.style.pointerEvents = 'auto';
            button.style.opacity = '1';
            updateButtonText();
        }
    });

    updateButtonText();
}

const STAGE_LABELS = [
    'Planning',
    'Negotiating',
    'Ordering',
    'Resolving',
    'Updating'
];

function initStageIndicator(container) {

    const indicator = document.getElementById('current-stage-display');
    
    if (!indicator) return;

    indicator.style.display = 'none'; // Initially hidden until game starts
    
    updateButtonText(); // Initialize button text
}

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

// Update the team indicator based on current team
function initTeamIndicator() {
    const teamDisplay = document.getElementById('current-team-display');
    const teamNameElement = document.getElementById('team-name');
    
    if (!gameState.teamModeActive || !gameState.tournamentRankings.length) {
        if (teamDisplay) {
            teamDisplay.style.display = 'none';
        }
        return;
    }

    if (!teamDisplay || !teamNameElement) return;

    const currentTeamData = gameState.tournamentRankings[gameState.currentTeamIndex];
    if (!currentTeamData) return;

    // Update team name
    teamNameElement.textContent = currentTeamData.team;

    // Update button text
    updateButtonText();

    // Show team display
    teamDisplay.style.display = 'block';
}

// Update the stage progresser button text
function updateButtonText() {
    const button = document.getElementById('stage-progresser');
    if (!button) return;

    if (gameState.teamModeActive && gameState.tournamentRankings.length > 0) {
        const isLastTeam = gameState.currentTeamIndex >= gameState.tournamentRankings.length - 1;
        button.textContent = isLastTeam ? 'Next Stage' : 'Next Team';
    } else {
        button.textContent = 'Next Stage';
    }
}

// Enable team mode - called after tournament rankings are determined
export function configureTeams() {
    const savedResults = localStorage.getItem('tournamentResults');
    if (savedResults) {
        try {
            const results = JSON.parse(savedResults);
            if (results.tournamentRankings && Array.isArray(results.tournamentRankings)) {
                gameState.tournamentRankings = results.tournamentRankings;
                gameState.teamModeActive = true;
                gameState.currentTeamIndex = 0;
                initTeamIndicator();

                // Display game UI elements after team rankings are determined
                showGameUI();
            }
        } catch (e) {
            console.error('Error loading tournament rankings:', e);
        }
    }
}

// Populate leaderboard with team rankings
export function populateLeaderboard() {
    const savedResults = localStorage.getItem('tournamentResults');
    if (savedResults) {
        try {
            const results = JSON.parse(savedResults);
            if (results.tournamentRankings && Array.isArray(results.tournamentRankings)) {
                const leaderboardContent = document.querySelector('.leaderboard-content ol');
                if (leaderboardContent) {
                    // Clear existing content
                    leaderboardContent.innerHTML = '';
                    
                    // Populate with team rankings
                    results.tournamentRankings.forEach((team, index) => {
                        const li = document.createElement('li');
                        li.textContent = `${index + 1}. ${team.team} - ${team.score} wins`;
                        leaderboardContent.appendChild(li);
                    });
                    
                    // Show leaderboard button
                    const button = document.getElementById('leaderboard-button');
                    if (button) {
                        button.style.display = 'block';
                    }
                }
            }
        } catch (e) {
            console.error('Error populating leaderboard:', e);
        }
    }
}

// Show game UI elements (stage indicator and progresser button)
function showGameUI() {
    const stageDisplay = document.getElementById('current-stage-display');
    const progresserButton = document.getElementById('stage-progresser');

    console.log("showGameUI called. gameState.teamModeActive:", gameState.teamModeActive);
    
    if (stageDisplay) {
        stageDisplay.style.display = gameState.teamModeActive ? 'block' : 'none';
    }
    if (progresserButton) {
        progresserButton.style.display = gameState.teamModeActive ? 'block' : 'none';
    }
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