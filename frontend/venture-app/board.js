import * as Phaser from "phaser";

const API_BASE =
    window.VENTURE_API_BASE ||
    import.meta.env.VITE_VENTURE_API_BASE ||
    "http://localhost:5000";
const STAGE_SEQUENCE = ["PLAN", "NEGOTIATE", "ORDERS", "RESOLVE", "UPDATE"];
const STAGE_LABELS = {
    PLAN: "Planning",
    NEGOTIATE: "Negotiating",
    ORDERS: "Ordering",
    RESOLVE: "Resolving",
    UPDATE: "Updating",
};

let game = null;
let currentBackendState = null;

const gameState = {
    currentStage: 0,
    currentStageName: "PLAN",
    teamModeActive: false,
    currentTeamIndex: 0,
    tournamentRankings: [],
};

export async function fetchGameState() {
    try {
        const response = await fetch(`${API_BASE}/api/game/state`);
        if (!response.ok) {
            throw new Error("No active game found on backend");
        }

        currentBackendState = await response.json();
        syncGameStateFromBackend(currentBackendState);
        renderLeaderboard(currentBackendState);
        renderMarketState(currentBackendState);
        updateTeamIndicator();
        updateStageIndicator();

        console.log("Backend state synced:", currentBackendState);
        return currentBackendState;
    } catch (error) {
        console.error("Failed to sync game state:", error);
        syncGameStateFromBackend(null);
        updateTeamIndicator();
        updateStageIndicator();
        return null;
    }
}

export function startGame() {
    if (game) return;

    const container = document.getElementById("board-container");
    if (!container) {
        console.warn("No #board-container found. Phaser not started.");
        return;
    }

    initLeaderboardUI(container);
    initTerritoryUI(container);
    initTeamIndicatorDisplay(container);
    initStageIndicator(container);
    initStageProgressButton(container);

    const config = {
        type: Phaser.AUTO,
        width: window.innerWidth,
        height: window.innerHeight,
        parent: container,
        backgroundColor: "#ffffff",
        scale: {
            mode: Phaser.Scale.RESIZE,
            autoCenter: Phaser.Scale.CENTER_BOTH,
        },
        input: {
            mouse: {
                target: document.getElementById("board-container"),
            },
            touch: {
                target: document.getElementById("board-container"),
            },
        },
        scene: {
            preload,
            create,
            update,
        },
    };

    setTimeout(() => {
        game = new Phaser.Game(config);
    }, 50);
    console.log("Phaser game started");
}

export function stopGame() {
    if (game) {
        game.destroy(true);
        game = null;
        console.log("Phaser game destroyed");
    }
}

// Enable team mode - called after tournament rankings are determined
export function configureTeams() {
    const savedResults = localStorage.getItem("tournamentResults");
    if (!savedResults) return;

    try {
        const results = JSON.parse(savedResults);
        if (Array.isArray(results.tournamentRankings)) {
            gameState.tournamentRankings = results.tournamentRankings;
            gameState.teamModeActive = true;
            gameState.currentTeamIndex = 0;
            updateTeamIndicator();
            updateButtonText();

            // Display game UI elements after team rankings are determined
            showGameUI();
        }
    } catch (error) {
        console.error("Error loading tournament rankings:", error);
    }
}

export function populateLeaderboard() {
    const savedResults = localStorage.getItem("tournamentResults");
    if (!savedResults) return;

    try {
        const results = JSON.parse(savedResults);
        if (!Array.isArray(results.tournamentRankings)) return;

        const content = document.querySelector(".leaderboard-content");
        if (!content) return;

        const items = results.tournamentRankings
            .map(
                (team, index) =>
                    `<li><strong>${index + 1}. ${escapeHtml(team.team)}</strong> - ${team.score} wins</li>`,
            )
            .join("");
        content.innerHTML = `<ol>${items}</ol>`;

        const button = document.getElementById("leaderboard-button");
        if (button) {
            button.style.display = "block";
        }
    } catch (error) {
        console.error("Error populating leaderboard:", error);
    }
}

function syncGameStateFromBackend(state) {
    const rawStage = state?.current_stage ?? "PLAN";
    const currentStageName = String(rawStage).toUpperCase();
    const stageIndex = STAGE_SEQUENCE.indexOf(currentStageName);
    gameState.currentStageName = stageIndex >= 0 ? currentStageName : "PLAN";
    gameState.currentStage = stageIndex >= 0 ? stageIndex : 0;
}

function initLeaderboardUI(container) {
    const button = document.getElementById("leaderboard-button");
    const overlay = document.getElementById("leaderboard-overlay");

    if (!button || !overlay) return;

    container.style.position = container.style.position || "relative";
    if (!currentBackendState && !localStorage.getItem("tournamentResults")) {
        button.style.display = "none";
    }

    button.addEventListener("click", () => {
        overlay.style.display = "flex";
    });

    const closeButton = overlay.querySelector(".leaderboard-close");
    if (closeButton) {
        closeButton.addEventListener("click", () => {
            overlay.style.display = "none";
        });
    }

    overlay.addEventListener("click", (event) => {
        if (event.target === overlay) {
            overlay.style.display = "none";
        }
    });
}

function initTerritoryUI(container) {
    const buttons = document.querySelectorAll(".territory-button");
    if (!buttons.length) return;

    container.style.position = container.style.position || "relative";

    buttons.forEach((button) => {
        const overlay = button.nextElementSibling;
        if (!overlay || !overlay.classList.contains("territory-overlay")) return;

        button.addEventListener("click", () => {
            overlay.style.display = "flex";
        });

        const closeButton = overlay.querySelector(".territory-close");
        if (closeButton) {
            closeButton.addEventListener("click", () => {
                overlay.style.display = "none";
            });
        }

        overlay.addEventListener("click", (event) => {
            if (event.target === overlay) {
                overlay.style.display = "none";
            }
        });
    });
}

function initTeamIndicatorDisplay() {
    updateTeamIndicator();
}

function initStageProgressButton() {
    const button = document.getElementById("stage-progresser");
    if (!button) return;

    button.style.display = 'none'; // Initially hidden until game starts

    const maxStage = STAGE_LABELS.length - 1;

    button.addEventListener('click', async () => {
        try {
            button.style.pointerEvents = "none";
            button.style.opacity = "0.5";

            if (currentBackendState?.is_finished) {
                return;
            }

            if (
                gameState.teamModeActive &&
                gameState.tournamentRankings.length > 0 &&
                gameState.currentTeamIndex < gameState.tournamentRankings.length - 1
            ) {
                gameState.currentTeamIndex += 1;
                updateTeamIndicator();
                updateButtonText();
                return;
            }

            const response = await fetch(`${API_BASE}/api/game/advance`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force: true }),
            });

            const result = await response.json().catch(() => ({}));
            console.log("Advanced stage:", result);

            if (response.ok) {
                gameState.currentTeamIndex = 0;
                await fetchGameState();
            }
        } catch (error) {
            console.error("Error advancing stage:", error);
        } finally {
            button.style.pointerEvents = "auto";
            button.style.opacity = "1";
            updateButtonText();
        }
    });

    updateButtonText();
}

function initStageIndicator(container) {

    const indicator = document.getElementById('current-stage-display');
    
    if (!indicator) return;

    indicator.style.display = 'none'; // Initially hidden until game starts
    
    updateButtonText(); // Initialize button text
}

// Update the stage indicator based on the current stage
function updateStageIndicator() {
    const dots = document.querySelectorAll(".stage-dot");
    const lines = document.querySelectorAll(".stage-line");
    const stageText = document.querySelector("#current-stage-display p");
    const stageButton = document.getElementById("stage-progresser");

    if (stageText) {
        const roundText = currentBackendState?.current_round
            ? ` (Round ${currentBackendState.current_round})`
            : "";
        const stageLabel =
            (STAGE_LABELS[gameState.currentStageName] || "Planning") + roundText;
        stageText.textContent = currentBackendState?.is_finished
            ? `${stageLabel} - Game Finished`
            : stageLabel;
    }

    if (stageButton) {
        stageButton.disabled = Boolean(currentBackendState?.is_finished);
    }

    dots.forEach((dot, index) => {
        dot.classList.toggle("active", index <= gameState.currentStage);
    });

    lines.forEach((line, index) => {
        line.classList.toggle("active", index < gameState.currentStage);
    });

    updateButtonText();
}

function renderLeaderboard(state) {
    const content = document.querySelector(".leaderboard-content");
    if (!content) return;

    const entries = state?.is_finished
        ? state.final_leaderboard || []
        : state?.leaderboard || [];

    if (!entries.length) {
        if (gameState.teamModeActive && gameState.tournamentRankings.length) {
            populateLeaderboard();
        } else {
            content.innerHTML = "<p>No leaderboard data yet.</p>";
        }
        return;
    }

    const items = entries
        .map((entry) => {
            const ethicsText =
                state?.is_finished &&
                entry.ethical_score !== null &&
                entry.ethical_score !== undefined
                    ? ` | Ethics ${Number(entry.ethical_score).toFixed(2)}`
                    : "";
            return (
                `<li><strong>${escapeHtml(entry.team_name)}</strong> - ` +
                `IP ${entry.ip} | Markets ${entry.markets_controlled}${ethicsText}</li>`
            );
        })
        .join("");

    content.innerHTML = `<ol>${items}</ol>`;

    const button = document.getElementById("leaderboard-button");
    if (button) {
        button.style.display = "block";
    }
}

function renderMarketState(state) {
    const marketState = state?.market_state || {};
    const teamNameById = new Map(
        (state?.teams || []).map((team) => [Number(team.team_id), team.team_name]),
    );

    Object.values(marketState).forEach((market) => {
        const slug = slugifyMarketName(market.market_name);
        const button = document.querySelector(
            `.territory-button[data-territory="${slug}"]`,
        );

        if (!button) return;

        const ownerId = market.owner === null ? null : Number(market.owner);
        const ownerName = ownerId === null ? null : teamNameById.get(ownerId);
        const colour = market.colour || "";
        const buttonTitle = button.querySelector("h3");
        const buttonMeta = button.querySelector("p");

        if (buttonTitle) {
            buttonTitle.textContent = market.market_name;
        }

        if (buttonMeta) {
            const statusText = ownerName ? `Owned by ${ownerName}` : "Uncaptured";
            const sizeText = market.size ? ` | ${toTitleCase(market.size)}` : "";
            buttonMeta.textContent = `${statusText}${sizeText}`;
        }

        button.style.borderColor = colour || "";
        button.style.boxShadow = colour ? `0 0 0 3px ${colour}` : "";

        const overlay = button.nextElementSibling;
        if (!overlay || !overlay.classList.contains("territory-overlay")) return;

        const title = overlay.querySelector("h3");
        const paragraphs = overlay.querySelectorAll("p");
        const actionButton = overlay.querySelector(".territory-action-button");

        if (title) {
            title.textContent = `${market.market_name} Market`;
        }

        if (paragraphs[0]) {
            const contestedText = market.contested ? "Contested" : "Stable";
            paragraphs[0].textContent = `Owner: ${ownerName || "Neutral"} | ${contestedText}`;
        }

        if (paragraphs[1]) {
            const upgrades = (market.research_upgrades || []).length
                ? market.research_upgrades.join(", ")
                : "No research upgrades yet";
            paragraphs[1].textContent = upgrades;
        }

        if (actionButton) {
            actionButton.textContent = ownerName ? "Inspect Market" : "Contest Market";
        }
    });
}

// Update the team indicator based on current team
function updateTeamIndicator() {
    const teamDisplay = document.getElementById("current-team-display");
    const teamNameElement = document.getElementById("team-name");

    if (!gameState.teamModeActive || !gameState.tournamentRankings.length) {
        if (teamDisplay) {
            teamDisplay.style.display = "none";
        }
        return;
    }

    if (!teamDisplay || !teamNameElement) return;

    const currentTeamData = gameState.tournamentRankings[gameState.currentTeamIndex];
    if (!currentTeamData) return;

    teamNameElement.textContent = currentTeamData.team;
    teamDisplay.style.display = "block";
}

function updateButtonText() {
    const button = document.getElementById("stage-progresser");
    if (!button) return;

    if (currentBackendState?.is_finished) {
        button.textContent = "Game Complete";
        return;
    }

    if (gameState.teamModeActive && gameState.tournamentRankings.length > 0) {
        const isLastTeam = gameState.currentTeamIndex >= gameState.tournamentRankings.length - 1;
        button.textContent = isLastTeam ? "Next Stage" : "Next Team";
        return;
    }

    button.textContent = "Next Stage";
}

function slugifyMarketName(name) {
    return String(name || "")
        .toLowerCase()
        .replace(/&/g, "and")
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
}

function toTitleCase(value) {
    return String(value || "")
        .split(" ")
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
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

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function updateTerritoryButtonPositions(boardScale) {
    const territoryButtons = document.querySelectorAll(".territory-button");

    territoryButtons.forEach((territoryButton) => {
        const baseLeft = parseFloat(territoryButton.dataset.adjustedPositionLeft);
        const baseTop = parseFloat(territoryButton.dataset.adjustedPositionTop);

        if (Number.isNaN(baseLeft) || Number.isNaN(baseTop)) return;

        territoryButton.style.left = `${baseLeft * boardScale}px`;
        territoryButton.style.top = `${baseTop * boardScale}px`;
    });
}

function preload() {
    this.load.image("board", "/images/game_board.png");
    this.load.on("filecomplete-image-board", () => {
        console.log("Board image loaded successfully");
    });
    this.load.on("loaderror", (file) => {
        console.error("FAILED TO LOAD:", file.src);
    });
}

function create() {
    const board = this.add.image(0, 0, "board");

    const resize = (width, height) => {
        board.setPosition(width / 2, height / 2);

        const scaleX = width / board.width;
        const scaleY = height / board.height;
        const scale = Math.max(scaleX, scaleY);

        board.setScale(scale);
        updateTerritoryButtonPositions(scale);
    };

    resize(this.scale.width, this.scale.height);

    this.scale.on("resize", (gameSize) => {
        resize(gameSize.width, gameSize.height);
    });

    this.input.on("wheel", (pointer, gameObjects, deltaX, deltaY) => {
        window.scrollBy(0, deltaY);
    });

    this.input.on("pointerdown", (pointer) => {
        console.log(`Clicked at: ${pointer.x}, ${pointer.y}`);
    });

    fetchGameState();
}

function update() {
    // Add any information to update or any animations here.
}
