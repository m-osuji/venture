export function buildTeamNameLookup(teams = []) {
    const lookup = new Map();

    teams.forEach((team, index) => {
        const teamName = team.team_name || team.name || `Team ${index + 1}`;
        [team.team_id, team.id, team.teamId].forEach((rawId) => {
            const numericId = Number(rawId);
            if (Number.isFinite(numericId)) {
                lookup.set(numericId, teamName);
            }
        });
    });

    return lookup;
}

export function normaliseOwnerId(owner) {
    if (owner === null || owner === undefined || owner === "") {
        return null;
    }

    const numericOwner = Number(owner);
    return Number.isFinite(numericOwner) && numericOwner > 0 ? numericOwner : null;
}

export function resolveOwnerName(market, ownerId, teamNameById) {
    if (ownerId === null) {
        return null;
    }

    return (
        teamNameById.get(ownerId) ||
        market.owner_name ||
        market.team_name ||
        market.ownerName ||
        `Team ${ownerId}`
    );
}

export function calculatePlanningReserve(team) {
    if (!team) {
        return 0;
    }

    return Number(team.ip || 0);
}

export function createZeroAllocationDraft(markets = []) {
    const draft = new Map();

    markets.forEach((market) => {
        draft.set(Number(market.marketId), 0);
    });

    return draft;
}

export function routeForGameStage(stage) {
    const stageName = String(stage || "PLAN").toUpperCase();

    if (stageName === "NEGOTIATE") {
        return "/negotiator";
    }
    if (stageName === "ORDERS") {
        return "/orders";
    }

    return "/game";
}

export function shouldNavigateToStage(currentPath, stage) {
    const nextPath = routeForGameStage(stage);

    return {
        nextPath,
        shouldNavigate: currentPath !== nextPath,
    };
}
