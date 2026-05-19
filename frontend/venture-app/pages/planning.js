const API_BASE =
    window.VENTURE_API_BASE ||
    import.meta.env.VITE_VENTURE_API_BASE ||
    "http://localhost:5000";

const TEAM_COLOURS = ["#EE672B", "#467096", "#2A9D8F", "#D62839", "#7B2CBF", "#F4A261"];

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

function teamInitials(name) {
    return String(name || "")
        .split(" ")
        .filter(Boolean)
        .map((part) => part[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();
}

function buildFallbackState() {
    try {
        const config = JSON.parse(localStorage.getItem("ventureGameConfig") || "{}");
        const teamNames = Array.isArray(config.teamNames) ? config.teamNames.filter(Boolean) : [];
        const teams = teamNames.map((name, index) => ({
            team_id: index + 1,
            team_name: name,
            colour: config.teamColours?.[index] || TEAM_COLOURS[index % TEAM_COLOURS.length],
            ip: 0,
            is_ai: false
        }));

        return {
            current_stage: "PLAN",
            current_round: 1,
            teams,
            market_state: {},
            current_team_turn: teams[0]?.team_id ?? null
        };
    } catch {
        return {
            current_stage: "PLAN",
            current_round: 1,
            teams: [],
            market_state: {},
            current_team_turn: null
        };
    }
}

async function fetchPlanningState() {
    const response = await fetch(`${API_BASE}/api/game/state`);
    if (!response.ok) {
        throw new Error(`Unable to load planning state (${response.status})`);
    }
    return response.json();
}

async function submitPlanAllocations(teamId, allocations) {
    const response = await fetch(`${API_BASE}/api/game/plan-allocation`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            team_id: teamId,
            allocations
        })
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload?.error || payload?.message || "Unable to save planning allocations.");
    }

    return payload.game_state || payload;
}

function ownedMarketsForTeam(state, teamId) {
    return Object.entries(state.market_state || {})
        .map(([marketId, market]) => ({ marketId: Number(marketId), ...market }))
        .filter((market) => Number(market.owner || 0) === Number(teamId))
        .sort((left, right) => String(left.market_name || "").localeCompare(String(right.market_name || "")));
}

export function initPlanningPage() {
    const elements = {
        tabs: document.getElementById("planning-team-tabs"),
        remaining: document.getElementById("planning-ip-remaining"),
        message: document.getElementById("planning-stage-message"),
        grid: document.getElementById("planning-grid"),
        status: document.getElementById("planning-status"),
        empty: document.getElementById("planning-empty"),
        emptyCopy: document.getElementById("planning-empty-copy"),
        refreshButton: document.getElementById("planning-refresh-btn"),
        backButton: document.getElementById("planning-back-btn"),
        resetButton: document.getElementById("planning-reset-btn"),
        submitButton: document.getElementById("planning-submit-btn")
    };

    if (!elements.tabs || !elements.grid || !elements.submitButton) {
        return null;
    }

    let disposed = false;
    let state = buildFallbackState();
    let selectedTeamId = null;
    let draftAllocations = new Map();

    function reserveForTeam(teamId) {
        const team = (state.teams || []).find((entry) => Number(entry.team_id) === Number(teamId));
        if (!team) {
            return 0;
        }

        const currentOwnedMarkets = ownedMarketsForTeam(state, teamId);
        const alreadyAllocated = currentOwnedMarkets.reduce(
            (sum, market) => sum + Number(market.allocated_ip || 0),
            0
        );
        return Number(team.ip || 0) + alreadyAllocated;
    }

    function currentDraftSum() {
        return Array.from(draftAllocations.values()).reduce((sum, value) => sum + value, 0);
    }

    function ipRemaining() {
        return reserveForTeam(selectedTeamId) - currentDraftSum();
    }

    function setStatus(message, variant = "success") {
        elements.status.classList.remove("hidden");
        elements.status.innerHTML = `
            <div class="planning-status-card is-${escapeHtml(variant)}">
                ${escapeHtml(message)}
            </div>
        `;
    }

    function clearStatus() {
        elements.status.classList.add("hidden");
        elements.status.innerHTML = "";
    }

    function syncDraftToSelectedTeam() {
        draftAllocations = new Map();
        ownedMarketsForTeam(state, selectedTeamId).forEach((market) => {
            draftAllocations.set(Number(market.marketId), Number(market.allocated_ip || 0));
        });
    }

    function renderTabs() {
        elements.tabs.innerHTML = "";
        const teams = state.teams || [];

        teams.forEach((team) => {
            const isActive = Number(team.team_id) === Number(selectedTeamId);
            const button = document.createElement("button");
            button.type = "button";
            button.className = `planning-team-tab${isActive ? " is-active" : ""}`;
            button.dataset.teamId = String(team.team_id);
            button.innerHTML = `
                <span class="planning-team-chip" style="background:${escapeHtml(team.colour || TEAM_COLOURS[0])}">${escapeHtml(teamInitials(team.team_name))}</span>
                <span class="planning-team-tab-copy">
                    <strong>${escapeHtml(team.team_name)}</strong>
                    <span>${escapeHtml(String(team.ip ?? 0))} reserve IP</span>
                </span>
            `;
            elements.tabs.appendChild(button);
        });
    }

    function renderGrid() {
        const team = (state.teams || []).find((entry) => Number(entry.team_id) === Number(selectedTeamId));
        const markets = ownedMarketsForTeam(state, selectedTeamId);

        elements.message.textContent = state.current_stage === "PLAN"
            ? `Round ${state.current_round} planning is open. Pick a team, tap plus or minus, and save before negotiation begins.`
            : `The game is currently in ${state.current_stage}. You can still review allocations here, but the live planning stage has passed.`;

        elements.remaining.textContent = String(Math.max(0, ipRemaining()));

        if (!markets.length) {
            elements.grid.innerHTML = "";
            elements.empty.classList.remove("hidden");
            elements.emptyCopy.textContent = team
                ? `${team.team_name} does not own any markets yet, so there is nothing to allocate.`
                : "No team is selected.";
            return;
        }

        elements.empty.classList.add("hidden");

        elements.grid.innerHTML = markets.map((market, index) => {
            const draftValue = draftAllocations.get(Number(market.marketId)) || 0;
            return `
                <article class="planning-market-card" style="--card-delay:${index * 80}ms;">
                    <div>
                        <div class="planning-market-top">
                            <div>
                                <h2>${escapeHtml(market.market_name || `Market ${market.marketId}`)}</h2>
                                <p>${escapeHtml(String(market.marketId))} &middot; owned by ${escapeHtml(team?.team_name || "team")}</p>
                            </div>
                            <span class="planning-market-size">${escapeHtml(market.size || "Market")}</span>
                        </div>

                        <div class="planning-allocation-pill">
                            <div class="planning-allocation-value">
                                <strong>${escapeHtml(String(draftValue))}</strong>
                                <span>allocated IP</span>
                            </div>
                        </div>
                    </div>

                    <div>
                        <div class="planning-controls">
                            <button class="planning-step-btn" data-action="decrement" data-market-id="${market.marketId}" type="button" ${draftValue <= 0 ? "disabled" : ""}>-</button>
                            <button class="planning-step-btn" data-action="increment" data-market-id="${market.marketId}" type="button" ${ipRemaining() <= 0 ? "disabled" : ""}>+</button>
                        </div>
                        <div class="planning-controls-note">
                            ${escapeHtml(String(market.allocated_ip || 0))} currently saved on this market
                        </div>
                    </div>
                </article>
            `;
        }).join("");
    }

    function render() {
        renderTabs();
        renderGrid();
    }

    function selectTeam(teamId) {
        selectedTeamId = Number(teamId);
        syncDraftToSelectedTeam();
        clearStatus();
        render();
    }

    async function refreshState(showMessage = false) {
        try {
            const nextState = await fetchPlanningState();
            if (disposed) {
                return;
            }

            state = nextState;
            if (!selectedTeamId) {
                selectedTeamId = Number(state.current_team_turn || state.teams?.[0]?.team_id || 0);
            }

            if (!(state.teams || []).some((team) => Number(team.team_id) === Number(selectedTeamId))) {
                selectedTeamId = Number(state.current_team_turn || state.teams?.[0]?.team_id || 0);
            }

            syncDraftToSelectedTeam();
            render();

            if (showMessage) {
                setStatus("Planning state refreshed.", "success");
            }
        } catch (error) {
            state = buildFallbackState();
            selectedTeamId = Number(state.current_team_turn || state.teams?.[0]?.team_id || 0);
            syncDraftToSelectedTeam();
            render();
            setStatus("Could not load live planning state. Showing local fallback only.", "error");
            console.error("Failed to load planning state:", error);
        }
    }

    function adjustAllocation(marketId, delta) {
        const numericMarketId = Number(marketId);
        const current = draftAllocations.get(numericMarketId) || 0;
        const nextValue = current + delta;

        if (nextValue < 0) {
            return;
        }

        if (delta > 0 && ipRemaining() <= 0) {
            return;
        }

        draftAllocations.set(numericMarketId, nextValue);
        clearStatus();
        renderGrid();
    }

    async function submitCurrentDraft() {
        if (!selectedTeamId) {
            setStatus("Select a team before saving allocations.", "error");
            return;
        }

        if (ipRemaining() < 0) {
            setStatus("This draft overspends the available IP pool.", "error");
            return;
        }

        const allocations = Array.from(draftAllocations.entries())
            .filter(([, ipAllocated]) => ipAllocated > 0)
            .map(([marketId, ipAllocated]) => ({
                market_id: marketId,
                ip_allocated: ipAllocated
            }));

        try {
            elements.submitButton.disabled = true;
            const nextState = await submitPlanAllocations(selectedTeamId, allocations);
            if (disposed) {
                return;
            }

            state = nextState;
            syncDraftToSelectedTeam();
            render();
            setStatus("Planning allocations saved.", "success");
        } catch (error) {
            setStatus(error.message || "Failed to save planning allocations.", "error");
        } finally {
            elements.submitButton.disabled = false;
        }
    }

    const onTabClick = (event) => {
        const button = event.target.closest("[data-team-id]");
        if (!button) {
            return;
        }
        selectTeam(button.dataset.teamId);
    };

    const onGridClick = (event) => {
        const button = event.target.closest("[data-market-id][data-action]");
        if (!button) {
            return;
        }
        adjustAllocation(button.dataset.marketId, button.dataset.action === "increment" ? 1 : -1);
    };

    const onRefresh = () => {
        clearStatus();
        refreshState(true);
    };

    const onBack = () => {
        if (typeof window.navigate === "function") {
            window.navigate("/game");
        }
    };

    const onReset = () => {
        syncDraftToSelectedTeam();
        clearStatus();
        renderGrid();
    };

    const onSubmit = () => {
        submitCurrentDraft();
    };

    elements.tabs.addEventListener("click", onTabClick);
    elements.grid.addEventListener("click", onGridClick);
    elements.refreshButton.addEventListener("click", onRefresh);
    elements.backButton.addEventListener("click", onBack);
    elements.resetButton.addEventListener("click", onReset);
    elements.submitButton.addEventListener("click", onSubmit);

    refreshState();

    return () => {
        disposed = true;
        elements.tabs.removeEventListener("click", onTabClick);
        elements.grid.removeEventListener("click", onGridClick);
        elements.refreshButton.removeEventListener("click", onRefresh);
        elements.backButton.removeEventListener("click", onBack);
        elements.resetButton.removeEventListener("click", onReset);
        elements.submitButton.removeEventListener("click", onSubmit);
    };
}
