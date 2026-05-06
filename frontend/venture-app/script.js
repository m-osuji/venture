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

      const setup = document.getElementById("game-setup-overlay");
      if (setup) {
        const footerTop = footer.getBoundingClientRect().top;
        const maxBottom = window.innerHeight - footerTop;
        if (footerTop < window.innerHeight) {
          setup.style.position = "fixed";
          setup.style.bottom = `${Math.max(0, maxBottom)}px`;
          setup.style.top = "auto";
        } else {
          setup.style.position = "fixed";
          setup.style.bottom = `0px`;
          setup.style.top = "auto";
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
// Replace the existing initAIInteraction function with this updated version
function initAIInteraction() {
  const button = document.getElementById("AI-confirm");
  const text = document.getElementById("AI-text");
  const aiImage = document.getElementById("AI");
  const setupOverlay = document.getElementById("game-setup-overlay");

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
    
    // Show the game setup overlay with dark background
    if (setupOverlay) {
      setupOverlay.style.display = "flex";
      
      // Initialize team name inputs based on selected team count
      updateTeamNameInputs();
      
      // Set up event listeners for the setup form
      setupGameEventListeners();
    }
  });
}

// New function to update team name inputs based on selected count
function updateTeamNameInputs() {
  const teamCountSelect = document.getElementById("teamCountSelect");
  const teamNamesContainer = document.getElementById("teamNamesContainer");
  
  if (!teamCountSelect || !teamNamesContainer) return;
  
  const teamCount = parseInt(teamCountSelect.value);
  teamNamesContainer.innerHTML = "";
  
  for (let i = 0; i < teamCount; i++) {
    const teamDiv = document.createElement("div");
    teamDiv.className = "team-input-group";
    teamDiv.innerHTML = `
      <span class="team-number">Team ${i + 1}:</span>
      <input type="text" id="teamName${i}" placeholder="Enter team name" value="Team ${String.fromCharCode(65 + i)}">
    `;
    teamNamesContainer.appendChild(teamDiv);
  }
}

// Function for selecting AI opponent on and off
function setupAIOptionListener() {
  const aiYesRadio = document.getElementById("AI-player-yes");
  const aiNoRadio = document.getElementById("AI-player-no");
  const difficultyContainer = document.getElementById("difficulty-container");
  
  if (!aiYesRadio || !aiNoRadio || !difficultyContainer) return;
  
  function toggleDifficulty() {
    if (aiYesRadio.checked) {
      difficultyContainer.style.display = "block";
    } else {
      difficultyContainer.style.display = "none";
    }
  }
  
  aiYesRadio.addEventListener("change", toggleDifficulty);
  aiNoRadio.addEventListener("change", toggleDifficulty);
  
  // Initial state
  toggleDifficulty();
}

function setupDifficultyButtons() {
  const difficultyBtns = document.querySelectorAll(".difficulty-btn");
  const selectedDifficultyDiv = document.getElementById("selected-difficulty");
  let currentDifficulty = "medium"; // default
  
  difficultyBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      // Remove selected class from all buttons
      difficultyBtns.forEach(b => b.classList.remove("selected"));
      // Add selected class to clicked button
      btn.classList.add("selected");
      
      // Store selected difficulty
      currentDifficulty = btn.getAttribute("data-difficulty");
      
      // Display selection
      if (selectedDifficultyDiv) {
        const difficultyText = {
          easy: "🌿 Easy Mode - AI makes occasional mistakes",
          medium: "⚡ Medium Mode - Balanced AI decisions",
          hard: "🔥 Hard Mode - Optimized AI strategy"
        };
        selectedDifficultyDiv.textContent = difficultyText[currentDifficulty];
      }
    });
  });
  // Set default selection (Medium)
  const defaultBtn = document.querySelector('.difficulty-btn[data-difficulty="medium"]');
  if (defaultBtn) {
    defaultBtn.classList.add("selected");
    if (selectedDifficultyDiv) {
      selectedDifficultyDiv.textContent = "⚡ Medium Mode - Balanced AI decisions";
    }
  }
  
  return () => currentDifficulty;
}

// New function to set up game event listeners
function setupGameEventListeners() {
  const teamCountSelect = document.getElementById("teamCountSelect");
  const startButton = document.getElementById("startGameSetupBtn");
  const cancelButton = document.getElementById("cancelSetupBtn");
  const setupOverlay = document.getElementById("game-setup-overlay");
  
  if (teamCountSelect) {
    // Remove old listener to prevent duplicates
    teamCountSelect.removeEventListener("change", updateTeamNameInputs);
    teamCountSelect.addEventListener("change", updateTeamNameInputs);
  }

  setupAIOptionListener();
  setupDifficultyButtons();
  
  if (startButton) {
    startButton.removeEventListener("click", startGameHandler);
    startButton.addEventListener("click", startGameHandler);
  }
  
  if (cancelButton) {
    cancelButton.removeEventListener("click", cancelGameSetup);
    cancelButton.addEventListener("click", cancelGameSetup);
  }

  if (setupOverlay) {
    // Remove old listener to prevent duplicates
    setupOverlay.removeEventListener("click", overlayClickHandler);
    setupOverlay.addEventListener("click", overlayClickHandler);
    
    // Prevent clicks on the setup card from bubbling up to the overlay
    const setupCard = setupOverlay.querySelector(".setup-card");
    if (setupCard) {
      setupCard.removeEventListener("click", stopPropagation);
      setupCard.addEventListener("click", stopPropagation);
    }
  }
}

function stopPropagation(event) {
  event.stopPropagation();
}

function overlayClickHandler(event) {
  cancelGameSetup();
}

// Function to handle game start
async function startGameHandler() {
  const teamCount = parseInt(document.getElementById("teamCountSelect").value);
  const teamNames = [];
  
  // Collect all team names from the UI
  for (let i = 0; i < teamCount; i++) {
    const teamInput = document.getElementById(`teamName${i}`);
    const teamName = teamInput ? teamInput.value.trim() : `Team ${String.fromCharCode(65 + i)}`;
    teamNames.push(teamName || `Team ${String.fromCharCode(65 + i)}`);
  }

  const aiYesRadio = document.getElementById("AI-player-yes");
  const includeAI = aiYesRadio ? aiYesRadio.checked : false;

  // Get difficulty (only if AI is included)
  let difficulty = "medium"; // default
  if (includeAI) {
    const selectedBtn = document.querySelector('.difficulty-btn.selected');
    if (selectedBtn) {
      difficulty = selectedBtn.getAttribute('data-difficulty');
    }
  }

  // Format data for backend
  const backendTeams = [];
  for (let i = 0; i < teamNames.length; i++) {
    backendTeams.push({
      id: i + 1,
      name: teamNames[i],
      colour: i === 0 ? "#FF0000" : "#0000FF", // Placeholder colors
      is_ai: false
    });
  }

  // If the user selected AI, add the AI as the final team
  if (includeAI) {
    backendTeams.push({
      id: backendTeams.length + 1,
      name: "IBM Granite AI",
      colour: "#00FF00",
      is_ai: true
    });
  }

  // Build the final payload for the Python backend
  const backendPayload = {
    teams: backendTeams,
    difficulty: difficulty,
    mode: 'full'
  };

  // Close the setup menu immediately so the screen doesn't freeze
  const setupOverlay = document.getElementById("game-setup-overlay");
  if (setupOverlay) {
    setupOverlay.style.display = "none";
  }

  // -----------------------------------------------
  // FETCH: Send data to Python, THEN load the board
  // -----------------------------------------------
  try {
    const response = await fetch('http://localhost:5000/api/game/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendPayload)
    });

    if (!response.ok) throw new Error("Failed to start game on backend");

    const result = await response.json();
    console.log("✅ Game created on backend!", result);

    // Only navigate to the map after Python confirms the JSON is ready
    window.navigate('/game');

  } catch (error) {
    console.error("Error starting game:", error);
    alert("Failed to connect to the game server. Is your Python backend running?");
    
    // Un-hide the menu if it failed so they can try again
    if (setupOverlay) setupOverlay.style.display = "flex";
  }
}

// Function to cancel game setup
function cancelGameSetup() {
  const setupOverlay = document.getElementById("game-setup-overlay");
  const text = document.getElementById("AI-text");
  const button = document.getElementById("AI-confirm");
  
  if (setupOverlay) {
    setupOverlay.style.display = "none";
  }
  
  // Restore the AI text and button if needed
  if (text && button) {
    text.style.display = "block";
    button.style.display = "block";
    text.classList.remove("fade-out");
    button.classList.remove("fade-out");
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