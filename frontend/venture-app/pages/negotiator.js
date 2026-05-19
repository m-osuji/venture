const API_BASE =
    window.VENTURE_API_BASE ||
    import.meta.env.VITE_VENTURE_API_BASE ||
    "http://localhost:5000";

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll("\"", "&quot;")
        .replaceAll("'", "&#39;");
}

function toIdKey(value) {
    return String(Number(value));
}

function orderedTeams(state) {
    const teams = [...(state?.teams || [])];
    const teamOrder = Array.isArray(state?.team_order) ? state.team_order.map(Number) : [];
    const orderIndex = new Map(teamOrder.map((teamId, index) => [teamId, index]));
    return teams.sort((left, right) => {
        const leftIndex = orderIndex.has(Number(left.team_id)) ? orderIndex.get(Number(left.team_id)) : Number.MAX_SAFE_INTEGER;
        const rightIndex = orderIndex.has(Number(right.team_id)) ? orderIndex.get(Number(right.team_id)) : Number.MAX_SAFE_INTEGER;
        if (leftIndex !== rightIndex) {
            return leftIndex - rightIndex;
        }
        return Number(left.team_id) - Number(right.team_id);
    });
}

function teamById(state, teamId) {
    return (state?.teams || []).find((team) => Number(team.team_id) === Number(teamId)) || null;
}

function marketEntries(state) {
    return Object.entries(state?.market_state || {}).map(([marketId, market]) => ({
        marketId: Number(marketId),
        ...market,
    }));
}

function ownedMarkets(state, teamId) {
    return marketEntries(state)
        .filter((market) => Number(market.owner || 0) === Number(teamId))
        .sort((left, right) => String(left.market_name || "").localeCompare(String(right.market_name || "")));
}

function targetMarkets(state, teamId) {
    return marketEntries(state)
        .filter((market) => Number(market.owner || 0) !== Number(teamId))
        .sort((left, right) => String(left.market_name || "").localeCompare(String(right.market_name || "")));
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

function teamColour(team, fallback = "#467096") {
    return team?.colour || fallback;
}

function blankMoveDraft(actionType = "hold") {
    return {
        action_type: actionType,
        source_market_id: "",
        target_market_id: "",
        ip_spent: actionType === "research" ? 2 : 1,
        research_option: "increase_production",
        break_alliance: false,
    };
}

function moveDraftFromMove(move) {
    const actionType = String(move?.action_type || "hold").trim().toLowerCase() || "hold";
    return {
        action_type: actionType,
        source_market_id: move?.source_market_id != null ? String(Number(move.source_market_id)) : "",
        target_market_id: move?.target_market_id != null ? String(Number(move.target_market_id)) : "",
        ip_spent: Number(move?.ip_spent || (actionType === "research" ? 2 : 1)),
        research_option: String(move?.metadata?.research_option || "increase_production"),
        break_alliance: Boolean(move?.metadata?.break_alliance),
    };
}

function defaultDraftForTeam(state, teamId) {
    const declaredMove = (state?.declared_moves?.[toIdKey(teamId)] || [])[0] || null;
    const actualMove =
        (state?.actual_moves?.[toIdKey(teamId)] || [])[0] ||
        (state?.prepared_moves?.[toIdKey(teamId)] || [])[0] ||
        null;

    return {
        declared: moveDraftFromMove(declaredMove),
        actual: moveDraftFromMove(actualMove),
        saved: Boolean(declaredMove),
    };
}

function storageKey(state) {
    return `ventureNegotiationDraft:${state?.session_uuid || "session"}:${state?.current_round || 1}`;
}

function loadDraftStore(state) {
    let parsed = {};
    try {
        parsed = JSON.parse(localStorage.getItem(storageKey(state)) || "{}");
    } catch {
        parsed = {};
    }

    const teamDrafts = parsed.teamDrafts || {};
    for (const team of orderedTeams(state)) {
        const teamKey = toIdKey(team.team_id);
        const existingDraft = teamDrafts[teamKey] || {};
        const fallbackDraft = defaultDraftForTeam(state, team.team_id);

        teamDrafts[teamKey] = {
            declared: {
                ...fallbackDraft.declared,
                ...(existingDraft.declared || {}),
            },
            actual: {
                ...fallbackDraft.actual,
                ...(existingDraft.actual || {}),
            },
            saved: Boolean(existingDraft.saved || fallbackDraft.saved),
        };
    }

    return {
        selectedTeamId: Number(parsed.selectedTeamId || orderedTeams(state)[0]?.team_id || 0),
        teamDrafts,
    };
}

function persistDraftStore(state, draftStore) {
    localStorage.setItem(storageKey(state), JSON.stringify(draftStore));
}

async function fetchNegotiationState() {
    if (typeof window.fetchBackendGameState === "function") {
        return window.fetchBackendGameState();
    }

    const response = await fetch(`${API_BASE}/api/game/state`);
    if (!response.ok) {
        return null;
    }
    return response.json();
}

function buildMarketOptions(markets, placeholder) {
    const options = [`<option value="">${escapeHtml(placeholder)}</option>`];
    markets.forEach((market) => {
        const ownerText = market.owner ? ` · ${escapeHtml(String(market.owner))}` : "";
        options.push(
            `<option value="${market.marketId}">${escapeHtml(market.market_name)} (${escapeHtml(String(market.size || "market"))}${ownerText})</option>`,
        );
    });
    return options.join("");
}

function setSelectValue(select, value) {
    const targetValue = String(value ?? "");
    const matchingOption = Array.from(select.options).some((option) => option.value === targetValue);
    select.value = matchingOption ? targetValue : "";
}

function applyMoveDraftToForm(prefix, moveDraft, state, teamId) {
    const ownMarkets = ownedMarkets(state, teamId);
    const otherMarkets = targetMarkets(state, teamId);

    const actionSelect = document.getElementById(`${prefix}-action-type`);
    const sourceSelect = document.getElementById(`${prefix}-source-market`);
    const targetSelect = document.getElementById(`${prefix}-target-market`);
    const ipInput = document.getElementById(`${prefix}-ip-spent`);
    const researchTargetSelect = document.getElementById(`${prefix}-research-market`);
    const researchOptionSelect = document.getElementById(`${prefix}-research-option`);
    const researchIpInput = document.getElementById(`${prefix}-research-ip`);
    const breakAllianceCheckbox = document.getElementById(`${prefix}-break-alliance`);

    actionSelect.value = moveDraft.action_type || "hold";
    sourceSelect.innerHTML = buildMarketOptions(ownMarkets, "Choose an owned market");
    targetSelect.innerHTML = buildMarketOptions(otherMarkets, "Choose a target market");
    researchTargetSelect.innerHTML = buildMarketOptions(ownMarkets, "Choose an owned market");

    setSelectValue(sourceSelect, moveDraft.source_market_id);
    setSelectValue(targetSelect, moveDraft.target_market_id);
    setSelectValue(researchTargetSelect, moveDraft.target_market_id);
    setSelectValue(researchOptionSelect, moveDraft.research_option || "increase_production");

    ipInput.value = String(moveDraft.ip_spent || 1);
    researchIpInput.value = String(moveDraft.ip_spent || 2);
    if (breakAllianceCheckbox) {
        breakAllianceCheckbox.checked = Boolean(moveDraft.break_alliance);
    }

    updateConditionalFields(prefix);
}

function updateConditionalFields(prefix) {
    const actionType = document.getElementById(`${prefix}-action-type`)?.value || "hold";
    const attackFields = document.getElementById(`${prefix}-attack-fields`);
    const researchFields = document.getElementById(`${prefix}-research-fields`);

    attackFields?.classList.toggle("hidden", actionType !== "attack");
    researchFields?.classList.toggle("hidden", actionType !== "research");
}

function moveDraftFromForm(prefix) {
    const actionType = document.getElementById(`${prefix}-action-type`)?.value || "hold";
    const draft = blankMoveDraft(actionType);

    if (actionType === "attack") {
        draft.source_market_id = document.getElementById(`${prefix}-source-market`)?.value || "";
        draft.target_market_id = document.getElementById(`${prefix}-target-market`)?.value || "";
        draft.ip_spent = Number(document.getElementById(`${prefix}-ip-spent`)?.value || 0);
        draft.break_alliance = Boolean(document.getElementById(`${prefix}-break-alliance`)?.checked);
    } else if (actionType === "research") {
        draft.target_market_id = document.getElementById(`${prefix}-research-market`)?.value || "";
        draft.research_option = document.getElementById(`${prefix}-research-option`)?.value || "increase_production";
        draft.ip_spent = Number(document.getElementById(`${prefix}-research-ip`)?.value || 0);
    }

    return draft;
}

function buildMovePayload(moveDraft, { allowBreakAlliance = false } = {}) {
    const actionType = String(moveDraft?.action_type || "hold").trim().toLowerCase() || "hold";

    if (actionType === "hold") {
        return [{ action_type: "hold", ip_spent: 0, metadata: {} }];
    }

    if (actionType === "attack") {
        if (!moveDraft?.source_market_id) {
            throw new Error("Attack moves need a source market.");
        }
        if (!moveDraft?.target_market_id) {
            throw new Error("Attack moves need a target market.");
        }
        if (Number(moveDraft?.ip_spent || 0) <= 0) {
            throw new Error("Attack moves must commit at least 1 IP.");
        }

        const metadata = {};
        if (allowBreakAlliance && moveDraft.break_alliance) {
            metadata.break_alliance = true;
        }

        return [
            {
                action_type: "attack",
                source_market_id: Number(moveDraft.source_market_id),
                target_market_id: Number(moveDraft.target_market_id),
                ip_spent: Number(moveDraft.ip_spent),
                metadata,
            },
        ];
    }

    if (actionType === "research") {
        if (!moveDraft?.target_market_id) {
            throw new Error("Research moves need a target market.");
        }
        if (Number(moveDraft?.ip_spent || 0) <= 0) {
            throw new Error("Research moves must commit a positive amount of IP.");
        }

        return [
            {
                action_type: "research",
                target_market_id: Number(moveDraft.target_market_id),
                ip_spent: Number(moveDraft.ip_spent),
                metadata: {
                    research_option: String(moveDraft.research_option || "increase_production"),
                },
            },
        ];
    }

    throw new Error(`Unsupported action type "${actionType}".`);
}

function setStatus(elements, message, variant) {
    if (!message) {
        elements.status.classList.add("hidden");
        elements.status.innerHTML = "";
        return;
    }

    elements.status.classList.remove("hidden");
    elements.status.innerHTML = `<div class="neg-status-card is-${escapeHtml(variant || "success")}">${escapeHtml(message)}</div>`;
}

function renderNegotiationWorkspace(state, draftStore, elements) {
    const teams = orderedTeams(state);
    if (!teams.length) {
        elements.workspace.classList.add("hidden");
        elements.empty.classList.remove("hidden");
        elements.emptyCopy.textContent = "No teams are available in the current game state yet.";
        return;
    }

    if (!teams.some((team) => Number(team.team_id) === Number(draftStore.selectedTeamId))) {
        draftStore.selectedTeamId = Number(teams[0].team_id);
    }

    persistDraftStore(state, draftStore);

    const savedCount = teams.filter((team) => Boolean(draftStore.teamDrafts[toIdKey(team.team_id)]?.saved)).length;
    const selectedTeam = teamById(state, draftStore.selectedTeamId);
    const selectedDraft = draftStore.teamDrafts[toIdKey(draftStore.selectedTeamId)] || defaultDraftForTeam(state, draftStore.selectedTeamId);
    const selectedOwnedMarkets = ownedMarkets(state, draftStore.selectedTeamId);

    elements.empty.classList.add("hidden");
    elements.workspace.classList.remove("hidden");

    elements.roundValue.textContent = String(state.current_round || 1);
    elements.savedValue.textContent = `${savedCount} / ${teams.length}`;
    elements.stageValue.textContent = String(state.current_stage || "NEGOTIATE").toUpperCase();
    elements.stageMessage.textContent = `Round ${state.current_round || 1} negotiation is live. Save every team's public move and private locked move, then reveal orders.`;

    elements.teamTabs.innerHTML = teams
        .map((team) => {
            const teamDraft = draftStore.teamDrafts[toIdKey(team.team_id)] || {};
            const saveClass = teamDraft.saved ? " is-saved" : "";
            const activeClass = Number(team.team_id) === Number(draftStore.selectedTeamId) ? " is-active" : "";
            return `
                <button class="neg-team-tab${activeClass}${saveClass}" data-team-id="${team.team_id}" type="button">
                    <span class="neg-team-emblem" style="background:${escapeHtml(teamColour(team))}">${escapeHtml(teamInitials(team.team_name))}</span>
                    <span class="neg-team-tab-copy">
                        <strong>${escapeHtml(team.team_name)}</strong>
                        <span>${escapeHtml(String(team.ip ?? 0))} reserve IP</span>
                    </span>
                </button>
            `;
        })
        .join("");

    elements.teamName.textContent = selectedTeam?.team_name || "Choose a team";
    elements.teamMeta.textContent = selectedTeam
        ? `${selectedOwnedMarkets.length} owned markets | ${Number(selectedTeam.ip ?? 0)} IP currently in reserve`
        : "Select a team tab to enter its moves.";

    elements.teamSaveBadge.textContent = selectedDraft.saved ? "Saved" : "Not saved";
    elements.teamSaveBadge.classList.toggle("is-saved", Boolean(selectedDraft.saved));

    applyMoveDraftToForm("declared", selectedDraft.declared, state, draftStore.selectedTeamId);
    applyMoveDraftToForm("actual", selectedDraft.actual, state, draftStore.selectedTeamId);
}

function collectSelectedTeamDraft(draftStore, markUnsaved = true) {
    const teamId = toIdKey(draftStore.selectedTeamId);
    draftStore.teamDrafts[teamId] = draftStore.teamDrafts[teamId] || {
        declared: blankMoveDraft("hold"),
        actual: blankMoveDraft("hold"),
        saved: false,
    };

    draftStore.teamDrafts[teamId].declared = moveDraftFromForm("declared");
    draftStore.teamDrafts[teamId].actual = moveDraftFromForm("actual");
    if (markUnsaved) {
        draftStore.teamDrafts[teamId].saved = false;
    }
}

async function postJson(url, body) {
    const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(payload?.error || payload?.message || "Request failed.");
    }
    return payload;
}

export function initNegotiatorPage() {
    const elements = {
        stageMessage: document.getElementById("negotiation-stage-message"),
        empty: document.getElementById("negotiation-empty-state"),
        emptyCopy: document.getElementById("negotiation-empty-copy"),
        workspace: document.getElementById("negotiation-workspace"),
        roundValue: document.getElementById("negotiation-round-value"),
        savedValue: document.getElementById("negotiation-saved-value"),
        stageValue: document.getElementById("negotiation-stage-value"),
        status: document.getElementById("negotiation-status"),
        teamTabs: document.getElementById("negotiation-team-tabs"),
        teamName: document.getElementById("negotiation-team-name"),
        teamMeta: document.getElementById("negotiation-team-meta"),
        teamSaveBadge: document.getElementById("negotiation-team-save-badge"),
        refreshButton: document.getElementById("negotiation-refresh-btn"),
        backButton: document.getElementById("negotiation-back-btn"),
        saveTeamButton: document.getElementById("negotiation-save-team-btn"),
        completeButton: document.getElementById("negotiation-complete-btn"),
    };

    if (!elements.stageMessage || !elements.workspace || !elements.teamTabs) {
        return null;
    }

    let disposed = false;
    let currentState = null;
    let draftStore = null;

    const inputIds = [
        "declared-action-type",
        "declared-source-market",
        "declared-target-market",
        "declared-ip-spent",
        "declared-research-market",
        "declared-research-option",
        "declared-research-ip",
        "actual-action-type",
        "actual-source-market",
        "actual-target-market",
        "actual-ip-spent",
        "actual-research-market",
        "actual-research-option",
        "actual-research-ip",
        "actual-break-alliance",
    ];

    function render() {
        if (!currentState || !draftStore) {
            elements.workspace.classList.add("hidden");
            elements.empty.classList.remove("hidden");
            elements.emptyCopy.textContent = "No active game state is available yet. Start a game first, then return to negotiation.";
            return;
        }

        renderNegotiationWorkspace(currentState, draftStore, elements);
    }

    function syncCurrentInputs(markUnsaved = true) {
        if (!draftStore) {
            return;
        }
        collectSelectedTeamDraft(draftStore, markUnsaved);
        persistDraftStore(currentState, draftStore);
    }

    async function refresh() {
        try {
            const state = await fetchNegotiationState();
            if (disposed) {
                return;
            }

            if (!state) {
                currentState = null;
                draftStore = null;
                setStatus(elements, null);
                render();
                return;
            }

            const expectedPath = typeof window.routeForGameStage === "function"
                ? window.routeForGameStage(state.current_stage)
                : null;
            if (expectedPath && expectedPath !== "/negotiator" && typeof window.navigate === "function") {
                window.navigate(expectedPath);
                return;
            }

            currentState = state;
            draftStore = loadDraftStore(state);
            setStatus(elements, null);
            render();
        } catch (error) {
            console.error("Failed to load negotiation state:", error);
            currentState = null;
            draftStore = null;
            setStatus(elements, "Could not load negotiation state. Check that the backend is running, then refresh.", "error");
            render();
        }
    }

    async function saveSelectedTeam() {
        if (!currentState || !draftStore) {
            return;
        }

        syncCurrentInputs(false);
        const teamId = Number(draftStore.selectedTeamId);
        const draft = draftStore.teamDrafts[toIdKey(teamId)];

        try {
            const declaredMoves = buildMovePayload(draft.declared);
            buildMovePayload(draft.actual, { allowBreakAlliance: true });

            elements.saveTeamButton.disabled = true;
            await postJson(`${API_BASE}/api/game/declared-moves`, {
                team_id: teamId,
                moves: declaredMoves,
            });

            draft.saved = true;
            persistDraftStore(currentState, draftStore);
            setStatus(elements, `${teamById(currentState, teamId)?.team_name || "Team"} saved for negotiation.`, "success");
            render();
        } catch (error) {
            console.error("Failed to save negotiation moves:", error);
            setStatus(elements, error.message || "Could not save this team's negotiation choices.", "error");
        } finally {
            elements.saveTeamButton.disabled = false;
        }
    }

    async function revealOrders() {
        if (!currentState || !draftStore) {
            return;
        }

        syncCurrentInputs(false);

        const teams = orderedTeams(currentState);
        const unsavedTeams = teams.filter((team) => !draftStore.teamDrafts[toIdKey(team.team_id)]?.saved);
        if (unsavedTeams.length) {
            setStatus(
                elements,
                `Save every team first. Still waiting on: ${unsavedTeams.map((team) => team.team_name).join(", ")}.`,
                "error",
            );
            render();
            return;
        }

        try {
            elements.completeButton.disabled = true;

            await postJson(`${API_BASE}/api/game/advance`, { force: false });

            for (const team of teams) {
                const teamDraft = draftStore.teamDrafts[toIdKey(team.team_id)];
                const actualMoves = buildMovePayload(teamDraft.actual, { allowBreakAlliance: true });
                await postJson(`${API_BASE}/api/game/orders`, {
                    team_id: Number(team.team_id),
                    moves: actualMoves,
                });
            }

            localStorage.removeItem(storageKey(currentState));
            if (typeof window.navigate === "function") {
                window.navigate("/orders");
            }
        } catch (error) {
            console.error("Failed to reveal orders:", error);
            setStatus(elements, error.message || "Could not move into Orders yet.", "error");
            elements.completeButton.disabled = false;
        }
    }

    const onTeamTabClick = (event) => {
        const button = event.target.closest("[data-team-id]");
        if (!button || !draftStore) {
            return;
        }

        syncCurrentInputs(false);
        draftStore.selectedTeamId = Number(button.dataset.teamId);
        persistDraftStore(currentState, draftStore);
        setStatus(elements, null);
        render();
    };

    const onFormChange = (event) => {
        const targetId = event.target?.id;
        if (!targetId || !inputIds.includes(targetId) || !draftStore) {
            return;
        }

        syncCurrentInputs(true);
        setStatus(elements, null);
        render();
    };

    const onRefreshClick = () => {
        void refresh();
    };

    const onBackClick = () => {
        if (typeof window.navigate === "function") {
            window.navigate("/game");
        }
    };

    const onSaveClick = () => {
        void saveSelectedTeam();
    };

    const onCompleteClick = () => {
        void revealOrders();
    };

    elements.teamTabs.addEventListener("click", onTeamTabClick);
    inputIds.forEach((inputId) => {
        document.getElementById(inputId)?.addEventListener("change", onFormChange);
        document.getElementById(inputId)?.addEventListener("input", onFormChange);
    });
    elements.refreshButton.addEventListener("click", onRefreshClick);
    elements.backButton.addEventListener("click", onBackClick);
    elements.saveTeamButton.addEventListener("click", onSaveClick);
    elements.completeButton.addEventListener("click", onCompleteClick);

    void refresh();

    return () => {
        disposed = true;
        elements.teamTabs.removeEventListener("click", onTeamTabClick);
        inputIds.forEach((inputId) => {
            document.getElementById(inputId)?.removeEventListener("change", onFormChange);
            document.getElementById(inputId)?.removeEventListener("input", onFormChange);
        });
        elements.refreshButton.removeEventListener("click", onRefreshClick);
        elements.backButton.removeEventListener("click", onBackClick);
        elements.saveTeamButton.removeEventListener("click", onSaveClick);
        elements.completeButton.removeEventListener("click", onCompleteClick);
    };
}
