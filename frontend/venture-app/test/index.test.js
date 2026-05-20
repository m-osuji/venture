// index.test.js

const fs = require("fs");
const path = require("path");

describe("Index HTML", () => {
  beforeEach(() => {
    const html = fs.readFileSync(
      path.resolve(__dirname, "../index.html"),
      "utf8"
    );

    document.body.innerHTML = html;
  });

  test("renders loader initially", () => {
    const loader = document.getElementById("loader");

    expect(loader).not.toBeNull();
    expect(loader.textContent).toBe("Loading...");
  });

  test("app container exists and is hidden by default", () => {
    const app = document.getElementById("app");

    expect(app).not.toBeNull();
    expect(app.style.display).toBe("none");
  });

  test("has header, content, and footer containers", () => {
    expect(document.getElementById("header")).not.toBeNull();
    expect(document.getElementById("content")).not.toBeNull();
    expect(document.getElementById("footer")).not.toBeNull();
  });

  test("script tag is present and uses module type", () => {
    const script = document.querySelector('script[type="module"]');

    expect(script).not.toBeNull();
    expect(script.getAttribute("src")).toBe("/script.js");
  });

  test("fonts and stylesheets are linked", () => {
    const styles = document.querySelectorAll('link[rel="stylesheet"]');

    expect(styles.length).toBeGreaterThanOrEqual(3);
  });
});