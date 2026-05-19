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

function teamInitials(name) {
    return String(name || "")
        .split(" ")
        .filter(Boolean)
        .map((part) => part[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();
}

function marketName(marketMap, marketId) {
    if (marketId == null) {
        return "Unknown market";
    }
    return marketMap.get(Number(marketId))?.market_name || `Market ${marketId}`;
}

function moveSignature(move) {
    const researchOption = String(move?.metadata?.research_option || "").trim().toLowerCase() || null;
    return [
        String(move?.action_type || "hold"),
        Number(move?.target_market_id ?? -1),
        Number(move?.source_market_id ?? -1),
        Number(move?.ip_spent ?? 0),
        researchOption
    ].join("|");
}

function movesEquivalent(leftMoves, rightMoves) {
    if (leftMoves.length !== rightMoves.length) {
        return false;
    }

    const left = [...leftMoves].map(moveSignature).sort();
    const right = [...rightMoves].map(moveSignature).sort();
    return left.every((value, index) => value === right[index]);
}

function formatResearchOption(option) {
    const label = String(option || "")
        .replaceAll("_", " ")
        .trim();

    if (!label) {
        return "Research";
    }

    return label.charAt(0).toUpperCase() + label.slice(1);
}

function describeMove(move, marketMap) {
    const actionType = String(move?.action_type || "hold").toLowerCase();
    const ipSpent = Number(move?.ip_spent || 0);
    const sourceName = move?.source_market_id != null ? marketName(marketMap, move.source_market_id) : null;
    const targetName = move?.target_market_id != null ? marketName(marketMap, move.target_market_id) : null;

    if (actionType === "attack") {
        return {
            chipClass: "chip-attack",
            chipLabel: "Attack",
            title: targetName ? `Attacked ${targetName}` : "Attack launched",
            detail: sourceName
                ? `Committed ${ipSpent} IP from ${sourceName}.`
                : `Committed ${ipSpent} IP.`
        };
    }

    if (actionType === "defend") {
        return {
            chipClass: "chip-defend",
            chipLabel: "Defend",
            title: targetName ? `Defended ${targetName}` : "Defence order",
            detail: sourceName
                ? `Reallocated ${ipSpent} IP from ${sourceName}.`
                : `Allocated ${ipSpent} IP to defence.`
        };
    }

    if (actionType === "research") {
        return {
            chipClass: "chip-research",
            chipLabel: "Research",
            title: targetName ? `Researched ${targetName}` : "Research order",
            detail: `${formatResearchOption(move?.metadata?.research_option)} for ${ipSpent} IP.`
        };
    }

    return {
        chipClass: "chip-hold",
        chipLabel: "Hold",
        title: "Held position",
        detail: "No aggressive or research action was revealed."
    };
}

function describePlanNote(note, marketMap) {
    if (note == null || note === "") {
        return null;
    }

    if (typeof note === "string") {
        return {
            chipClass: "chip-intent",
            chipLabel: "Intent",
            title: "Planned note",
            detail: note
        };
    }

    const action = String(note.planned_action || note.action || "plan").replaceAll("_", " ");
    const marketId = note.target_market_id ?? note.market_id ?? null;
    const target = marketId != null ? marketName(marketMap, marketId) : null;

    return {
        chipClass: "chip-intent",
        chipLabel: "Intent",
        title: `${action.charAt(0).toUpperCase()}${action.slice(1)}${target ? ` ${target}` : ""}`,
        detail: target ? `Planned around ${target}.` : "No declared move list was recorded."
    };
}

function buildBetrayalSummary(teamId, actualMoves, state) {
    const activeAlliances = (state.alliances || []).filter(
        (alliance) => String(alliance.status || "active").toLowerCase() === "active" &&
            (alliance.members || []).map(Number).includes(Number(teamId))
    );

    if (!activeAlliances.length) {
        return null;
    }

    const marketState = state.market_state || {};
    const marketMap = new Map(
        Object.entries(marketState).map(([marketId, market]) => [Number(marketId), market])
    );

    const attackedAlliedMarkets = [];
    for (const move of actualMoves) {
        if (String(move.action_type || "").toLowerCase() !== "attack" || move.target_market_id == null) {
            continue;
        }

        const market = marketMap.get(Number(move.target_market_id));
        const owner = Number(market?.owner || 0);
        if (!owner) {
            continue;
        }

        const brokenAlliance = activeAlliances.find((alliance) => {
            const members = (alliance.members || []).map(Number);
            return members.includes(owner) && owner !== Number(teamId);
        });

        if (brokenAlliance) {
            attackedAlliedMarkets.push(marketName(marketMap, move.target_market_id));
        }
    }

    if (!attackedAlliedMarkets.length) {
        return null;
    }

    return attackedAlliedMarkets;
}

function buildStatusInfo(teamId, declaredMoves, actualMoves, state) {
    if (!state.move_reveal_available) {
        return {
            variant: "silent",
            label: "Awaiting Reveal",
            summary: `The game is currently in ${state.current_stage}. Locked orders have not been revealed yet.`
        };
    }

    const betrayalTargets = buildBetrayalSummary(teamId, actualMoves, state);
    if (betrayalTargets) {
        return {
            variant: "betrayal",
            label: "Alliance Broken",
            summary: `Attacked allied market${betrayalTargets.length > 1 ? "s" : ""}: ${betrayalTargets.join(", ")}.`
        };
    }

    if (!declaredMoves.length && !actualMoves.length) {
        return {
            variant: "silent",
            label: "Quiet Round",
            summary: "No declared or revealed action this round."
        };
    }

    if (declaredMoves.length && movesEquivalent(declaredMoves, actualMoves)) {
        return {
            variant: "kept",
            label: "Promise Kept",
            summary: "Declared intent matched the final locked decisions."
        };
    }

    if (!declaredMoves.length && actualMoves.length) {
        return {
            variant: "changed",
            label: "Undeclared Move",
            summary: "A real move was revealed without a matching declared move list."
        };
    }

    if (declaredMoves.length && !actualMoves.length) {
        return {
            variant: "changed",
            label: "Plan Withheld",
            summary: "A declared move existed, but no actual order was revealed."
        };
    }

    return {
        variant: "changed",
        label: "Changed Plan",
        summary: "Final decisions differed from the declared intent."
    };
}

function buildAllocations(teamId, state) {
    const entries = Object.entries(state.market_state || {})
        .map(([marketId, market]) => ({ marketId: Number(marketId), ...market }))
        .filter((market) => Number(market.owner || 0) === Number(teamId))
        .sort((left, right) => {
            const ipDifference = Number(right.allocated_ip || 0) - Number(left.allocated_ip || 0);
            if (ipDifference !== 0) {
                return ipDifference;
            }
            return String(left.market_name || "").localeCompare(String(right.market_name || ""));
        });

    const nonZero = entries.filter((market) => Number(market.allocated_ip || 0) > 0);
    return nonZero.length ? nonZero : entries.slice(0, 4);
}

function renderMoveItems(items, delayOffset = 0) {
    if (!items.length) {
        return `<div class="orders-item-empty">Nothing was revealed here for this team.</div>`;
    }

    return `<div class="orders-move-list">${items.map((item, index) => `
        <div class="orders-move-item" style="--item-delay:${delayOffset + index * 80}ms;">
            <span class="orders-chip ${escapeHtml(item.chipClass)}">${escapeHtml(item.chipLabel)}</span>
            <div class="orders-item-copy">
                <strong>${escapeHtml(item.title)}</strong>
                <span>${escapeHtml(item.detail)}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function renderAllocationItems(items, delayOffset = 0) {
    if (!items.length) {
        return `<div class="orders-item-empty">No IP allocation is visible for this team yet.</div>`;
    }

    return `<div class="orders-allocation-list">${items.map((item, index) => `
        <div class="orders-allocation-item" style="--item-delay:${delayOffset + index * 70}ms;">
            <span class="orders-chip chip-hold">${escapeHtml(item.market_name || `Market ${item.marketId}`)}</span>
            <div class="orders-item-copy">
                <strong>${escapeHtml(String(item.allocated_ip || 0))} IP allocated</strong>
                <span>${escapeHtml(item.size || "Unknown size")} market${item.contested ? " · contested" : ""}</span>
            </div>
        </div>
    `).join("")}</div>`;
}

function animateCounters(summaryRoot) {
    summaryRoot.querySelectorAll("[data-count-target]").forEach((element, index) => {
        const target = Number(element.dataset.countTarget || 0);
        const duration = 450 + index * 90;
        const startTime = performance.now();

        function tick(timestamp) {
            const elapsed = Math.min(1, (timestamp - startTime) / duration);
            const eased = 1 - Math.pow(1 - elapsed, 3);
            element.textContent = String(Math.round(target * eased));
            if (elapsed < 1) {
                requestAnimationFrame(tick);
            }
        }

        requestAnimationFrame(tick);
    });
}

function fallbackStateFromLocalStorage() {
    try {
        const config = JSON.parse(localStorage.getItem("ventureGameConfig") || "{}");
        const teamNames = Array.isArray(config.teamNames) ? config.teamNames.filter(Boolean) : [];
        const teams = teamNames.map((teamName, index) => ({
            team_id: index + 1,
            team_name: teamName,
            colour: config.teamColours?.[index] || ["#EE672B", "#467096", "#2A9D8F", "#D62839"][index % 4],
            ip: 0
        }));

        return {
            current_round: 1,
            current_stage: "ORDERS",
            move_reveal_available: false,
            teams,
            market_state: {},
            declared_moves: {},
            actual_moves: {},
            prepared_moves: {},
            plan_notes: {},
            alliances: []
        };
    } catch {
        return null;
    }
}

async function fetchOrdersState() {
    const response = await fetch(`${API_BASE}/api/game/state`);
    if (!response.ok) {
        throw new Error(`Unable to load game state (${response.status})`);
    }
    return response.json();
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

function renderOrdersPage(state, elements) {
    const teams = state.teams || [];
    const marketMap = new Map(
        Object.entries(state.market_state || {}).map(([marketId, market]) => [Number(marketId), market])
    );

    const summary = {
        revealed: state.move_reveal_available ? teams.length : 0,
        kept: 0,
        changed: 0,
        betrayal: 0
    };

    elements.message.textContent = state.move_reveal_available
        ? `Round ${state.current_round} orders are now visible. Compare each team's stated intent with what they actually locked in.`
        : `The game is currently in ${state.current_stage}. This reveal screen will populate once the round reaches Orders.`;

    if (elements.continueButton) {
        const stageName = String(state.current_stage || "").toUpperCase();
        if (stageName === "ORDERS") {
            elements.continueButton.textContent = "Resolve round";
        } else if (stageName === "RESOLVE") {
            elements.continueButton.textContent = "Finish resolution";
        } else if (stageName === "UPDATE") {
            elements.continueButton.textContent = "Return to board";
        } else if (stageName === "PLAN") {
            elements.continueButton.textContent = "Back to board";
        } else {
            elements.continueButton.textContent = "Continue";
        }

        elements.continueButton.disabled = Boolean(state.is_finished);
    }

    if (!teams.length) {
        elements.grid.innerHTML = "";
        elements.empty.classList.remove("hidden");
        elements.emptyCopy.textContent = "No active game state is available yet. Start a game first, then return to this reveal page.";
        updateSummary(summary, elements.summary);
        return;
    }

    const cards = teams.map((team, index) => {
        const teamId = Number(team.team_id);
        const declaredMoves = state.declared_moves?.[toIdKey(teamId)] || [];
        const actualMoves = (state.prepared_moves?.[toIdKey(teamId)] || state.actual_moves?.[toIdKey(teamId)] || []);
        const allocations = buildAllocations(teamId, state);
        const status = buildStatusInfo(teamId, declaredMoves, actualMoves, state);

        if (status.variant === "kept") {
            summary.kept += 1;
        } else if (status.variant === "betrayal") {
            summary.betrayal += 1;
            summary.changed += 1;
        } else if (status.variant === "changed") {
            summary.changed += 1;
        }

        const intentItems = declaredMoves.length
            ? declaredMoves.map((move) => ({
                ...describeMove(move, marketMap),
                chipClass: "chip-intent",
                chipLabel: "Intent"
            }))
            : (() => {
                const note = describePlanNote(state.plan_notes?.[toIdKey(teamId)], marketMap);
                return note ? [note] : [];
            })();

        const actualItems = actualMoves.map((move) => ({
            ...describeMove(move, marketMap),
            chipClass: "chip-actual",
            chipLabel: "Revealed"
        }));

        const marketsControlled = Object.values(state.market_state || {}).filter(
            (market) => Number(market.owner || 0) === teamId
        ).length;

        return `
            <article class="orders-team-card ${status.variant === "betrayal" ? "is-betrayal" : ""}" style="--order-delay:${index * 110}ms;">
                <div class="orders-team-top">
                    <div class="orders-team-identity">
                        <div class="orders-team-emblem" style="background:${escapeHtml(team.colour || "#467096")}">${escapeHtml(teamInitials(team.team_name))}</div>
                        <div>
                            <h2 class="orders-team-name">${escapeHtml(team.team_name)}</h2>
                            <div class="orders-team-meta">
                                <span>${escapeHtml(String(team.ip ?? 0))} IP in reserve</span>
                                <span>${escapeHtml(String(marketsControlled))} markets controlled</span>
                            </div>
                        </div>
                    </div>
                    <span class="orders-status-badge status-${escapeHtml(status.variant)}">${escapeHtml(status.label)}</span>
                </div>

                <div class="orders-card-grid">
                    <section class="orders-panel">
                        <h3 class="orders-panel-title">Allocated IP</h3>
                        ${renderAllocationItems(allocations, 80)}
                    </section>
                    <section class="orders-panel">
                        <h3 class="orders-panel-title">Stated Intent</h3>
                        ${renderMoveItems(intentItems, 110)}
                    </section>
                    <section class="orders-panel">
                        <h3 class="orders-panel-title">Revealed Decisions</h3>
                        ${renderMoveItems(actualItems, 140)}
                    </section>
                </div>

                <div class="orders-card-footer">
                    <strong>Read:</strong> ${escapeHtml(status.summary)}
                </div>
            </article>
        `;
    });

    elements.grid.innerHTML = cards.join("");
    elements.empty.classList.toggle("hidden", true);
    updateSummary(summary, elements.summary);
}

function updateSummary(summary, summaryRoot) {
    const counters = summaryRoot.querySelectorAll("[data-count-target]");
    const values = [summary.revealed, summary.kept, summary.changed, summary.betrayal];
    counters.forEach((counter, index) => {
        counter.dataset.countTarget = String(values[index] || 0);
        counter.textContent = "0";
    });
    animateCounters(summaryRoot);
}

export function initOrdersPage() {
    const elements = {
        summary: document.getElementById("orders-summary"),
        grid: document.getElementById("orders-grid"),
        message: document.getElementById("orders-stage-message"),
        empty: document.getElementById("orders-empty-state"),
        emptyCopy: document.getElementById("orders-empty-copy"),
        refreshButton: document.getElementById("orders-refresh-btn"),
        continueButton: document.getElementById("orders-continue-btn"),
        backButton: document.getElementById("orders-back-btn")
    };

    if (!elements.summary || !elements.grid || !elements.refreshButton || !elements.continueButton || !elements.backButton) {
        return null;
    }

    let disposed = false;

    async function refresh() {
        try {
            const state = await fetchOrdersState();
            if (disposed) {
                return;
            }
            renderOrdersPage(state, elements);
        } catch (error) {
            const fallback = fallbackStateFromLocalStorage();
            if (fallback) {
                renderOrdersPage(fallback, elements);
                elements.empty.classList.remove("hidden");
                elements.emptyCopy.textContent = "Live game state could not be loaded, so this page is showing a safe local fallback.";
            } else {
                elements.grid.innerHTML = "";
                elements.empty.classList.remove("hidden");
                elements.emptyCopy.textContent = "Could not load the reveal data. Check that the backend is running, then refresh.";
                updateSummary({ revealed: 0, kept: 0, changed: 0, betrayal: 0 }, elements.summary);
            }
            console.error("Failed to load orders reveal:", error);
        }
    }

    const onRefreshClick = () => {
        refresh();
    };

    const onBackClick = () => {
        if (typeof window.navigate === "function") {
            window.navigate("/game");
        }
    };

    const onContinueClick = async () => {
        elements.continueButton.disabled = true;
        try {
            let state = await fetchOrdersState();
            const stageName = String(state?.current_stage || "").toUpperCase();

            if (stageName === "ORDERS") {
                const payload = await postJson(`${API_BASE}/api/game/advance`, { force: false });
                state = payload.game_state || await fetchOrdersState();
            }

            if (String(state?.current_stage || "").toUpperCase() === "RESOLVE") {
                const payload = await postJson(`${API_BASE}/api/game/advance`, { force: true });
                state = payload.game_state || await fetchOrdersState();
            }

            if (typeof window.navigateToGameStage === "function") {
                await window.navigateToGameStage(state);
            } else if (typeof window.navigate === "function") {
                window.navigate("/game");
            }
        } catch (error) {
            console.error("Failed to continue from Orders:", error);
            elements.empty.classList.remove("hidden");
            elements.emptyCopy.textContent = error.message || "Could not continue the round yet.";
            elements.continueButton.disabled = false;
        }
    };

    elements.refreshButton.addEventListener("click", onRefreshClick);
    elements.continueButton.addEventListener("click", onContinueClick);
    elements.backButton.addEventListener("click", onBackClick);

    refresh();

    return () => {
        disposed = true;
        elements.refreshButton.removeEventListener("click", onRefreshClick);
        elements.continueButton.removeEventListener("click", onContinueClick);
        elements.backButton.removeEventListener("click", onBackClick);
    };
}
