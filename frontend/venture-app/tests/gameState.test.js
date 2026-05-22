let gameState;

beforeAll(async () => {
  gameState = await import("../lib/gameState.js");
});

test("team lookup supports backend and frontend id shapes", () => {
  const lookup = gameState.buildTeamNameLookup([
    { team_id: 1, team_name: "Team A" },
    { id: 2, name: "Team B" },
    { teamId: 3, team_name: "Team C" },
  ]);

  expect(lookup.get(1)).toBe("Team A");
  expect(lookup.get(2)).toBe("Team B");
  expect(lookup.get(3)).toBe("Team C");
});

test("owner names fall back without marking captured markets as uncaptured", () => {
  const lookup = gameState.buildTeamNameLookup([{ id: 2, name: "Team B" }]);
  const ownerId = gameState.normaliseOwnerId("2");

  expect(ownerId).toBe(2);
  expect(gameState.resolveOwnerName({}, ownerId, lookup)).toBe("Team B");
  expect(gameState.resolveOwnerName({}, 9, lookup)).toBe("Team 9");
});

test("neutral or invalid owners stay uncaptured", () => {
  expect(gameState.normaliseOwnerId(null)).toBeNull();
  expect(gameState.normaliseOwnerId("")).toBeNull();
  expect(gameState.normaliseOwnerId(0)).toBeNull();
});

test("planning reserve only counts spare team IP, not already saved market IP", () => {
  const team = { team_id: 2, team_name: "Team B", ip: 3 };

  expect(gameState.calculatePlanningReserve(team)).toBe(3);
  expect(gameState.calculatePlanningReserve(null)).toBe(0);
});

test("planning drafts start at zero even when markets already have saved IP", () => {
  const draft = gameState.createZeroAllocationDraft([
    { marketId: 7, allocated_ip: 9 },
    { marketId: 8, allocated_ip: 4 },
  ]);

  expect(draft.get(7)).toBe(0);
  expect(draft.get(8)).toBe(0);
});

test("stage routing sends active workflow pages to the right screen", () => {
  expect(gameState.routeForGameStage("PLAN")).toBe("/game");
  expect(gameState.routeForGameStage("NEGOTIATE")).toBe("/negotiator");
  expect(gameState.routeForGameStage("ORDERS")).toBe("/orders");
  expect(gameState.routeForGameStage("RESOLVE")).toBe("/game");
  expect(gameState.routeForGameStage("UPDATE")).toBe("/game");
  expect(gameState.routeForGameStage(undefined)).toBe("/game");
});

test("stage navigation does not reload the current route unnecessarily", () => {
  expect(gameState.shouldNavigateToStage("/game", "PLAN")).toEqual({
    nextPath: "/game",
    shouldNavigate: false,
  });
  expect(gameState.shouldNavigateToStage("/game", "NEGOTIATE")).toEqual({
    nextPath: "/negotiator",
    shouldNavigate: true,
  });
  expect(gameState.shouldNavigateToStage("/orders", "ORDERS")).toEqual({
    nextPath: "/orders",
    shouldNavigate: false,
  });
});
