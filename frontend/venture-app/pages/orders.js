const API_BASE =
    window.VENTURE_API_BASE ||
    "https://venture-o2cx.onrender.com" ||
    "http://localhost:5000";

let resolveSession = null;
let activeConflictQuiz = null;

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

function teamNameById(state, teamId) {
    return (state?.teams || []).find((team) => Number(team.team_id) === Number(teamId))?.team_name || `Team ${teamId}`;
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

function quizSessionKey(state) {
    return JSON.stringify(
        (state.active_quizzes || []).map((quiz) => ({
            market_id: Number(quiz.market_id),
            participants: (quiz.participant_team_ids || []).map(Number),
            questions: (quiz.questions || []).map((question) => Number(question.question_id)),
        })),
    );
}

function buildResolveSession(state) {
    const submitted = new Set((state.quiz_results_submitted_markets || []).map(Number));
    const quizzes = (state.active_quizzes || []).filter(
        (quiz) => !submitted.has(Number(quiz.market_id)),
    );

    return {
        key: quizSessionKey({ active_quizzes: quizzes }),
        quizzes,
        currentQuizIndex: 0,
        currentQuestionIndex: 0,
        currentParticipantIndex: 0,
        answers: {},
        statusMessage: quizzes.length
            ? "Answer each question for both teams to resolve the contested market."
            : "",
        completed: quizzes.length === 0,
        currentQuestionStartedAt: Date.now(),
    };
}

function ensureResolveSession(state) {
    const nextSession = buildResolveSession(state);
    if (!resolveSession || resolveSession.key !== nextSession.key) {
        resolveSession = nextSession;
    } else {
        resolveSession.quizzes = nextSession.quizzes;
        resolveSession.completed = nextSession.completed;
    }
    return resolveSession;
}

function getResolveQuiz(session) {
    return session?.quizzes?.[session.currentQuizIndex] || null;
}

function getResolveQuestion(session, quiz) {
    return quiz?.questions?.[session.currentQuestionIndex] || null;
}

function ensureAnswerBucket(session, marketId, teamId) {
    session.answers[marketId] = session.answers[marketId] || {};
    session.answers[marketId][teamId] = session.answers[marketId][teamId] || [];
    return session.answers[marketId][teamId];
}

function answeredQuestionCount(session, marketId, teamId) {
    return (session.answers?.[marketId]?.[teamId] || []).length;
}

function recordResolveAnswer(optionValue) {
    if (!resolveSession) {
        return;
    }

    const quiz = getResolveQuiz(resolveSession);
    const question = getResolveQuestion(resolveSession, quiz);
    if (!quiz || !question) {
        return;
    }

    const marketId = Number(quiz.market_id);
    const participantIds = (quiz.participant_team_ids || []).map(Number);
    const teamId = participantIds[resolveSession.currentParticipantIndex];
    const bucket = ensureAnswerBucket(resolveSession, marketId, teamId);
    const responseTime = Math.max(250, Date.now() - Number(resolveSession.currentQuestionStartedAt || Date.now()));

    bucket.push({
        question_id: Number(question.question_id),
        selected_option: optionValue,
        response_time_ms: responseTime,
    });

    if (resolveSession.currentParticipantIndex < participantIds.length - 1) {
        resolveSession.currentParticipantIndex += 1;
        resolveSession.currentQuestionStartedAt = Date.now();
        resolveSession.statusMessage = `${teamId} answered. Pass to ${participantIds[resolveSession.currentParticipantIndex]}.`;
        return;
    }

    if (resolveSession.currentQuestionIndex < (quiz.questions || []).length - 1) {
        resolveSession.currentQuestionIndex += 1;
        resolveSession.currentParticipantIndex = 0;
        resolveSession.currentQuestionStartedAt = Date.now();
        resolveSession.statusMessage = `Question ${resolveSession.currentQuestionIndex + 1} is live for ${participantIds[0]}.`;
        return;
    }

    if (resolveSession.currentQuizIndex < resolveSession.quizzes.length - 1) {
        const finishedMarket = Number(quiz.market_id);
        resolveSession.currentQuizIndex += 1;
        resolveSession.currentQuestionIndex = 0;
        resolveSession.currentParticipantIndex = 0;
        resolveSession.currentQuestionStartedAt = Date.now();
        const nextQuiz = getResolveQuiz(resolveSession);
        resolveSession.statusMessage = `${finishedMarket} resolved locally. Continue with ${marketName(new Map(), nextQuiz?.market_id)}.`;
        return;
    }

    resolveSession.completed = true;
    resolveSession.statusMessage = "All conflict quiz answers are ready. Press Finish resolution to apply the outcomes.";
}

const optionLetterToAnswerKey = {
    a: "option_1",
    b: "option_2",
    c: "option_3",
    d: "option_4",
};

const answerKeyToOptionLetter = {
    option_1: "a",
    option_2: "b",
    option_3: "c",
    option_4: "d",
};

class ConflictResolutionQuiz {
    constructor(state, marketMap) {
        this.state = state;
        this.marketMap = marketMap;
        this.quizzes = state.active_quizzes || [];
        this.aiTeamIds = new Set(
            (state.teams || [])
                .filter((team) => Boolean(team.is_ai))
                .map((team) => Number(team.team_id)),
        );
        this.aiDifficulty = String(state.ai_difficulty || "medium").toLowerCase();
        this.teamNameLookup = new Map(
            (state.teams || []).map((team) => [Number(team.team_id), team.team_name]),
        );
        this.currentQuizIndex = 0;
        this.currentQuestionIndex = 0;
        this.questionActive = true;
        this.countdownInterval = null;
        this.currentTimeRemaining = 30;
        this.currentQuestionStartTime = null;
        this.resultsByMarket = {};
        this.currentQuizResults = null;
        this.onComplete = null;
        this.aiAnswerTimeouts = [];
        
        // Track per-team response times for the current question
        this.questionTeamAnswers = new Map(); // teamIndex -> { answeredAt: timestamp }
        
        this.keyToOption = {
            "1": { team: 1, option: "a" },
            "2": { team: 1, option: "b" },
            "3": { team: 1, option: "c" },
            "4": { team: 1, option: "d" },
            "6": { team: 2, option: "a" },
            "7": { team: 2, option: "b" },
            "8": { team: 2, option: "c" },
            "9": { team: 2, option: "d" },
        };
    }

    start(onComplete) {
        this.onComplete = onComplete;
        this.createOverlay();
        this.setupEventListeners();
        this.startMatchup();
    }

    createOverlay() {
        this.overlay = document.getElementById("conflict-resolution-overlay");
        if (!this.overlay) {
            this.overlay = document.createElement("div");
            this.overlay.id = "conflict-resolution-overlay";
            this.overlay.className = "game-setup-overlay";
            this.overlay.innerHTML = `
                <div class="tournament-layout">
                    <div id="team1-panel" class="tournament-team-panel team1-panel">
                        <h3>TEAM 1</h3>
                        <div class="team-score">Score: <span id="team1-score">0</span></div>
                        <div class="team-total-time">Total Time: <span id="team1-time">0.0</span>s</div>
                        <div class="team-keys">Use keys: 1 2 3 4</div>
                    </div>
                    <div class="setup-card quiz-card">
                        <div class="quiz-header">
                            <h2>CONFLICT CHALLENGE</h2>
                            <div id="question-timer" class="question-timer">Time: 30s</div>
                        </div>
                        <div id="tournament-progress" class="tournament-progress">Matchup X of Y</div>
                        <div id="question-area" class="question-area">
                            <div id="question-text" class="question-text">Loading question...</div>
                            <div id="options-area" class="options-area">
                                <div id="option-a" class="competition-option" data-option="a">A. </div>
                                <div id="option-b" class="competition-option" data-option="b">B. </div>
                                <div id="option-c" class="competition-option" data-option="c">C. </div>
                                <div id="option-d" class="competition-option" data-option="d">D. </div>
                            </div>
                        </div>
                        <div id="round-result" class="round-result" style="display: none;"></div>
                        <div class="setup-actions">
                            <button id="next-question-btn" class="setup-btn-primary" style="display: none;">Next Question</button>
                            <button id="next-matchup-btn" class="setup-btn-primary" style="display: none;">Next Matchup</button>
                        </div>
                    </div>
                    <div id="team2-panel" class="tournament-team-panel team2-panel">
                        <h3>TEAM 2</h3>
                        <div class="team-score">Score: <span id="team2-score">0</span></div>
                        <div class="team-total-time">Total Time: <span id="team2-time">0.0</span>s</div>
                        <div class="team-keys">Use keys: 6 7 8 9</div>
                    </div>
                </div>
            `;
            document.body.appendChild(this.overlay);
        }
        this.overlay.style.display = "flex";
    }

    currentQuiz() {
        return this.quizzes[this.currentQuizIndex] || null;
    }

    currentTeams() {
        return (this.currentQuiz()?.participant_team_ids || []).map(Number);
    }

    currentQuestion() {
        return this.currentQuiz()?.questions?.[this.currentQuestionIndex] || null;
    }

    startMatchup() {
        const quiz = this.currentQuiz();
        if (!quiz) {
            this.finish();
            return;
        }

        this.currentQuestionIndex = 0;
        this.questionActive = true;
        this.currentTimeRemaining = 30;
        this.currentQuizResults = {
            market_id: Number(quiz.market_id),
            team_results: this.currentTeams().map((teamId) => ({
                team_id: teamId,
                answers: [],
                totalResponseTimeMs: 0,  // Track total time in milliseconds
                correctCount: 0,           // Track correct answers
            })),
        };
        this.resultsByMarket[Number(quiz.market_id)] = this.currentQuizResults;

        const [team1Id, team2Id] = this.currentTeams();
        const team1Panel = document.getElementById("team1-panel");
        const team2Panel = document.getElementById("team2-panel");
        if (team1Panel) {
            team1Panel.querySelector("h3").innerHTML = `TEAM 1: ${escapeHtml(this.teamNameLookup.get(team1Id) || `Team ${team1Id}`)}`;
        }
        if (team2Panel) {
            team2Panel.querySelector("h3").innerHTML = `TEAM 2: ${escapeHtml(this.teamNameLookup.get(team2Id) || `Team ${team2Id}`)}`;
        }

        this.updateScores();
        this.updateTotalTimeDisplay();
        this.updateTournamentProgress();
        this.displayQuestion();

        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) {
            nextMatchupBtn.style.display = "none";
        }
    }

    updateScores() {
        const [team1Id, team2Id] = this.currentTeams();
        const team1Correct = this.getTeamCorrectCount(team1Id);
        const team2Correct = this.getTeamCorrectCount(team2Id);
        const team1ScoreEl = document.getElementById("team1-score");
        const team2ScoreEl = document.getElementById("team2-score");
        if (team1ScoreEl) team1ScoreEl.textContent = String(team1Correct);
        if (team2ScoreEl) team2ScoreEl.textContent = String(team2Correct);
    }

    updateTotalTimeDisplay() {
        const [team1Id, team2Id] = this.currentTeams();
        const team1TimeSec = (this.getTeamTotalTime(team1Id) / 1000).toFixed(1);
        const team2TimeSec = (this.getTeamTotalTime(team2Id) / 1000).toFixed(1);
        const team1TimeEl = document.getElementById("team1-time");
        const team2TimeEl = document.getElementById("team2-time");
        if (team1TimeEl) team1TimeEl.textContent = team1TimeSec;
        if (team2TimeEl) team2TimeEl.textContent = team2TimeSec;
    }

    getTeamCorrectCount(teamId) {
        const result = this.currentQuizResults?.team_results?.find(
            (entry) => Number(entry.team_id) === Number(teamId)
        );
        return result?.correctCount || 0;
    }

    getTeamTotalTime(teamId) {
        const result = this.currentQuizResults?.team_results?.find(
            (entry) => Number(entry.team_id) === Number(teamId)
        );
        return result?.totalResponseTimeMs || 0;
    }

    revealCorrectAnswer() {
        const correctOptionLetter = answerKeyToOptionLetter[this.currentQuestion()?.answer];
        if (!correctOptionLetter) {
            return;
        }

        const correctOption = document.getElementById(`option-${correctOptionLetter}`);
        if (!correctOption) {
            return;
        }

        correctOption.style.background = "#27ae60";
        correctOption.style.border = "2px solid #1d7c45";
        correctOption.style.color = "#ffffff";
        correctOption.style.opacity = "1";
        correctOption.style.boxShadow = "0 14px 30px rgba(39, 174, 96, 0.28)";
    }

    clearAiAnswerTimeouts() {
        this.aiAnswerTimeouts.forEach((timeoutId) => clearTimeout(timeoutId));
        this.aiAnswerTimeouts = [];
    }

    getAiAccuracyChance(question) {
        const questionDifficulty = String(question?.difficulty_level || "medium").toLowerCase();
        const baseByDifficulty = {
            easy: 0.58,
            medium: 0.74,
            hard: 0.88,
        };
        const questionModifier = {
            easy: 0.16,
            medium: 0.0,
            hard: -0.12,
        };
        const baseChance = baseByDifficulty[this.aiDifficulty] ?? 0.74;
        return Math.max(0.2, Math.min(0.97, baseChance + (questionModifier[questionDifficulty] ?? 0)));
    }

    randomWrongOption(correctOption) {
        const distractors = ["a", "b", "c", "d"].filter((option) => option !== correctOption);
        return distractors[Math.floor(Math.random() * distractors.length)] || "a";
    }

    getAiDelayMs() {
        if (this.aiDifficulty === "easy") {
            return 9000 + Math.floor(Math.random() * 9000);
        }
        if (this.aiDifficulty === "hard") {
            return 2500 + Math.floor(Math.random() * 4500);
        }
        return 5000 + Math.floor(Math.random() * 7000);
    }

    scheduleAiAnswers(question) {
        this.currentTeams().forEach((teamId, index) => {
            if (!this.aiTeamIds.has(Number(teamId))) {
                return;
            }

            const timeoutId = setTimeout(() => {
                if (!this.questionActive) {
                    return;
                }
                const correctOption = answerKeyToOptionLetter[question?.answer] || "a";
                const selectedOption = Math.random() <= this.getAiAccuracyChance(question)
                    ? correctOption
                    : this.randomWrongOption(correctOption);
                this.handleAnswer(index + 1, selectedOption);
            }, this.getAiDelayMs());

            this.aiAnswerTimeouts.push(timeoutId);
        });
    }

    updateTournamentProgress() {
        const progressDiv = document.getElementById("tournament-progress");
        if (!progressDiv) return;
        const quiz = this.currentQuiz();
        progressDiv.innerHTML = `Conflict ${this.currentQuizIndex + 1} of ${this.quizzes.length} | ${marketName(this.marketMap, Number(quiz?.market_id))}`;
    }

    displayQuestion() {
        const question = this.currentQuestion();
        if (!question) {
            this.endMatchup();
            return;
        }

        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }

        this.questionActive = true;
        window.team1Locked = false;
        window.team2Locked = false;
        this.currentQuestionStartTime = Date.now();
        
        // Reset per-question answer tracking
        this.questionTeamAnswers.clear();
        this.clearAiAnswerTimeouts();

        const questionText = document.getElementById("question-text");
        if (questionText) {
            questionText.innerHTML = `Question ${this.currentQuestionIndex + 1} of ${this.currentQuiz()?.questions?.length || 0}: ${escapeHtml(question.content)}`;
        }
        const optionA = document.getElementById("option-a");
        const optionB = document.getElementById("option-b");
        const optionC = document.getElementById("option-c");
        const optionD = document.getElementById("option-d");
        if (optionA) optionA.innerHTML = `A. ${escapeHtml(question.options?.option_1 || "")}`;
        if (optionB) optionB.innerHTML = `B. ${escapeHtml(question.options?.option_2 || "")}`;
        if (optionC) optionC.innerHTML = `C. ${escapeHtml(question.options?.option_3 || "")}`;
        if (optionD) optionD.innerHTML = `D. ${escapeHtml(question.options?.option_4 || "")}`;

        const roundResult = document.getElementById("round-result");
        if (roundResult) {
            roundResult.style.display = "none";
            roundResult.innerHTML = "";
        }

        const nextQuestionBtn = document.getElementById("next-question-btn");
        if (nextQuestionBtn) {
            nextQuestionBtn.style.display = "none";
        }

        document.querySelectorAll(".competition-option").forEach((opt) => {
            opt.style.background = "#f0f0f0";
            opt.style.border = "2px solid #ddd";
            opt.style.cursor = "pointer";
            opt.style.opacity = "1";
        });

        const timerElement = document.getElementById("question-timer");
        if (timerElement) {
            timerElement.style.display = "block";
            timerElement.style.background = "var(--main-orange)";
            timerElement.style.animation = "none";
            timerElement.textContent = "Time: 30s";
        }

        this.startCountdown();
        this.scheduleAiAnswers(question);
    }

    recordAnswer(teamIndex, selectedOption, isCorrect) {
        const question = this.currentQuestion();
        const teamId = this.currentTeams()[teamIndex - 1];
        const result = this.currentQuizResults?.team_results?.find((entry) => Number(entry.team_id) === Number(teamId));
        if (!question || !result) return false;

        // Check if already answered this question
        if (result.answers.some((answer) => Number(answer.question_id) === Number(question.question_id))) {
            return false;
        }

        // Calculate response time - from question start to when this team answered
        const responseTime = this.currentQuestionStartTime 
            ? Math.max(250, Date.now() - this.currentQuestionStartTime) 
            : 1000;

        result.answers.push({
            question_id: Number(question.question_id),
            selected_option: optionLetterToAnswerKey[selectedOption] || "option_1",
            response_time_ms: responseTime,
        });

        // Add to total response time for this team
        result.totalResponseTimeMs += responseTime;
        
        // Track correct answers count
        if (isCorrect) {
            result.correctCount += 1;
        }

        return true;
    }

    startCountdown() {
        this.currentTimeRemaining = 30;
        this.countdownInterval = setInterval(() => {
            if (!this.questionActive) return;

            this.currentTimeRemaining -= 1;
            const timerEl = document.getElementById("question-timer");
            if (timerEl) {
                timerEl.textContent = `Time: ${this.currentTimeRemaining}s`;
                if (this.currentTimeRemaining <= 10 && this.currentTimeRemaining > 0) {
                    timerEl.style.background = "#e74c3c";
                    timerEl.style.animation = "pulse 0.5s infinite";
                } else if (this.currentTimeRemaining <= 20 && this.currentTimeRemaining > 0) {
                    timerEl.style.background = "#f39c12";
                    timerEl.style.animation = "none";
                } else if (this.currentTimeRemaining > 0) {
                    timerEl.style.background = "var(--main-orange)";
                    timerEl.style.animation = "none";
                }
            }

            if (this.currentTimeRemaining <= 0) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
                
                if (this.questionActive) {
                    this.questionActive = false;
                    
                    // Record that timer expired - no additional time recorded for unanswered teams
                    const roundResult = document.getElementById("round-result");
                    if (roundResult) {
                        const unansweredTeams = [];
                        if (!window.team1Locked) unansweredTeams.push("Team 1");
                        if (!window.team2Locked) unansweredTeams.push("Team 2");
                        const unansweredText = unansweredTeams.length 
                            ? ` (${unansweredTeams.join(" and ")} did not answer)` 
                            : "";
                        roundResult.innerHTML = `<span style="color: orange; font-weight: bold;">Time's up!${unansweredText} The correct answer was ${answerKeyToOptionLetter[this.currentQuestion()?.answer]?.toUpperCase()}.</span>`;
                        roundResult.style.display = "block";
                    }
                    
                    const nextQuestionBtn = document.getElementById("next-question-btn");
                    if (nextQuestionBtn) {
                        nextQuestionBtn.style.display = "block";
                    }
                    
                    document.querySelectorAll(".competition-option").forEach((opt) => {
                        opt.style.cursor = "not-allowed";
                        opt.style.opacity = "0.5";
                    });
                    
                    this.revealCorrectAnswer();
                    this.updateTotalTimeDisplay();
                }
            }
        }, 1000);
    }

    handleAnswer(teamIndex, selectedOption) {
        if (!this.questionActive) return;
        if ((teamIndex === 1 && window.team1Locked) || (teamIndex === 2 && window.team2Locked)) {
            return;
        }

        const question = this.currentQuestion();
        const selectedAnswerKey = optionLetterToAnswerKey[selectedOption];
        const isCorrect = selectedAnswerKey === question?.answer;
        
        // Record the answer with time tracking
        this.recordAnswer(teamIndex, selectedOption, isCorrect);
        
        if (teamIndex === 1) window.team1Locked = true;
        if (teamIndex === 2) window.team2Locked = true;

        const roundResult = document.getElementById("round-result");
        if (roundResult) {
            const teamId = this.currentTeams()[teamIndex - 1];
            const teamName = this.teamNameLookup.get(teamId) || `Team ${teamId}`;
            
            if (isCorrect) {
                roundResult.innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${escapeHtml(teamName)} earns a point! (Response time recorded)</span>`;
            } else {
                roundResult.innerHTML = `<span style="color: red;">WRONG! ${escapeHtml(teamName)} does not earn a point. (Response time still recorded)</span>`;
            }
            roundResult.style.display = "block";
        }

        // Update displays
        this.updateScores();
        this.updateTotalTimeDisplay();

        const allLocked = Boolean(window.team1Locked) && Boolean(window.team2Locked);
        
        // Only end the question if:
        // 1. Someone answered correctly, OR
        // 2. Both teams have answered (even if both wrong)
        if (isCorrect || allLocked) {
            this.stopCountdown();
            this.questionActive = false;
            
            const nextQuestionBtn = document.getElementById("next-question-btn");
            if (nextQuestionBtn) {
                nextQuestionBtn.style.display = "block";
            }
            
            document.querySelectorAll(".competition-option").forEach((opt) => {
                opt.style.cursor = "not-allowed";
                opt.style.opacity = "0.5";
            });
            
            this.revealCorrectAnswer();
            
            // If both were wrong, show additional message
            const bothWrong = allLocked && this.currentTeams().every((teamId) => {
                const result = this.currentQuizResults?.team_results?.find(
                    (entry) => Number(entry.team_id) === Number(teamId),
                );
                const answer = result?.answers?.find(
                    (entry) => Number(entry.question_id) === Number(question?.question_id),
                );
                return answer && String(answer.selected_option) !== String(question?.answer);
            });
            if (bothWrong) {
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: orange; font-weight: bold;">Both teams were wrong! The correct answer was ${answerKeyToOptionLetter[question?.answer]?.toUpperCase()}.</span>`;
                    roundResult.style.display = "block";
                }
            }
        }
    }

    stopCountdown() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }

    nextQuestion() {
        this.stopCountdown();
        this.clearAiAnswerTimeouts();
        this.currentQuestionIndex += 1;
        if (this.currentQuestionIndex < (this.currentQuiz()?.questions?.length || 0)) {
            this.displayQuestion();
        } else {
            this.endMatchup();
        }
    }

    endMatchup() {
        const [team1Id, team2Id] = this.currentTeams();
        const team1Correct = this.getTeamCorrectCount(team1Id);
        const team2Correct = this.getTeamCorrectCount(team2Id);
        const team1TimeSec = (this.getTeamTotalTime(team1Id) / 1000).toFixed(1);
        const team2TimeSec = (this.getTeamTotalTime(team2Id) / 1000).toFixed(1);
        
        // Determine winner: highest correct wins, tie goes to lower total time
        let winnerText = "";
        let winnerColor = "#f39c12"; // Default tie color
        
        if (team1Correct > team2Correct) {
            winnerText = `WINNER: ${escapeHtml(this.teamNameLookup.get(team1Id) || `Team ${team1Id}`)} (${team1Correct} correct, ${team1TimeSec}s total)`;
            winnerColor = "#27ae60";
        } else if (team2Correct > team1Correct) {
            winnerText = `WINNER: ${escapeHtml(this.teamNameLookup.get(team2Id) || `Team ${team2Id}`)} (${team2Correct} correct, ${team2TimeSec}s total)`;
            winnerColor = "#27ae60";
        } else {
            // Tie - compare total time
            if (team1TimeSec < team2TimeSec) {
                winnerText = `TIE BREAKER! ${escapeHtml(this.teamNameLookup.get(team1Id) || `Team ${team1Id}`)} wins on time (${team1Correct} correct, ${team1TimeSec}s vs ${team2TimeSec}s)`;
                winnerColor = "#27ae60";
            } else if (team2TimeSec < team1TimeSec) {
                winnerText = `TIE BREAKER! ${escapeHtml(this.teamNameLookup.get(team2Id) || `Team ${team2Id}`)} wins on time (${team2Correct} correct, ${team2TimeSec}s vs ${team1TimeSec}s)`;
                winnerColor = "#27ae60";
            } else {
                winnerText = "IT'S A COMPLETE TIE! (Same correct answers AND total time)";
                winnerColor = "#f39c12";
            }
        }

        const questionArea = document.getElementById("question-area");
        if (questionArea) questionArea.style.display = "none";
        const nextQuestionBtn = document.getElementById("next-question-btn");
        if (nextQuestionBtn) nextQuestionBtn.style.display = "none";

        const roundResult = document.getElementById("round-result");
        if (roundResult) {
            roundResult.innerHTML = `
                <div style="text-align: center;">
                    <h3>MATCHUP COMPLETE</h3>
                    <div style="font-size: 20px; margin: 15px 0;">
                        ${escapeHtml(this.teamNameLookup.get(team1Id) || `Team ${team1Id}`)}: ${team1Correct} correct (${team1TimeSec}s total)<br>
                        ${escapeHtml(this.teamNameLookup.get(team2Id) || `Team ${team2Id}`)}: ${team2Correct} correct (${team2TimeSec}s total)
                    </div>
                    <div style="font-size: 24px; font-weight: bold; color: ${winnerColor};">
                        ${winnerText}
                    </div>
                </div>
            `;
            roundResult.style.display = "block";
        }

        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) {
            nextMatchupBtn.style.display = "block";
            nextMatchupBtn.textContent = this.currentQuizIndex + 1 < this.quizzes.length ? "Next Matchup" : "View Tournament Results";
        }
    }

    nextMatchup() {
        this.clearAiAnswerTimeouts();
        this.currentQuizIndex += 1;
        if (this.currentQuizIndex < this.quizzes.length) {
            const questionArea = document.getElementById("question-area");
            const roundResult = document.getElementById("round-result");
            const nextMatchupBtn = document.getElementById("next-matchup-btn");
            if (questionArea) questionArea.style.display = "block";
            if (roundResult) roundResult.style.display = "none";
            if (nextMatchupBtn) nextMatchupBtn.style.display = "none";
            this.startMatchup();
        } else {
            this.finish();
        }
    }

    finish() {
        this.stopCountdown();
        this.clearAiAnswerTimeouts();
        this.removeEventListeners();
        if (this.overlay) {
            this.overlay.remove();
        }
        const results = Object.values(this.resultsByMarket);
        this.onComplete?.(results);
    }

    setupEventListeners() {
        this.boundKeyDown = this.onKeyDown.bind(this);
        this.boundNextQuestion = this.nextQuestion.bind(this);
        this.boundNextMatchup = this.nextMatchup.bind(this);
        document.addEventListener("keydown", this.boundKeyDown);
        const nextQuestionBtn = document.getElementById("next-question-btn");
        if (nextQuestionBtn) nextQuestionBtn.onclick = this.boundNextQuestion;
        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) nextMatchupBtn.onclick = this.boundNextMatchup;
    }

    removeEventListeners() {
        document.removeEventListener("keydown", this.boundKeyDown);
    }

    onKeyDown(event) {
        const mapping = this.keyToOption[event.key];
        if (!mapping || !this.questionActive) {
            return;
        }
        event.preventDefault();
        this.handleAnswer(mapping.team, mapping.option);
    }
}

function answeredCountForTeam(resultSet, teamId) {
    return (resultSet?.team_results?.find((entry) => Number(entry.team_id) === Number(teamId))?.answers?.length) || 0;
}

function correctAnswerCountForTeam(resultSet, quiz, teamId) {
    const answers =
        resultSet?.team_results?.find((entry) => Number(entry.team_id) === Number(teamId))?.answers || [];
    const answerLookup = new Map(
        (quiz?.questions || []).map((question) => [Number(question.question_id), String(question.answer || "")]),
    );

    return answers.filter((answer) => {
        const correctAnswer = answerLookup.get(Number(answer.question_id));
        return correctAnswer && String(answer.selected_option || "") === correctAnswer;
    }).length;
}

function launchConflictResolutionQuiz(state, marketMap) {
    return new Promise((resolve, reject) => {
        try {
            if (activeConflictQuiz) {
                activeConflictQuiz.finish();
            }
            activeConflictQuiz = new ConflictResolutionQuiz(state, marketMap);
            activeConflictQuiz.start((results) => {
                activeConflictQuiz = null;
                resolve(results);
            });
        } catch (error) {
            activeConflictQuiz = null;
            reject(error);
        }
    });
}

function renderResolveSection(state, elements, marketMap) {
    if (!elements.resolveShell) return;
    resolveSession = null;
    elements.resolveShell.classList.add("hidden");
    elements.resolveShell.innerHTML = "";
}

async function submitActiveQuizResults(results) {
    for (const quizResult of results) {
        await postJson(`${API_BASE}/api/game/quiz-results`, {
            market_id: Number(quizResult.market_id),
            team_results: quizResult.team_results,
        });
    }
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
        renderResolveSection(state, elements, marketMap);
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
                                <span>Ethics ${escapeHtml(Number(team.ethical_score ?? 1).toFixed(2))}</span>
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
    renderResolveSection(state, elements, marketMap);
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
        resolveShell: document.getElementById("orders-resolve-shell"),
        refreshButton: document.getElementById("orders-refresh-btn"),
        continueButton: document.getElementById("orders-continue-btn"),
        backButton: document.getElementById("orders-back-btn")
    };

    if (!elements.summary || !elements.grid || !elements.refreshButton || !elements.continueButton || !elements.backButton) {
        return null;
    }

    let disposed = false;
    let currentState = null;

    async function refresh() {
        try {
            const state = await fetchOrdersState();
            if (disposed) {
                return;
            }
            currentState = state;
            renderOrdersPage(state, elements);
        } catch (error) {
            const fallback = fallbackStateFromLocalStorage();
            if (fallback) {
                currentState = fallback;
                renderOrdersPage(fallback, elements);
                elements.empty.classList.remove("hidden");
                elements.emptyCopy.textContent = "Live game state could not be loaded, so this page is showing a safe local fallback.";
            } else {
                currentState = null;
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
            const marketMap = new Map(
                Object.entries(state.market_state || {}).map(([marketId, market]) => [Number(marketId), market])
            );

            if (stageName === "ORDERS") {
                const payload = await postJson(`${API_BASE}/api/game/advance`, { force: false });
                state = payload.game_state || await fetchOrdersState();
                if (String(state?.current_stage || "").toUpperCase() === "RESOLVE" && (state.active_quizzes || []).length) {
                    const quizResults = await launchConflictResolutionQuiz(state, marketMap);
                    await submitActiveQuizResults(quizResults);
                    state = await fetchOrdersState();
                }
            }

            if (String(state?.current_stage || "").toUpperCase() === "RESOLVE") {
                if ((state.active_quizzes || []).length) {
                    const quizResults = await launchConflictResolutionQuiz(state, marketMap);
                    await submitActiveQuizResults(quizResults);
                    state = await fetchOrdersState();
                }
                const payload = await postJson(`${API_BASE}/api/game/advance`, { force: false });
                state = payload.game_state || await fetchOrdersState();
            }

            if (String(state?.current_stage || "").toUpperCase() === "UPDATE") {
                const payload = await postJson(`${API_BASE}/api/game/advance`, { force: false });
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
        if (activeConflictQuiz) {
            activeConflictQuiz.finish();
            activeConflictQuiz = null;
        }
    };
}
