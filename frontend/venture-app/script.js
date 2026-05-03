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

let scrollHandlerAttached = false;

function initScrollIndicator() {
  // Tutorial page navigation bar to be above the footer
  const indicator = document.getElementById("scroll-indicator");
  const progress = document.getElementById("scroll-progress");
  const ball = document.getElementById("scroll-ball");
  const markersContainer = document.getElementById("scroll-markers");
  const sections = document.querySelectorAll("#content h2");

  // Game page for the AI opponent to be above the footer
  const footer = document.getElementById("footer");

  // Always attach scroll logic once but keep doing it for game and tutorial
  if (!scrollHandlerAttached && footer) {
    window.addEventListener("scroll", () => {
      const footerRect = footer.getBoundingClientRect();
      const viewportHeight = window.innerHeight;

      // How much space we want from edges
      const margin = 20;

      // Where fixed elements would sit
      const fixedBottom = viewportHeight - margin;

      // Check collision with footer
      const isColliding = footerRect.top < fixedBottom;

      // Get AI dynamically (important for SPA navigation)
      const opponent = document.getElementById("AI-container");

      // Logic to make AI opponent stay above footer      
      if (opponent) {
        // Footer position relative to viewport
        const footerTop = footer.getBoundingClientRect().top;
        // Max allowed bottom so it doesn't overlap footer
        const maxBottom = window.innerHeight - footerTop + margin;

        if (footerTop < window.innerHeight) {
          // Make fixed onto page above footer instead of below
          opponent.style.position = "fixed";
          opponent.style.bottom = `${Math.max(margin, maxBottom)}px`;
          opponent.style.top = "auto";
        } else {
          // Normal fixed at bottom of page
          opponent.style.position = "fixed";
          opponent.style.bottom = `${margin}px`;
          opponent.style.top = "auto";
        }
      }

      // Tutorial page navigation bar above footer, same logic as above
      const indicator = document.getElementById("scroll-indicator");
      if (indicator) {
        const footerTop = footer.getBoundingClientRect().top;
        const maxBottom = window.innerHeight - footerTop + margin;
        if (footerTop < window.innerHeight) {
          indicator.style.position = "fixed";
          indicator.style.bottom = `${Math.max(margin, maxBottom)}px`;
          indicator.style.top = "auto";
        } else {
          indicator.style.position = "fixed";
          indicator.style.bottom = `${margin}px`;
          indicator.style.top = "auto";
        }
      }

      const textbox = document.getElementById("stage-progresser");
      if (textbox) {
        const footerTop = footer.getBoundingClientRect().top;
        const maxBottom = window.innerHeight - footerTop + margin;
        if (footerTop < window.innerHeight) {
          textbox.style.position = "fixed";
          textbox.style.bottom = `${Math.max(margin, maxBottom)}px`;
          textbox.style.top = "auto";
        } else {
          textbox.style.position = "fixed";
          textbox.style.bottom = `${margin}px`;
          textbox.style.top = "auto";
        }
      }
    });

    scrollHandlerAttached = true;
  }

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
    window.addEventListener("scroll", () => {
      const scrollTop = window.scrollY;
      const docHeight = document.body.scrollHeight - window.innerHeight;
      const indicatorHeight = indicator.offsetHeight;

      const percent = docHeight > 0
        ? (scrollTop + headerHeight) / docHeight
        : 0;

      const y = Math.min(percent * indicatorHeight, indicatorHeight);

      progress.style.height = `${y}px`;
      ball.style.transform = `translate(-50%, -50%) translateY(${y}px)`;
    });
  });
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
      //initLeaderboard();
      initAIInteraction();
    } else {
      if (currentGameModule) {
        currentGameModule.stopGame();
        currentGameModule = null;
      }
    }

    initScrollIndicator();
    // Needed to actually link the scroll event when reloaded
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        window.dispatchEvent(new Event("scroll"));
      });
    });

  } catch {
    document.getElementById("content").innerHTML = "<h2>404 - Page not found</h2>";
  }
}

// AI image controller
function initAIInteraction() {
  const button = document.getElementById("AI-confirm");
  const text = document.getElementById("AI-text");
  const aiImage = document.getElementById("AI");

  if (!button || !text || !aiImage) return;

  button.addEventListener("click", () => {
    text.classList.add("fade-out");
    button.classList.add("fade-out");

    setTimeout(() => {
      // Hide text and button
      text.style.display = "none";
      button.style.display = "none";
    }, 300);

    // Change AI image
    aiImage.src = "../images/AI_happy.png"; 
  });
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