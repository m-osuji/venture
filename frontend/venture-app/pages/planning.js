import {
    calculatePlanningReserve,
    createZeroAllocationDraft,
} from "../lib/gameState.js";

const API_BASE =
    window.VENTURE_API_BASE ||
    "https://venture-o2cx.onrender.com" ||
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

function getPlanningTeams(state) {
    const teams = state?.teams || [];
    const humanTeams = teams.filter((team) => !team?.is_ai);
    return humanTeams.length ? humanTeams : teams;
}

export function initPlanningPage() {
    // Add drag functionality to the planning panel
    function setupDraggable() {
        const planningPage = document.querySelector(".planning-page");
        if (!planningPage) return false;
        
        // Check if already has drag handle
        if (planningPage.hasAttribute('data-draggable-setup')) return true;
        
        // Add styles
        if (!document.getElementById('planning-drag-styles')) {
            const style = document.createElement('style');
            style.id = 'planning-drag-styles';
            style.textContent = `
                .planning-page {
                    position: fixed !important;
                    z-index: 10000;
                    cursor: default;
                }
                .planning-drag-header {
                    cursor: grab;
                    user-select: none;
                    padding: 12px 20px;
                    background: linear-gradient(135deg, #EE672B 0%, #D4561E 100%);
                    color: white;
                    border-top-left-radius: 30px;
                    border-top-right-radius: 30px;
                    margin: -20px -24px 20px -24px;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                }
                .planning-drag-header:active {
                    cursor: grabbing;
                }
                .planning-drag-header .drag-icon {
                    font-size: 20px;
                    letter-spacing: 2px;
                    margin-right: 10px;
                }
                .planning-drag-header .drag-title {
                    flex: 1;
                    font-weight: 600;
                }
                .planning-drag-header .planning-close-btn {
                    background: rgba(255,255,255,0.2);
                    border: none;
                    color: white;
                    font-size: 24px;
                    width: 32px;
                    height: 32px;
                    border-radius: 50%;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .planning-drag-header .planning-close-btn:hover {
                    background: rgba(255,255,255,0.4);
                }
                .planning-reopen-btn {
                    position: fixed;
                    bottom: 20px;
                    right: 20px;
                    background: linear-gradient(135deg, #EE672B 0%, #D4561E 100%);
                    color: white;
                    border: none;
                    border-radius: 50px;
                    padding: 12px 24px;
                    font-family: "Inter", sans-serif;
                    font-weight: 600;
                    cursor: pointer;
                    z-index: 9999;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.2);
                    display: none;
                }
                .planning-reopen-btn:hover {
                    transform: translateY(-2px);
                }
            `;
            document.head.appendChild(style);
        }
        
        // Save original position if not set
        if (!planningPage.style.top && !planningPage.style.left) {
            const savedPos = localStorage.getItem('planningPanelPos');
            if (savedPos) {
                try {
                    const { top, left } = JSON.parse(savedPos);
                    planningPage.style.top = top;
                    planningPage.style.left = left;
                    planningPage.style.right = 'auto';
                } catch(e) {}
            } else {
                planningPage.style.top = '100px';
                planningPage.style.right = '20px';
                planningPage.style.left = 'auto';
            }
        }
        
        // Check if header already exists
        let dragHeader = planningPage.querySelector('.planning-drag-header');
        if (!dragHeader) {
            // Create drag header
            dragHeader = document.createElement('div');
            dragHeader.className = 'planning-drag-header';
            dragHeader.innerHTML = `
                <div style="display: flex; align-items: center;">
                    <span class="drag-icon">⋮⋮</span>
                    <span class="drag-title">Planning Panel</span>
                </div>
                <button class="planning-close-btn">×</button>
            `;
            
            // Insert at the beginning of planning-page-content or planning-page
            const contentWrapper = planningPage.querySelector('.planning-page-content');
            if (contentWrapper) {
                planningPage.insertBefore(dragHeader, contentWrapper);
                // Adjust padding on content wrapper
                contentWrapper.style.paddingTop = '0';
            } else {
                // No content wrapper, wrap existing content
                const existingContent = planningPage.innerHTML;
                const newWrapper = document.createElement('div');
                newWrapper.className = 'planning-page-content';
                newWrapper.style.padding = '20px 24px';
                newWrapper.innerHTML = existingContent;
                planningPage.innerHTML = '';
                planningPage.appendChild(dragHeader);
                planningPage.appendChild(newWrapper);
            }
        }
        
        // Close button functionality
        const closeBtn = dragHeader.querySelector('.planning-close-btn');
        const reopenBtn = document.getElementById('planning-reopen-btn') || (() => {
            const btn = document.createElement('button');
            btn.id = 'planning-reopen-btn';
            btn.className = 'planning-reopen-btn';
            btn.innerHTML = '📋 Open Planning Panel';
            document.body.appendChild(btn);
            return btn;
        })();
        
        const updateVisibility = () => {
            if (planningPage.style.display === 'none') {
                reopenBtn.style.display = 'flex';
            } else {
                reopenBtn.style.display = 'none';
            }
        };
        
        if (closeBtn) {
            closeBtn.onclick = (e) => {
                e.stopPropagation();
                planningPage.style.display = 'none';
                localStorage.setItem('planningPanelClosed', 'true');
                updateVisibility();
            };
        }
        
        reopenBtn.onclick = () => {
            planningPage.style.display = 'block';
            localStorage.setItem('planningPanelClosed', 'false');
            updateVisibility();
        };
        
        const wasClosed = localStorage.getItem('planningPanelClosed') === 'true';
        if (wasClosed) {
            planningPage.style.display = 'none';
        }
        updateVisibility();
        
        // Drag functionality
        let isDragging = false;
        let startX, startY, startLeft, startTop;
        
        const onMouseDown = (e) => {
            // Don't drag if clicking close button
            if (e.target.closest('.planning-close-btn')) return;
            
            isDragging = true;
            const rect = planningPage.getBoundingClientRect();
            startLeft = rect.left;
            startTop = rect.top;
            startX = e.clientX;
            startY = e.clientY;
            
            planningPage.style.cursor = 'grabbing';
            dragHeader.style.cursor = 'grabbing';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        };
        
        const onMouseMove = (e) => {
            if (!isDragging) return;
            
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            
            let newLeft = startLeft + dx;
            let newTop = startTop + dy;
            
            // Constrain to viewport
            const rect = planningPage.getBoundingClientRect();
            newLeft = Math.max(0, Math.min(newLeft, window.innerWidth - rect.width));
            newTop = Math.max(0, Math.min(newTop, window.innerHeight - rect.height));
            
            planningPage.style.left = newLeft + 'px';
            planningPage.style.top = newTop + 'px';
            planningPage.style.right = 'auto';
            planningPage.style.bottom = 'auto';
        };
        
        const onMouseUp = () => {
            if (!isDragging) return;
            isDragging = false;
            planningPage.style.cursor = '';
            dragHeader.style.cursor = 'grab';
            document.body.style.userSelect = '';
            
            // Save position
            localStorage.setItem('planningPanelPos', JSON.stringify({
                left: planningPage.style.left,
                top: planningPage.style.top
            }));
        };
        
        dragHeader.addEventListener('mousedown', onMouseDown);
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        
        planningPage.setAttribute('data-draggable-setup', 'true');
        
        // Store cleanup
        window._cleanupPlanningDrag = () => {
            dragHeader.removeEventListener('mousedown', onMouseDown);
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        };
        
        return true;
    }
    
    // Try to setup draggable immediately
    if (document.querySelector(".planning-page")) {
        setupDraggable();
    }
    
    // Also watch for DOM changes (in case planning page is re-rendered)
    const observer = new MutationObserver(() => {
        if (document.querySelector(".planning-page") && !document.querySelector(".planning-page").hasAttribute('data-draggable-setup')) {
            setupDraggable();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    
    // Original planning functionality
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
        return calculatePlanningReserve(team);
    }

    function currentDraftSum() {
        return Array.from(draftAllocations.values()).reduce((sum, value) => sum + value, 0);
    }

    function ipRemaining() {
        return reserveForTeam(selectedTeamId) - currentDraftSum();
    }

    function setStatus(message, variant = "success") {
        if (elements.status) {
            elements.status.classList.remove("hidden");
            elements.status.innerHTML = `
                <div class="planning-status-card is-${escapeHtml(variant)}">
                    ${escapeHtml(message)}
                </div>
            `;
        }
    }

    function clearStatus() {
        if (elements.status) {
            elements.status.classList.add("hidden");
            elements.status.innerHTML = "";
        }
    }

    function syncDraftToSelectedTeam() {
        draftAllocations = createZeroAllocationDraft(ownedMarketsForTeam(state, selectedTeamId));
    }

    function renderTabs() {
        if (!elements.tabs) return;
        elements.tabs.innerHTML = "";
        const teams = getPlanningTeams(state);

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

        if (elements.message) {
            elements.message.textContent = state.current_stage === "PLAN"
                ? `Round ${state.current_round} planning is open. Pick one of the player teams, tap plus or minus, and save before negotiation begins.`
                : `The game is currently in ${state.current_stage}. You can still review allocations here, but the live planning stage has passed.`;
        }

        if (elements.remaining) {
            elements.remaining.textContent = String(Math.max(0, ipRemaining()));
        }

        if (!markets.length) {
            if (elements.grid) elements.grid.innerHTML = "";
            if (elements.empty) {
                elements.empty.classList.remove("hidden");
                if (elements.emptyCopy) {
                    elements.emptyCopy.textContent = team
                        ? `${team.team_name} does not own any markets yet, so there is nothing to allocate.`
                        : "No team is selected.";
                }
            }
            return;
        }

        if (elements.empty) elements.empty.classList.add("hidden");

        if (elements.grid) {
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
                                    <span>new IP</span>
                                </div>
                            </div>
                        </div>

                        <div>
                            <div class="planning-controls">
                                <button class="planning-step-btn" data-action="decrement" data-market-id="${market.marketId}" type="button" ${draftValue <= 0 ? "disabled" : ""}>-</button>
                                <button class="planning-step-btn" data-action="increment" data-market-id="${market.marketId}" type="button" ${ipRemaining() <= 0 ? "disabled" : ""}>+</button>
                            </div>
                            <div class="planning-controls-note">
                                ${escapeHtml(String(market.allocated_ip || 0))} already saved on this market
                            </div>
                        </div>
                    </article>
                `;
            }).join("");
        }
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
            if (disposed) return;
            
            state = nextState;
            if (!selectedTeamId) {
                const planningTeams = getPlanningTeams(state);
                selectedTeamId = Number(state.current_team_turn || planningTeams[0]?.team_id || 0);
            }
            
            if (!getPlanningTeams(state).some((team) => Number(team.team_id) === Number(selectedTeamId))) {
                const planningTeams = getPlanningTeams(state);
                selectedTeamId = Number(state.current_team_turn || planningTeams[0]?.team_id || 0);
            }
            
            syncDraftToSelectedTeam();
            render();
            
            if (showMessage) {
                setStatus("Planning state refreshed.", "success");
            }
        } catch (error) {
            state = buildFallbackState();
            const planningTeams = getPlanningTeams(state);
            selectedTeamId = Number(state.current_team_turn || planningTeams[0]?.team_id || 0);
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
        
        if (nextValue < 0) return;
        if (delta > 0 && ipRemaining() <= 0) return;
        
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
            if (elements.submitButton) elements.submitButton.disabled = true;
            const nextState = await submitPlanAllocations(selectedTeamId, allocations);
            if (disposed) return;
            
            state = nextState;
            syncDraftToSelectedTeam();
            render();
            setStatus("Planning allocations saved.", "success");
        } catch (error) {
            setStatus(error.message || "Failed to save planning allocations.", "error");
        } finally {
            if (elements.submitButton) elements.submitButton.disabled = false;
        }
    }

    const onTabClick = (event) => {
        const button = event.target.closest("[data-team-id]");
        if (!button) return;
        selectTeam(button.dataset.teamId);
    };

    const onGridClick = (event) => {
        const button = event.target.closest("[data-market-id][data-action]");
        if (!button) return;
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

    if (elements.tabs) elements.tabs.addEventListener("click", onTabClick);
    if (elements.grid) elements.grid.addEventListener("click", onGridClick);
    if (elements.refreshButton) elements.refreshButton.addEventListener("click", onRefresh);
    if (elements.backButton) elements.backButton.addEventListener("click", onBack);
    if (elements.resetButton) elements.resetButton.addEventListener("click", onReset);
    if (elements.submitButton) elements.submitButton.addEventListener("click", onSubmit);

    refreshState();

    return () => {
        disposed = true;
        if (elements.tabs) elements.tabs.removeEventListener("click", onTabClick);
        if (elements.grid) elements.grid.removeEventListener("click", onGridClick);
        if (elements.refreshButton) elements.refreshButton.removeEventListener("click", onRefresh);
        if (elements.backButton) elements.backButton.removeEventListener("click", onBack);
        if (elements.resetButton) elements.resetButton.removeEventListener("click", onReset);
        if (elements.submitButton) elements.submitButton.removeEventListener("click", onSubmit);
        
        if (window._cleanupPlanningDrag) {
            window._cleanupPlanningDrag();
        }
        
        observer.disconnect();
        
        const reopenBtn = document.getElementById("planning-reopen-btn");
        if (reopenBtn) reopenBtn.remove();
    };
}
