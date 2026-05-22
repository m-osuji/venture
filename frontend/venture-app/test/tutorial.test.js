// tutorial.test.js

const fs = require("fs");
const path = require("path");

describe("Tutorial Page", () => {
  beforeEach(() => {
    const html = fs.readFileSync(
      path.resolve(__dirname, "../pages/tutorial.html"),
      "utf8"
    );

    document.body.innerHTML = html;
  });

  test("renders tutorial page root container", () => {
    const root = document.getElementById("tutorial-page");

    expect(root).not.toBeNull();
  });

  test("renders scroll indicator structure", () => {
    expect(document.getElementById("scroll-indicator")).not.toBeNull();
    expect(document.getElementById("scroll-line")).not.toBeNull();
    expect(document.getElementById("scroll-progress")).not.toBeNull();
    expect(document.getElementById("scroll-ball")).not.toBeNull();
    expect(document.getElementById("scroll-markers")).not.toBeNull();
  });

  test("renders main tutorial title", () => {
    const title = document.querySelector("h1");

    expect(title).not.toBeNull();
    expect(title.textContent).toBe("How to Play Venture");
  });

  test("renders quickstart steps", () => {
    const steps = document.querySelectorAll(".tutorial-quickstep");

    expect(steps.length).toBe(5);
    expect(steps[0].textContent).toContain("Allocate IP");
    expect(steps[1].textContent).toContain("Negotiate");
    expect(steps[2].textContent).toContain("Lock Orders");
    expect(steps[3].textContent).toContain("Resolve Quizzes");
    expect(steps[4].textContent).toContain("Update Board");
  });

  test("renders stage cards grid", () => {
    const grid = document.querySelector(".stage-card-grid");
    const cards = document.querySelectorAll(".stage-card");

    expect(grid).not.toBeNull();
    expect(cards.length).toBe(5);
  });

  test("renders key sections", () => {
    expect(document.querySelectorAll("h2").length).toBeGreaterThan(3);
    expect(document.querySelectorAll("h3").length).toBeGreaterThan(5);
  });

  test("contains winning tips section", () => {
    const tips = document.querySelector(".tutorial-tips");

    expect(tips).not.toBeNull();
    expect(tips.textContent).toContain("Winning Tips");
  });
});