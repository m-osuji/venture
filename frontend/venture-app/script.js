
// Loads all index.html features at the same time
async function init() {
  try {
    const [header, footer] = await Promise.all([
      fetch("/header.html").then(res => res.text()),
      fetch("/footer.html").then(res => res.text())
    ]);

    document.getElementById("header").innerHTML = header;
    document.getElementById("footer").innerHTML = footer;

    await loadRoute(window.location.pathname);

    document.getElementById("loader").style.display = "none";
    document.getElementById("app").style.display = "block";

  } catch (err) {
    console.error("Load error:", err);
  }
}

// Displayed web pages and their files
const routes = {
  "/": "home.html",
  "/tutorial": "pages/tutorial.html",
  "/game": "pages/game.html"
};

// Asynch to load all page elements at the same time, less jumpy
async function loadRoute(path) {
  if (path === "/index.html") path = "/";

  const page = routes[path] || "home.html";

  try {
    const res = await fetch("/" + page);
    if (!res.ok) throw new Error("Page not found");

    const data = await res.text();
    document.getElementById("content").innerHTML = data;

  } catch {
    document.getElementById("content").innerHTML = "<h2>404 - Page not found</h2>";
  }
}

// File navigation, did not like js navigate function, now uses global
window.navigate = function (path) {
  history.pushState({}, "", path);
  loadRoute(path);
};

window.onpopstate = () => {
  loadRoute(window.location.pathname);
};

init();

console.log("PATH:", window.location.pathname);