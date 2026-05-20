import test from "node:test";
import assert from "node:assert/strict";

import {
    buildTeamNameLookup,
    calculatePlanningReserve,
    createZeroAllocationDraft,
    normaliseOwnerId,
    routeForGameStage,
    resolveOwnerName,
    shouldNavigateToStage,
} from "../lib/gameState.js";

test("team lookup supports backend and frontend id shapes", () => {
    const lookup = buildTeamNameLookup([
        { team_id: 1, team_name: "Team A" },
        { id: 2, name: "Team B" },
        { teamId: 3, team_name: "Team C" },
    ]);

    assert.equal(lookup.get(1), "Team A");
    assert.equal(lookup.get(2), "Team B");
    assert.equal(lookup.get(3), "Team C");
});

test("owner names fall back without marking captured markets as uncaptured", () => {
    const lookup = buildTeamNameLookup([{ id: 2, name: "Team B" }]);
    const ownerId = normaliseOwnerId("2");

    assert.equal(ownerId, 2);
    assert.equal(resolveOwnerName({}, ownerId, lookup), "Team B");
    assert.equal(resolveOwnerName({}, 9, lookup), "Team 9");
});

test("neutral or invalid owners stay uncaptured", () => {
    assert.equal(normaliseOwnerId(null), null);
    assert.equal(normaliseOwnerId(""), null);
    assert.equal(normaliseOwnerId(0), null);
});

test("planning reserve only counts spare team IP, not already saved market IP", () => {
    const team = { team_id: 2, team_name: "Team B", ip: 3 };

    assert.equal(calculatePlanningReserve(team), 3);
    assert.equal(calculatePlanningReserve(null), 0);
});

test("planning drafts start at zero even when markets already have saved IP", () => {
    const draft = createZeroAllocationDraft([
        { marketId: 7, allocated_ip: 9 },
        { marketId: 8, allocated_ip: 4 },
    ]);

    assert.equal(draft.get(7), 0);
    assert.equal(draft.get(8), 0);
});

test("stage routing sends active workflow pages to the right screen", () => {
    assert.equal(routeForGameStage("PLAN"), "/game");
    assert.equal(routeForGameStage("NEGOTIATE"), "/negotiator");
    assert.equal(routeForGameStage("ORDERS"), "/orders");
    assert.equal(routeForGameStage("RESOLVE"), "/game");
    assert.equal(routeForGameStage("UPDATE"), "/game");
    assert.equal(routeForGameStage(undefined), "/game");
});

test("stage navigation does not reload the current route unnecessarily", () => {
    assert.deepEqual(shouldNavigateToStage("/game", "PLAN"), {
        nextPath: "/game",
        shouldNavigate: false,
    });
    assert.deepEqual(shouldNavigateToStage("/game", "NEGOTIATE"), {
        nextPath: "/negotiator",
        shouldNavigate: true,
    });
    assert.deepEqual(shouldNavigateToStage("/orders", "ORDERS"), {
        nextPath: "/orders",
        shouldNavigate: false,
    });
});
