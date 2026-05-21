import * as Phaser from "phaser";
import {
    buildTeamNameLookup,
    calculatePlanningReserve,
    createZeroAllocationDraft,
    normaliseOwnerId,
    resolveOwnerName,
} from "./lib/gameState.js";

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

const planningState = {
    selectedTeamId: null,
    selectedMarketId: null,
    drafts: new Map(),
    status: null,
};

export async function fetchGameState() {
    try {
        const response = await fetch(`${API_BASE}/api/game/state`);
        if (!response.ok) {
            throw new Error("No active game found on backend");
        }

        currentBackendState = await response.json();
        syncGameStateFromBackend(currentBackendState);
        syncPlanningFromBackend(currentBackendState);
        renderLeaderboard(currentBackendState);
        renderMarketState(currentBackendState);
        renderPlanningBoard();
        updateTeamIndicator();
        updateStageIndicator();
        updateBoardNarration(currentBackendState);
        showGameUI();
        maybeNavigateToStagePage(currentBackendState);

        console.log("Backend state synced:", currentBackendState);
        return currentBackendState;
    } catch (error) {
        console.error("Failed to sync game state:", error);
        syncGameStateFromBackend(null);
        syncPlanningFromBackend(null);
        renderPlanningBoard();
        updateTeamIndicator();
        updateStageIndicator();
        updateBoardNarration(null);
        showGameUI();
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
    initPlanningBoardUI(container);
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
                (team) =>
                    `<li><strong>${escapeHtml(team.team)}</strong> - ${team.score} wins</li>`,
            )
            .join("");
        content.innerHTML = `<ol>${items}</ol>`;

        const button = document.getElementById("leaderboard-button");
        const rightPanel = document.getElementById("right-panel");
        
        if (button) {
            button.style.display = "block";
        }
        
        // Show right panel when leaderboard is populated
        if (rightPanel && gameState.teamModeActive) {
            rightPanel.classList.add('active');
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
    gameState.teamModeActive = Boolean(state?.session_uuid);

    if (!state) {
        gameState.currentTeamIndex = 0;
        gameState.tournamentRankings = [];
    }
}

function stageRouteForState(state) {
    const stageName = String(state?.current_stage || "PLAN").toUpperCase();
    if (stageName === "NEGOTIATE") {
        return "/negotiator";
    }
    if (stageName === "ORDERS") {
        return "/orders";
    }
    return "/game";
}

function maybeNavigateToStagePage(state) {
    const nextPath = stageRouteForState(state);
    if (!nextPath || window.location.pathname === nextPath || typeof window.navigate !== "function") {
        return;
    }
    window.navigate(nextPath);
}

function isPlanningStageActive() {
    return Boolean(currentBackendState) && !currentBackendState?.is_finished && gameState.currentStageName === "PLAN";
}

function getMarketEntries(state = currentBackendState) {
    return Object.entries(state?.market_state || {}).map(([marketId, market]) => ({
        marketId: Number(marketId),
        ...market,
    }));
}

function ownedMarketsForTeam(teamId, state = currentBackendState) {
    return getMarketEntries(state)
        .filter((market) => Number(market.owner || 0) === Number(teamId))
        .sort((left, right) =>
            String(left.market_name || "").localeCompare(String(right.market_name || "")),
        );
}

function findMarketEntryBySlug(slug, state = currentBackendState) {
    return getMarketEntries(state).find(
        (market) => slugifyMarketName(market.market_name) === slug,
    );
}

function getPlanningReserve(teamId) {
    const team = (currentBackendState?.teams || []).find(
        (entry) => Number(entry.team_id) === Number(teamId),
    );
    if (!team) {
        return 0;
    }

    return calculatePlanningReserve(team);
}

function getPlanningDraftForTeam(teamId) {
    const numericTeamId = Number(teamId);
    if (!planningState.drafts.has(numericTeamId)) {
        planningState.drafts.set(
            numericTeamId,
            createZeroAllocationDraft(ownedMarketsForTeam(numericTeamId)),
        );
    }
    return planningState.drafts.get(numericTeamId);
}

function getPlanningDraftSum(teamId) {
    return Array.from(getPlanningDraftForTeam(teamId)?.values() || []).reduce(
        (sum, value) => sum + Number(value || 0),
        0,
    );
}

function getPlanningRemaining(teamId) {
    return getPlanningReserve(teamId) - getPlanningDraftSum(teamId);
}

function getSelectedPlanningMarket() {
    const selectedTeamId = Number(planningState.selectedTeamId);
    return ownedMarketsForTeam(selectedTeamId).find(
        (market) => Number(market.marketId) === Number(planningState.selectedMarketId),
    );
}

function syncPlanningFromBackend(state) {
    if (!state) {
        planningState.selectedTeamId = null;
        planningState.selectedMarketId = null;
        planningState.drafts = new Map();
        planningState.status = null;
        return;
    }

    const nextDrafts = new Map();
    (state.teams || []).forEach((team) => {
        nextDrafts.set(
            Number(team.team_id),
            createZeroAllocationDraft(ownedMarketsForTeam(team.team_id, state)),
        );
    });
    planningState.drafts = nextDrafts;

    const fallbackTeamId = Number(state.current_team_turn || state.teams?.[0]?.team_id || 0);
    if (!nextDrafts.has(Number(planningState.selectedTeamId))) {
        planningState.selectedTeamId = nextDrafts.has(fallbackTeamId)
            ? fallbackTeamId
            : Number(state.teams?.[0]?.team_id || 0);
    }

    const selectedOwnedMarkets = ownedMarketsForTeam(planningState.selectedTeamId, state);
    if (
        !selectedOwnedMarkets.some(
            (market) => Number(market.marketId) === Number(planningState.selectedMarketId),
        )
    ) {
        planningState.selectedMarketId = selectedOwnedMarkets[0]?.marketId ?? null;
    }

    if (!isPlanningStageActive()) {
        planningState.status = null;
    }
}

function setPlanningStatus(message, variant = "success") {
    planningState.status = { message, variant };
}

function clearPlanningStatus() {
    planningState.status = null;
}

function selectPlanningTeam(teamId) {
    planningState.selectedTeamId = Number(teamId);
    const teamMarkets = ownedMarketsForTeam(planningState.selectedTeamId);
    if (
        !teamMarkets.some(
            (market) => Number(market.marketId) === Number(planningState.selectedMarketId),
        )
    ) {
        planningState.selectedMarketId = teamMarkets[0]?.marketId ?? null;
    }
    clearPlanningStatus();
    renderPlanningBoard();
}

function selectPlanningMarket(marketId) {
    planningState.selectedMarketId = Number(marketId);
    clearPlanningStatus();
    renderPlanningBoard();
}

function adjustPlanningAllocation(delta) {
    const selectedMarket = getSelectedPlanningMarket();
    if (!selectedMarket) {
        setPlanningStatus("Select one of the team's owned markets first.", "error");
        renderPlanningBoard();
        return;
    }

    const teamId = Number(planningState.selectedTeamId);
    const draft = getPlanningDraftForTeam(teamId);
    const current = Number(draft.get(Number(selectedMarket.marketId)) || 0);
    const nextValue = current + delta;

    if (nextValue < 0) {
        return;
    }

    if (delta > 0 && getPlanningRemaining(teamId) <= 0) {
        return;
    }

    draft.set(Number(selectedMarket.marketId), nextValue);
    clearPlanningStatus();
    renderPlanningBoard();
}

async function submitPlanningAllocations() {
    const selectedTeamId = Number(planningState.selectedTeamId);
    if (!selectedTeamId) {
        setPlanningStatus("Choose a team before saving allocations.", "error");
        renderPlanningBoard();
        return;
    }

    if (getPlanningRemaining(selectedTeamId) < 0) {
        setPlanningStatus("This draft overspends the available IP pool.", "error");
        renderPlanningBoard();
        return;
    }

    const saveButton = document.getElementById("planning-board-save");
    const allocations = Array.from(getPlanningDraftForTeam(selectedTeamId)?.entries() || [])
        .filter(([, value]) => Number(value) > 0)
        .map(([marketId, value]) => ({
            market_id: Number(marketId),
            ip_allocated: Number(value),
        }));

    try {
        if (saveButton) {
            saveButton.disabled = true;
        }

        const response = await fetch(`${API_BASE}/api/game/plan-allocation`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                team_id: selectedTeamId,
                allocations,
            }),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(payload?.error || payload?.message || "Could not save allocations.");
        }

        currentBackendState = payload.game_state || payload;
        syncGameStateFromBackend(currentBackendState);
        syncPlanningFromBackend(currentBackendState);
        setPlanningStatus("Planning allocations saved.", "success");
        renderLeaderboard(currentBackendState);
        renderMarketState(currentBackendState);
        renderPlanningBoard();
        updateStageIndicator();
    } catch (error) {
        setPlanningStatus(error.message || "Could not save allocations.", "error");
        renderPlanningBoard();
    } finally {
        if (saveButton) {
            saveButton.disabled = false;
        }
    }
}

function updatePlanningTerritoryClasses() {
    const buttons = document.querySelectorAll(".territory-button");
    const planningActive = isPlanningStageActive();
    const selectedTeamId = Number(planningState.selectedTeamId);
    const selectedMarketId = Number(planningState.selectedMarketId);

    buttons.forEach((button) => {
        button.classList.remove("planning-selectable", "planning-selected");
        if (!planningActive) {
            return;
        }

        const market = findMarketEntryBySlug(button.dataset.territory);
        if (!market) {
            return;
        }

        let boxShadow = market.colour ? `0 0 0 3px ${market.colour}` : "";
        if (Number(market.owner || 0) === selectedTeamId) {
            button.classList.add("planning-selectable");
            boxShadow = `${boxShadow ? `${boxShadow}, ` : ""}0 0 0 6px rgba(238, 103, 43, 0.18)`;
        }

        if (Number(market.marketId) === selectedMarketId) {
            button.classList.add("planning-selected");
            boxShadow = `${boxShadow ? `${boxShadow}, ` : ""}0 0 0 9px rgba(70, 112, 150, 0.24)`;
        }

        button.style.boxShadow = boxShadow;
    });
}

function renderPlanningBoard() {
    const panel = document.getElementById("planning-board-panel");
    const tabs = document.getElementById("planning-board-team-tabs");
    const status = document.getElementById("planning-board-status");
    const remaining = document.getElementById("planning-board-remaining-value");
    const copy = document.getElementById("planning-board-copy");
    const marketName = document.getElementById("planning-board-market-name");
    const marketMeta = document.getElementById("planning-board-market-meta");
    const marketAllocation = document.getElementById("planning-board-market-allocation");
    const marketList = document.getElementById("planning-board-market-list");
    const decrementButton = document.getElementById("planning-board-decrement");
    const incrementButton = document.getElementById("planning-board-increment");

    if (
        !panel ||
        !tabs ||
        !status ||
        !remaining ||
        !copy ||
        !marketName ||
        !marketMeta ||
        !marketAllocation ||
        !marketList ||
        !decrementButton ||
        !incrementButton
    ) {
        return;
    }

    if (!isPlanningStageActive()) {
        panel.classList.add("hidden");
        updatePlanningTerritoryClasses();
        return;
    }

    panel.classList.remove("hidden");

    const teams = currentBackendState?.teams || [];
    const selectedTeamId = Number(planningState.selectedTeamId);
    const selectedTeam = teams.find((team) => Number(team.team_id) === selectedTeamId);
    const selectedTeamMarkets = ownedMarketsForTeam(selectedTeamId);
    const selectedMarket = getSelectedPlanningMarket();
    const remainingIp = Math.max(0, getPlanningRemaining(selectedTeamId));

    copy.textContent = selectedTeam
        ? `Round ${currentBackendState?.current_round || 1} planning is open. Click one of ${selectedTeam.team_name}'s owned markets on the board, then use the controls below.`
        : "Pick a team, click one of its markets on the board, then use the controls below.";

    tabs.innerHTML = teams
        .map((team) => `
            <button class="planning-board-team-tab${Number(team.team_id) === selectedTeamId ? " is-active" : ""}" data-planning-team-id="${team.team_id}" type="button">
                <span class="planning-board-team-chip" style="background:${escapeHtml(team.colour || "#467096")}">${escapeHtml(
                    String(team.team_name || "T")
                        .split(" ")
                        .map((part) => part[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase(),
                )}</span>
                <span class="planning-board-team-copy">
                    <strong>${escapeHtml(team.team_name)}</strong>
                    <span>${escapeHtml(String(team.ip ?? 0))} reserve IP</span>
                </span>
            </button>
        `)
        .join("");

    remaining.textContent = String(remainingIp);

    if (planningState.status?.message) {
        status.classList.remove("hidden");
        status.innerHTML = `
            <div class="planning-board-status-card is-${escapeHtml(planningState.status.variant || "success")}">
                ${escapeHtml(planningState.status.message)}
            </div>
        `;
    } else {
        status.classList.add("hidden");
        status.innerHTML = "";
    }

    if (selectedMarket) {
        const draftValue = Number(
            getPlanningDraftForTeam(selectedTeamId)?.get(Number(selectedMarket.marketId)) || 0,
        );
        marketName.textContent = selectedMarket.market_name;
        marketMeta.textContent = `${toTitleCase(selectedMarket.size || "market")} market | ${Number(selectedMarket.allocated_ip || 0)} already saved`;
        marketAllocation.textContent = String(draftValue);
    } else {
        marketName.textContent = "Select a market";
        marketMeta.textContent = "Click one of the selected team's owned territories.";
        marketAllocation.textContent = "0";
    }

    marketList.innerHTML = selectedTeamMarkets.length
        ? selectedTeamMarkets
              .map((market) => {
                  const draftValue = Number(
                      getPlanningDraftForTeam(selectedTeamId)?.get(Number(market.marketId)) || 0,
                  );
                  return `
                    <button class="planning-board-market-item${Number(market.marketId) === Number(planningState.selectedMarketId) ? " is-active" : ""}" data-planning-market-id="${market.marketId}" type="button">
                        <span>
                            <strong>${escapeHtml(market.market_name)}</strong>
                            <span>${escapeHtml(toTitleCase(market.size || "market"))}</span>
                        </span>
                        <span class="planning-board-market-value">+${escapeHtml(String(draftValue))} IP</span>
                    </button>
                  `;
              })
              .join("")
        : `<div class="planning-board-status-card is-error">This team does not own any markets yet.</div>`;

    decrementButton.disabled = !selectedMarket || Number(marketAllocation.textContent || 0) <= 0;
    incrementButton.disabled = !selectedMarket || remainingIp <= 0;

    updatePlanningTerritoryClasses();
}

function initPlanningBoardUI() {
    const panel = document.getElementById("planning-board-panel");
    const tabs = document.getElementById("planning-board-team-tabs");
    const marketList = document.getElementById("planning-board-market-list");
    const decrementButton = document.getElementById("planning-board-decrement");
    const incrementButton = document.getElementById("planning-board-increment");
    const resetButton = document.getElementById("planning-board-reset");
    const saveButton = document.getElementById("planning-board-save");

    if (
        !panel ||
        !tabs ||
        !marketList ||
        !decrementButton ||
        !incrementButton ||
        !resetButton ||
        !saveButton
    ) {
        return;
    }

    tabs.addEventListener("click", (event) => {
        const button = event.target.closest("[data-planning-team-id]");
        if (!button) {
            return;
        }
        selectPlanningTeam(button.dataset.planningTeamId);
    });

    marketList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-planning-market-id]");
        if (!button) {
            return;
        }
        selectPlanningMarket(button.dataset.planningMarketId);
    });

    decrementButton.addEventListener("click", () => {
        adjustPlanningAllocation(-1);
    });

    incrementButton.addEventListener("click", () => {
        adjustPlanningAllocation(1);
    });

    resetButton.addEventListener("click", () => {
        const selectedTeamId = Number(planningState.selectedTeamId);
        planningState.drafts.set(
            selectedTeamId,
            createZeroAllocationDraft(ownedMarketsForTeam(selectedTeamId)),
        );
        clearPlanningStatus();
        renderPlanningBoard();
    });

    saveButton.addEventListener("click", () => {
        submitPlanningAllocations();
    });
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
            const market = findMarketEntryBySlug(button.dataset.territory);
            if (isPlanningStageActive() && market) {
                if (Number(market.owner || 0) === Number(planningState.selectedTeamId)) {
                    selectPlanningMarket(market.marketId);
                } else {
                    const selectedTeam = (currentBackendState?.teams || []).find(
                        (team) => Number(team.team_id) === Number(planningState.selectedTeamId),
                    );
                    setPlanningStatus(
                        selectedTeam
                            ? `Select one of ${selectedTeam.team_name}'s owned markets to allocate IP.`
                            : "Select a team first, then click one of its owned markets.",
                        "error",
                    );
                    renderPlanningBoard();
                }
                return;
            }

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
            const forceAdvance = gameState.currentStageName !== "PLAN";

            const response = await fetch(`${API_BASE}/api/game/advance`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force: forceAdvance }),
            });

            const result = await response.json().catch(() => ({}));
            console.log("Advanced stage:", result);

            if (!response.ok) {
                throw new Error(result?.error || result?.message || "Could not advance the stage.");
            }

            if (result?.game_state) {
                currentBackendState = result.game_state;
                syncGameStateFromBackend(currentBackendState);
                syncPlanningFromBackend(currentBackendState);
                renderLeaderboard(currentBackendState);
                renderMarketState(currentBackendState);
                renderPlanningBoard();
                updateTeamIndicator();
                updateStageIndicator();
                maybeNavigateToStagePage(currentBackendState);
            } else {
                await fetchGameState();
            }
        } catch (error) {
            console.error("Error advancing stage:", error);
            if (isPlanningStageActive()) {
                setPlanningStatus(error.message || "Could not advance the stage yet.", "error");
                renderPlanningBoard();
            } else {
                window.alert(error.message || "Could not advance the stage yet.");
            }
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
    const teamNameById = buildTeamNameLookup(state?.teams || []);

    Object.entries(marketState).forEach(([marketId, market]) => {
        const numericMarketId = Number(marketId);
        const slug = slugifyMarketName(market.market_name);
        const button = document.querySelector(
            `.territory-button[data-territory="${slug}"]`,
        );

        if (!button) return;

        const ownerId = normaliseOwnerId(market.owner);
        const ownerName = resolveOwnerName(market, ownerId, teamNameById);
        const colour = market.colour || "";
        const allocation = Number(market.allocated_ip || 0);
        const buttonTitle = button.querySelector("h3");
        const buttonMeta = button.querySelector("p");
        let allocationBadge = button.querySelector(".territory-ip-badge");

        if (buttonTitle) {
            buttonTitle.textContent = market.market_name;
        }

        if (buttonMeta) {
            const statusText = ownerName ? `Owned by ${ownerName}` : "Uncaptured";
            const sizeText = market.size ? ` | ${toTitleCase(market.size)}` : "";
            const allocationText = allocation > 0 ? ` | ${allocation} IP allocated` : "";
            buttonMeta.textContent = `${statusText}${sizeText}${allocationText}`;
        }

        button.dataset.marketId = String(numericMarketId);
        button.style.borderColor = colour || "";
        button.style.boxShadow = colour ? `0 0 0 3px ${colour}` : "";

        if (allocation > 0) {
            if (!allocationBadge) {
                allocationBadge = document.createElement("span");
                allocationBadge.className = "territory-ip-badge";
                button.appendChild(allocationBadge);
            }
            allocationBadge.textContent = `${allocation} IP`;
        } else if (allocationBadge) {
            allocationBadge.remove();
        }

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

    updatePlanningTerritoryClasses();
}

function updateBoardNarration(state) {
    const container = document.getElementById("AI-container");
    const text = document.getElementById("AI-text");
    const button = document.getElementById("AI-confirm");

    if (!container || !text || !button) {
        return;
    }

    if (!state?.session_uuid) {
        container.style.display = "";
        return;
    }

    const stageGuidance = {
        PLAN: "Planning is live on the board. Pick a team in the panel, allocate IP to owned markets, save each team, then open negotiation.",
        NEGOTIATE: "Negotiation is now active. Use the negotiation page to save each team's public move and locked move.",
        ORDERS: "Orders have been locked. Open the reveal page to compare each team's stated intent with what they actually chose.",
        RESOLVE: "The round is in resolution. Continue to finish the conflicts and move into the update phase.",
        UPDATE: "Round updates are ready. Review the board, then start the next round when you are ready.",
    };

    text.textContent = stageGuidance[String(state.current_stage || "PLAN").toUpperCase()] || stageGuidance.PLAN;

    const newButton = button.cloneNode(true);
    button.parentNode.replaceChild(newButton, button);
    newButton.addEventListener("click", () => {
        container.style.display = "none";
    });
}

// Initialize team info button
function initTeamInfoButton() {
    const teamInfoButton = document.getElementById("team-info-button");
    const teamDisplay = document.getElementById("current-team-display");
    const closeButton = document.getElementById("close-team-display");
    
    if (!teamInfoButton || !teamDisplay) return;
    
    // Remove any existing event listeners to prevent duplicates
    const newButton = teamInfoButton.cloneNode(true);
    teamInfoButton.parentNode.replaceChild(newButton, teamInfoButton);
    
    const updatedButton = document.getElementById("team-info-button");
    const updatedCloseButton = document.getElementById("close-team-display");
    
    // Click handler for pinning/unpinning
    updatedButton.addEventListener("click", (event) => {
        event.stopPropagation();
        
        if (teamDisplay.classList.contains("pinned")) {
            // Unpin
            teamDisplay.classList.remove("pinned");
            if (updatedCloseButton) {
                updatedCloseButton.style.display = "none";
            }
        } else {
            // Pin and show
            teamDisplay.classList.add("pinned");
            if (updatedCloseButton) {
                updatedCloseButton.style.display = "flex";
            }
        }
    });
    
    // Close button handler
    if (updatedCloseButton) {
        updatedCloseButton.addEventListener("click", (event) => {
            event.stopPropagation();
            teamDisplay.classList.remove("pinned");
            updatedCloseButton.style.display = "none";
        });
    }
    
    // Prevent mouseleave from hiding pinned display
    const container = document.getElementById("team-info-container");
    if (container) {
        container.addEventListener("mouseleave", () => {
            if (!teamDisplay.classList.contains("pinned")) {
                teamDisplay.style.display = "none";
            }
        });
        
        container.addEventListener("mouseenter", () => {
            if (!teamDisplay.classList.contains("pinned")) {
                teamDisplay.style.display = "block";
            }
        });
    }
}

// Update the team indicator based on current team
function updateTeamIndicator() {
    const teamDisplay = document.getElementById("current-team-display");
    const teamNameElement = document.getElementById("team-name");
    const teamActionsList = document.getElementById("current-team-display-list");
    const rightPanel = document.getElementById("right-panel");
    const closeButton = document.getElementById("close-team-display");
    if (!teamDisplay || !teamNameElement || !teamActionsList) return;

    if (!currentBackendState || currentBackendState?.is_finished) {
        teamDisplay.classList.remove("pinned");
        teamDisplay.style.display = "none";
        if (closeButton) closeButton.style.display = "none";
        if (rightPanel) rightPanel.classList.remove("active");
        return;
    }

    const teams = currentBackendState.teams || [];
    const selectedTeam =
        teams.find((team) => Number(team.team_id) === Number(planningState.selectedTeamId)) ||
        teams.find((team) => Number(team.team_id) === Number(currentBackendState.current_team_turn));

    if (!selectedTeam) {
        teamDisplay.style.display = "none";
        return;
    }

    const stageHints = {
        PLAN: [
            "Allocate IP on owned markets",
            "Save each team's planning draft",
        ],
        RESOLVE: [
            "Conflicts are being resolved",
            "Advance to update when you are ready",
        ],
        UPDATE: [
            "Review the updated leaderboard",
            "Start the next round when ready",
        ],
    };

    const hints = stageHints[gameState.currentStageName] || [];
    teamNameElement.textContent = selectedTeam.team_name;
    teamActionsList.innerHTML = hints.map((hint) => `<li>${escapeHtml(hint)}</li>`).join("");
    if (rightPanel) rightPanel.classList.add("active");

    if (teamDisplay.classList.contains("pinned")) {
        teamDisplay.style.display = "block";
    } else {
        teamDisplay.style.display = hints.length ? "block" : "none";
    }
}

function updateButtonText() {
    const button = document.getElementById("stage-progresser");
    if (!button) return;

    if (currentBackendState?.is_finished) {
        button.textContent = "Game Complete";
        return;
    }

    if (gameState.currentStageName === "PLAN") {
        button.textContent = "Open Negotiation";
        return;
    }

    if (gameState.currentStageName === "RESOLVE") {
        button.textContent = "Finish Resolution";
        return;
    }

    if (gameState.currentStageName === "UPDATE") {
        button.textContent = "Start Next Round";
        return;
    }

    button.textContent = "Continue";
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
    const rightPanel = document.getElementById('right-panel');
    
    console.log("showGameUI called. gameState.teamModeActive:", gameState.teamModeActive);
    
    if (stageDisplay) {
        stageDisplay.style.display = gameState.teamModeActive ? 'block' : 'none';
    }
    if (progresserButton) {
        progresserButton.style.display = gameState.teamModeActive ? 'block' : 'none';
    }
    if (rightPanel) {
        if (gameState.teamModeActive) {
            rightPanel.classList.add('active');
            // Initialize team info button when game starts
            initTeamInfoButton();
        } else {
            rightPanel.classList.remove('active');
        }
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
