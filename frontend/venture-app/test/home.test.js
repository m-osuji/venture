import fs from "node:fs";

describe("Home Page", () => {
  beforeEach(() => {
    const html = fs.readFileSync(
      new URL("../home.html", import.meta.url),
      "utf8"
    );

    document.body.innerHTML = html;
  });

  test("renders heading", () => {
    expect(document.querySelector("h1").textContent)
      .toBe("Welcome to Venture");
  });

  test("renders buttons", () => {
    const buttons = document.querySelectorAll("button");

    expect(buttons.length).toBe(2);
    expect(buttons[0].textContent).toBe("Start Venture");
    expect(buttons[1].textContent).toBe("Learn More");
  });
});
