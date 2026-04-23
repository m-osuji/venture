
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

function initScrollIndicator() {
  const indicator = document.getElementById("scroll-indicator");
  const progress = document.getElementById("scroll-progress");
  const ball = document.getElementById("scroll-ball");
  const markersContainer = document.getElementById("scroll-markers");
  const sections = document.querySelectorAll("#content h2");

  if (!indicator || !markersContainer || sections.length === 0) return;

  // Wait until header is actually rendered because of DOM
  function waitForHeaderThenInit(callback) {
    const header = document.querySelector("#header header");

    if (header && header.offsetHeight > 0) {
      callback(header.offsetHeight * 1.2);
    } else {
      requestAnimationFrame(() => waitForHeaderThenInit(callback));
    }
  }

  waitForHeaderThenInit((headerHeight) => {
    markersContainer.innerHTML = "";

    const docHeight = document.body.scrollHeight - window.innerHeight;
    const indicatorHeight = indicator.offsetHeight;

    const footer = document.getElementById("footer");

    // Adding each marker
    sections.forEach(section => {
      const marker = document.createElement("div");
      marker.classList.add("marker");

      const rect = section.getBoundingClientRect();
      const absoluteTop = rect.top + window.scrollY;

      const percent = absoluteTop / docHeight;
      const y = percent * indicatorHeight;

      marker.style.top = `${y}px`;
      marker.title = section.innerText;

      // When clicked, navigate to correct page location
      marker.onclick = () => {
        window.scrollTo({
          top: section.offsetTop - headerHeight,
          behavior: "smooth"
        });
      };

      markersContainer.appendChild(marker);
    });

    // Scrolling updates the page navigation bar
    window.onscroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.body.scrollHeight - window.innerHeight;
      const indicatorHeight = indicator.offsetHeight;

      const percent = docHeight > 0
        ? (scrollTop + headerHeight) / docHeight
        : 0;

      const y = Math.min(percent * indicatorHeight, indicatorHeight);

      progress.style.height = `${y}px`;
      ball.style.transform = `translate(-50%, -50%) translateY(${y}px)`;

      // So there is no footer overlap
      const footerRect = footer.getBoundingClientRect();
      const viewportHeight = window.innerHeight;

      // How much the footer overlaps into the viewport
      const overlap = Math.max(0, viewportHeight - footerRect.top);

      if (overlap > 0) {
        // Push indicator up smoothly
        indicator.style.transform = `translateY(-${overlap}px)`;
      } else {
        indicator.style.transform = `translateY(0)`;
      }
    };
  });
}

//Leaderboard loading
function initLeaderboard() {
  const button = document.getElementById("leaderboard-toggle");
  const panel = document.getElementById("leaderboard-panel");
  const list = document.getElementById("leaderboard-list");

  if (!button) return;

  button.onclick = () => {
    panel.classList.toggle("hidden");
  };

  // Example dummy data
  const data = [
    { name: "Alice", score: 120 },
    { name: "Bob", score: 95 },
    { name: "You", score: 80 }
  ];

  list.innerHTML = data
    .map(player => `<li>${player.name}: ${player.score}</li>`)
    .join("");
}

// Asynch to load all page elements at the same time, less jumpy
let currentGameModule = null;
async function loadRoute(path) {
  if (path === "/index.html") path = "/";

  const page = routes[path] || "home.html";

  try {
    const res = await fetch("/" + page);
    if (!res.ok) throw new Error("Page not found");

    const data = await res.text();
    document.getElementById("content").innerHTML = data;

    if (path === "/game") {
      currentGameModule = await import("/board.js");
      currentGameModule.startGame();
      initLeaderboard();
    } else {
      if (currentGameModule) {
        currentGameModule.stopGame();
        currentGameModule = null;
      }
    }

    initScrollIndicator();

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