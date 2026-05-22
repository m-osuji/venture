import fs from "node:fs";

describe("Game Page", () => {
  beforeEach(() => {
    const html = fs.readFileSync(
      new URL("../pages/game.html", import.meta.url),
      "utf8"
    );

    document.body.innerHTML = html;
  });

  test("renders main board container", () => {
    expect(document.getElementById("board-container")).not.toBeNull();
  });

  test("renders stage display", () => {
    expect(document.getElementById("current-stage-display")).not.toBeNull();
    expect(document.getElementById("stage-indicator")).not.toBeNull();
  });

  test("renders planning board panel hidden by default", () => {
    const planningPanel = document.getElementById("planning-board-panel");

    expect(planningPanel).not.toBeNull();
    expect(planningPanel.classList.contains("hidden")).toBe(true);
  });

  test("renders leaderboard button and overlay", () => {
    expect(document.getElementById("leaderboard-button")).not.toBeNull();
    expect(document.getElementById("leaderboard-overlay")).not.toBeNull();
  });

  test("renders AI container and text", () => {
    const ai = document.getElementById("AI");
    const text = document.getElementById("AI-text");

    expect(ai).not.toBeNull();
    expect(text).not.toBeNull();
    expect(text.textContent.length).toBeGreaterThan(0);
  });

  test("renders stage progresser button", () => {
    expect(document.getElementById("stage-progresser")).not.toBeNull();
  });

  test("renders game setup overlay", () => {
    const setup = document.getElementById("game-setup-overlay");

    expect(setup).not.toBeNull();
    expect(setup.style.display).toBe("none");
  });

  test("renders team selector options", () => {
    const select = document.getElementById("teamCountSelect");

    expect(select).not.toBeNull();
    expect(select.options.length).toBe(5);
  });

  test("renders AI difficulty container hidden by default", () => {
    const difficulty = document.getElementById("difficulty-container");

    expect(difficulty).not.toBeNull();
    expect(difficulty.style.display).toBe("none");
  });

  test("renders at least one territory button", () => {
    const territories = document.querySelectorAll(".territory-button");

    expect(territories.length).toBeGreaterThan(0);
  });

  test("renders capture UI for territories", () => {
    const overlays = document.querySelectorAll(".territory-overlay");

    expect(overlays.length).toBeGreaterThan(0);
  });
});
