import { TournamentQuiz } from './quiz.js';

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

// Team colours if nothing is selected
const DEFAULT_TEAM_COLOURS = [
  "#EE672B",
  "#467096",
  "#2A9D8F",
  "#D62839",
  "#7B2CBF",
  "#F4A261"
];

const API_BASE =
  window.VENTURE_API_BASE ||
  import.meta.env.VITE_VENTURE_API_BASE ||
  "http://localhost:5000";

// Question bank loaded from CSV format
let questionBank = [];
let questionBankPromise = null;

// Load questions from the provided data
function loadFallbackQuestionBank() {
  questionBank = [];
  const csvData = [
    ["SkillsBuild Course","question_id","topic","content","option_1","option_2","option_3","option_4","answer","difficulty_level"],
    ["AI in Legal: From Research to Results","2","AI in Law","A community center hires Rachel to assist multiple families appeal denied government benefits. With no additional staff to manage the caseload, she uses AI to autofill forms, flag missing data, and automate the sorting of case files based on deadlines. How is AI helping Rachel in this case to assist the families?","It is helping her skip the need for client interviews and documentation.","It is helping her guarantee successful outcomes for all benefit appeals.","It is helping her to automatically approve denied benefit applications.","It is helping her reduce costs and make services more affordable.","option_4","medium"],
    ["Elevate education with ai","2","Education","Élodie is a middle school teacher preparing reading materials with help from a general-purpose AI tool. She avoids entering student names, grades, or personal details into the system and instead uses only general class information. Which best practice is Élodie following?","Verify accuracy","Be transparent","Use AI to support, not replace","Protect student privacy","option_4","easy"],
    ["The Power of Personalized Finance with AI","4","Ethics, AI","A weekly summary notifies a married couple that their grocery spending has increased by 15% since they moved to a new city. Match this personal finance scenario to the applicable AI enhancement.","Customized investment advice","Proactive fraud detection","Conversational financial assistance","Smart spending insights","option_4","easy"],
    ["The Power of Personalized Finance with AI","5","Ethics, AI, Cybersecurity","After detecting large, consistent balances in a checking account, a banking app suggests opening a high-yield savings account that better fits the user’s situation. Match this personal finance scenario to the applicable AI enhancement.","Customized investment advice","Personalized product recommendations","Conversational financial assistance","Smart spending insights","option_2","hard"],
    ["The Power of Personalized Finance with AI","6","Ethics, AI","A user asks a financial advisory app, 'Should I pay off my student loans or start investing?' The app provides guidance based on the user's income and loan interest rates. Match this personal finance scenario to the applicable AI enhancement.","Customized investment advice","Proactive fraud detection","Conversational financial assistance","Smart spending insights","option_3","easy"],
    ["The Power of Personalized Finance with AI","7","Ethics, AI, Cybersecurity","A credit card holder receives an alert stating, 'Your usual coffee purchase was declined after an ATM withdrawal occurred 200 miles away'. Match this personal finance scenario to the applicable AI enhancement.","Customized investment advice","Proactive fraud detection","Conversational financial assistance","Smart spending insights","option_2","easy"],
    ["The Power of Personalized Finance with AI","8","Ethics, AI","An investment platform explains why a low-risk bond fund fits a long-term retirement timeline and conservative investment approach.","Customized investment advice","Proactive fraud detection","Conversational financial assistance","Smart spending insights","option_1","easy"],
    ["The Power of Personalized Finance with AI","9","AI, Cybersecurity","An app reviews several months of spending and sends a message explaining why entertainment costs increased after a recent subscription change. Match the personalization scenario with the corresponding AI technology.","Machine learning + large language models","Large language models","Machine learning","Natural language processing","option_1","hard"],
    ["The Power of Personalized Finance with AI","10","AI, Cybersecurity","An app explains, 'You've spent more on dining out this month. Here are three ways to reduce those costs.' Match the personalization scenario with the corresponding AI technology.","Machine learning + large language models","Large language models","Machine learning","Natural language processing","option_2","easy"],
    ["Elevate education with ai","11","Education","Chen uses AI to help her evaluate student essays. The AI tool provides detailed comments on each essay based on her rubric, giving her more time to meet with students who need extra guidance.","Decision-making AI","Predictive AI","Generative AI","Computer vision","option_3","easy"],
    ["The Power of Personalized Finance with AI","12","AI, Cybersecurity","An app answers the question, 'Should I pay off debt or start investing?' by using income, loan rates, and savings goals. Match the personalization scenario with the corresponding AI technology.","Natural language processing","Machine learning","Large language models","Natural language processing + large language models","option_4","medium"],
    ["The Power of Personalized Finance with AI","13","AI, Cybersecurity","Lakshmi starts a new job with a longer commute. Now, her banking app shows a weekly update highlighting her increased spending on transportation. It also suggests that Lakshmi adjust her monthly budget accordingly. Which AI personalization enhancement does this scenario illustrate?","Personalized product recommendations","Proactive fraud detection","Smart spending insights","Conversational financial assistance","option_3","medium"],
    ["Elevate education with ai","14","Education","Jordan is using an AI tool to help prepare a lesson on the solar system. In his prompt, he instructs the AI tool to draft the material from his point of view, as a middle school science teacher, so the content aligns with how he would present it in class. Which prompt pattern is Jordan using?","Alternative approaches pattern","Flipped interaction pattern","Persona pattern","Template pattern","option_3","hard"],
    ["Elevate education with ai","15","Education","Aarav is a vice-principal who uses an AI tool to generate a first draft of the monthly staff update. Before sending it out, he carefully reviews all AI-generated sections to ensure they align with school goals and do not contain errors. Which best practice is Aarav following?","Verify accuracy","Maintain human oversite","Protect student privacy","Use ai to support, not replace","option_2","medium"],
    ["Elevate education with ai","16","Education","Selena is using an AI tool to help create a new unit on ancient civilizations. She needs the AI tool to produce a lesson plan with a clear, consistent structure, so she provides a specific format in her prompt. The response should include objectives, materials, activities, and assessments, in that order, and include complete content for each section.","Cognitive verifier pattern","Persona pattern","Alternative approaches pattern","Template pattern","option_4","easy"],
    ["The Power of Personalized Finance with AI","17","AI, Cybersecurity","An investment platform reviews a customer's age, income, savings goals, and risk tolerance. Then, it presents a long-term portfolio strategy with a clear explanation of how this strategy aligns to those goals. Which AI personalization enhancement does this scenario illustrate?","Conversational financial assistance","Smart spending insights","Proactive fraud detection","Customized investment advice","option_4","medium"],
    ["AI in Legal: From Research to Results","18","AI in Law","Associates at a large law firm spend a considerable amount of their work hours on document review and fact-checking. With AI-enabled automation, the time spent on these tasks drop, freeing up almost 10 hours per week. What benefit does this provide?","Increases productivity.","Enhances accessibility.","Improves legal research.","Strengthens case outcomes.","option_1","easy"],
    ["AI in Legal: From Research to Results","19","AI in Law","Saul is working on a contract dispute case between companies located in different states and countries, each governed by its own legal system. He uses AI to extract relevant laws and statutes from multiple data sources, gathering insights accurately and quickly. What benefit does this provide?","Increases productivity.","Enhances accessibility.","Improves legal research.","Strengthens case outcomes.","option_3","easy"]
  ];

  // Skip header row and convert to objects
  for (let i = 1; i < csvData.length; i++) {
    const row = csvData[i];
    questionBank.push({
      id: parseInt(row[1]),
      course: row[0],
      topic: row[2],
      content: row[3],
      options: {
        a: row[4],
        b: row[5],
        c: row[6],
        d: row[7]
      },
      correct: row[8], // e.g., "option_1", "option_2", etc.
      difficulty: row[9]
    });
  }
  
  console.log(`Loaded ${questionBank.length} questions`);
}

async function loadQuestionBankFromBackend() {
  const response = await fetch(`${API_BASE}/api/questions?shuffle=true`);
  if (!response.ok) {
    throw new Error("Failed to load questions from backend");
  }

  const payload = await response.json();
  questionBank = Array.isArray(payload.questions) ? payload.questions : [];
  console.log(`Loaded ${questionBank.length} questions from backend`);
  return questionBank;
}

async function ensureQuestionBankLoaded() {
  if (questionBank.length) {
    return questionBank;
  }

  if (!questionBankPromise) {
    questionBankPromise = loadQuestionBankFromBackend().catch((error) => {
      console.warn("Falling back to bundled question bank:", error);
      loadFallbackQuestionBank();
      return questionBank;
    });
  }

  return questionBankPromise;
}

// Helper function to get the correct option letter
function getCorrectLetter(correctOption) {
  const mapping = {
    'option_1': 'a',
    'option_2': 'b',
    'option_3': 'c',
    'option_4': 'd'
  };
  return mapping[correctOption] || 'a';
}

// Get random questions filtered by difficulty
function getRandomQuestions(count, difficulty = null) {
  let filtered = [...questionBank];
  if (difficulty && difficulty !== 'all') {
    filtered = filtered.filter(q => q.difficulty === difficulty);
  }
  
  // Shuffle
  for (let i = filtered.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [filtered[i], filtered[j]] = [filtered[j], filtered[i]];
  }
  
  return filtered.slice(0, count);
}

// Load questions at startup
void ensureQuestionBankLoaded();

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

      const tournament = document.getElementById("tournament-overlay");
      if (tournament) {
        const footerTop = footer.getBoundingClientRect().top;
        const maxBottom = window.innerHeight - footerTop;
        if (footerTop < window.innerHeight) {
          tournament.style.position = "fixed";
          tournament.style.bottom = `${Math.max(0, maxBottom)}px`;
          tournament.style.top = "auto";
        } else {
          tournament.style.position = "fixed";
          tournament.style.bottom = `0px`;
          tournament.style.top = "auto";
        }
      }

      const selection = document.getElementById("market-overlay");
      if (selection) {
        const footerTop = footer.getBoundingClientRect().top;
        const maxBottom = window.innerHeight - footerTop;
        if (footerTop < window.innerHeight) {
          selection.style.position = "fixed";
          selection.style.bottom = `${Math.max(0, maxBottom)}px`;
          selection.style.top = "auto";
        } else {
          selection.style.position = "fixed";
          selection.style.bottom = `0px`;
          selection.style.top = "auto";
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
  // Remove tournament and market overlays when changing pages
  const tournamentOverlay = document.getElementById("tournament-overlay");
  const marketOverlay = document.getElementById("market-overlay");
  const quizOverlay = document.getElementById("quiz-overlay");

  if (tournamentOverlay) tournamentOverlay.remove();
  if (marketOverlay) marketOverlay.remove();
  if (quizOverlay) quizOverlay.remove();

  // Also clear any timer intervals
  if (window.countdownInterval) {
    clearInterval(window.countdownInterval);
    window.countdownInterval = null;
  }

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
      initAIInteraction();
      // Also clear game timer
      if (gameTimerInterval) {
        clearInterval(gameTimerInterval);
        gameTimerInterval = null;
      }
      const gameTimer = document.getElementById("game-timer");
      if (gameTimer) gameTimer.remove();
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

  } catch (error) {
    console.error("Error loading page:", error);
    document.getElementById("content").innerHTML = "<h2>404 - Page not found</h2>";
  }
}

// AI image controller
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

// Function to update team name inputs based on selected count as well as team colours
function updateTeamNameInputs() {
  const teamCountSelect = document.getElementById("teamCountSelect");
  const teamNamesContainer = document.getElementById("teamNamesContainer");
  
  if (!teamCountSelect || !teamNamesContainer) return;
  
  const teamCount = parseInt(teamCountSelect.value);
  teamNamesContainer.innerHTML = "";
  
  // Predefined color options for teams
  const colorOptions = [
    "#EE672B", // Orange
    "#467096", // Blue
    "#2A9D8F", // Teal
    "#D62839", // Red
    "#7B2CBF", // Purple
    "#F4A261"  // Gold
  ];
  
  for (let i = 0; i < teamCount; i++) {
    const teamDiv = document.createElement("div");
    teamDiv.className = "team-input-group";
    teamDiv.style.display = "flex";
    teamDiv.style.alignItems = "center";
    teamDiv.style.gap = "10px";
    teamDiv.style.marginBottom = "12px";
    
    teamDiv.innerHTML = `
      <span class="team-number">Team ${i + 1}:</span>
      <input type="text" id="teamName${i}" placeholder="Enter team name" value="Team ${String.fromCharCode(65 + i)}" style="flex: 1; padding: 8px 12px; border: 1px solid #ddd; border-radius: 8px;">
      <div class="team-color-picker" style="position: relative;">
        <div class="color-preview" data-team-index="${i}" style="width: 40px; height: 40px; border-radius: 8px; background: ${colorOptions[i % colorOptions.length]}; cursor: pointer; border: 2px solid #ddd; transition: all 0.2s ease;"></div>
        <input type="color" id="teamColor${i}" value="${colorOptions[i % colorOptions.length]}" style="position: absolute; opacity: 0; width: 40px; height: 40px; cursor: pointer; top: 0; left: 0;">
      </div>
    `;
    
    teamNamesContainer.appendChild(teamDiv);
    
    // Color picker functionality
    const colorInput = teamDiv.querySelector(`#teamColor${i}`);
    const colorPreview = teamDiv.querySelector('.color-preview');
    
    colorInput.addEventListener('input', (e) => {
      colorPreview.style.background = e.target.value;
    });
    
    colorPreview.addEventListener('click', () => {
      colorInput.click();
    });
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

// Function to setup game length buttons
function setupGameLengthButtons() {
  const lengthBtns = document.querySelectorAll(".length-btn");
  const selectedLengthDiv = document.getElementById("selected-length");
  let currentLength = "freeplay";
  
  lengthBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      lengthBtns.forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
      currentLength = btn.getAttribute("data-length");
      
      if (selectedLengthDiv) {
        const lengthText = {
          short: "Short game - 20 minute time limit",
          medium: "Medium game - 1 hour time limit",
          freeplay: "Freeplay - No time limit"
        };
        selectedLengthDiv.textContent = lengthText[currentLength];
      }
    });
  });
  
  // Set default selection (Freeplay)
  const defaultBtn = document.querySelector('.length-btn[data-length="freeplay"]');
  if (defaultBtn) {
    defaultBtn.classList.add("selected");
    if (selectedLengthDiv) {
      selectedLengthDiv.textContent = "Freeplay - No time limit";
    }
  }
  
  return () => currentLength;
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
  setupGameLengthButtons();
  
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
  const teamColors = [];
  
  // Collect all team names and colors from the UI
  for (let i = 0; i < teamCount; i++) {
    const teamInput = document.getElementById(`teamName${i}`);
    const teamName = teamInput ? teamInput.value.trim() : `Team ${String.fromCharCode(65 + i)}`;
    teamNames.push(teamName || `Team ${String.fromCharCode(65 + i)}`);
    
    const colorInput = document.getElementById(`teamColor${i}`);
    const teamColor = colorInput ? colorInput.value : DEFAULT_TEAM_COLOURS[i % DEFAULT_TEAM_COLOURS.length];
    teamColors.push(teamColor);
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

  // Get game length
  const lengthBtns = document.querySelectorAll(".length-btn");
  let gameLength = "freeplay";
  lengthBtns.forEach(btn => {
    if (btn.classList.contains("selected")) {
      gameLength = btn.getAttribute("data-length");
    }
  });
  
  // Format data for backend
  const backendTeams = [];
  for (let i = 0; i < teamNames.length; i++) {
    backendTeams.push({
      id: i + 1,
      name: teamNames[i],
      colour: DEFAULT_TEAM_COLOURS[i] || "#467096",
      is_ai: false
    });
  }

  // If the user selected AI, add the AI as the final team
  if (includeAI) {
    backendTeams.push({
      id: backendTeams.length + 1,
      name: "IBM Granite AI",
      colour: "#1b9aaa",
      is_ai: true
    });
  }

  // Build the final payload for the Python backend
  const backendPayload = {
    teams: backendTeams,
    difficulty: difficulty,
    mode: 'full'
  };

  const apiBase = API_BASE;
  const startEndpoint = `${apiBase}/api/game/start`;

  // Close the setup menu immediately
  const setupOverlay = document.getElementById("game-setup-overlay");
  if (setupOverlay) {
    setupOverlay.style.display = "none";
  }

  // Save the game config with the correct structure for the quiz
  const gameConfigForQuiz = {
    teamCount: teamCount,
    teamNames: teamNames,
    teamColors: teamColors,
    includeAI: includeAI,
    aiDifficulty: difficulty,
    gameLength: gameLength,
    timestamp: new Date().toISOString()
  };
  
  // Save to localStorage for the quiz to use
  localStorage.setItem("ventureGameConfig", JSON.stringify(gameConfigForQuiz));
  localStorage.setItem("backendGameConfig", JSON.stringify(backendPayload));
  
  // Start game timer immediately
  startGameTimer(gameLength);

  // -----------------------------------------------
  // FETCH: Send data to Python
  // -----------------------------------------------
  try {
    const response = await fetch(startEndpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(backendPayload)
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      throw new Error(errorPayload.error || "Failed to start game on backend");
    }

    const result = await response.json();
    console.log("✅ Game created on backend!", result);

  } catch (error) {
    console.error("Error starting game:", error);
    alert("Failed to connect to the game server. Is your Python backend running?\n\nContinuing with local game.");
  }
  
  console.log("Game configuration for quiz:", gameConfigForQuiz);
  
  // Start the quiz
  initQuizSetup();
}

// Function to cancel game setup
function cancelGameSetup() {
  const setupOverlay = document.getElementById("game-setup-overlay");
  const image = document.getElementById("AI")
  const text = document.getElementById("AI-text");
  const button = document.getElementById("AI-confirm");
  
  if (setupOverlay) {
    setupOverlay.style.display = "none";
  }

  if (image) {
    image.src = "../images/AI_thinking.png";
  }
  
  // Restore the AI text and button if needed
  if (text && button) {
    text.style.display = "block";
    button.style.display = "block";
    text.classList.remove("fade-out");
    button.classList.remove("fade-out");
  }
}

// Text to explain initial quiz taking
function initQuizSetup() {
  const aiText = document.getElementById("AI-text");
  const aiButton = document.getElementById("AI-confirm");
  const aiImage = document.getElementById("AI");
  
  if (!aiText || !aiButton) return;

  // Change AI text to explain the quiz
  aiText.innerHTML = "The game begins with a structured quiz to establish the sequence of team participation. Teams will be evaluated on both speed and accuracy, and those demonstrating the strongest performance will be granted first choice of market entry. This approach ensures a fair and merit-based process as you progress through the initial stages of Venture.";

  // Make sure text and button are visible
  aiText.style.display = "block";
  aiButton.style.display = "block";
  aiText.classList.remove("fade-out");
  aiButton.classList.remove("fade-out");

  // Remove existing event listeners and add new one for quiz
  const newButton = aiButton.cloneNode(true);
  aiButton.parentNode.replaceChild(newButton, aiButton);
  
  newButton.addEventListener("click", () => {
    void startTeamQuiz();
  });
}

// Tournament system with round robin between all teams
async function startTeamQuiz() {
    if (window.location.pathname !== "/game") return;

    await ensureQuestionBankLoaded();
    if (!questionBank.length) {
        alert("No quiz questions are available right now.");
        return;
    }

    const savedConfig = localStorage.getItem("ventureGameConfig");
    if (!savedConfig) {
        console.error("No game configuration found");
        return;
    }
    
    const gameConfig = JSON.parse(savedConfig);
    const teamNames = gameConfig.teamNames;
    
    if (teamNames.length < 2) {
        alert("Tournament requires at least 2 teams. Please restart game setup.");
        return;
    }
    
    // Create and start the tournament
    const tournament = new TournamentQuiz(
        teamNames,
        questionBank,
        getCorrectLetter,
        getRandomQuestions
    );
    
    tournament.start((rankedTeams, tournamentResults) => {
        console.log("Tournament complete!", rankedTeams);
        // Store results
        localStorage.setItem("tournamentResults", JSON.stringify({
            tournamentRankings: rankedTeams,
            allMatchups: tournamentResults,
            timestamp: new Date().toISOString()
        }));
        // Start market selection
        startMarketSelection(rankedTeams);
    });
}

// Function to update AI text for next team
function updateAITextForNextTeam(teamName) {
  const aiText = document.getElementById("AI-text");
  if (aiText) {
    aiText.innerHTML = `🤝 Now it's <strong>${teamName}'s</strong> turn! Answer the business questions to earn points and determine your starting advantage. Good luck!`;
  }
}

// Calculate and display quiz results
function calculateQuizResults(teamScoresArg, allTeamResponsesArg, includeAI) {
  const container = document.getElementById("quiz-question-container");
  const progress = document.getElementById("quiz-progress");
  const quizActions = document.getElementById("quiz-actions");
  const resultsDiv = document.getElementById("quiz-results");
  const scoreResults = document.getElementById("score-results");
  const orderResults = document.getElementById("order-results");
  const timerDisplay = document.getElementById("quiz-timer");
  
  if (!container || !resultsDiv) return;

  // Hide timer
  if (timerDisplay) timerDisplay.style.display = "none";
  
  // Calculate team order based on scores
  const teamOrder = Object.entries(teamScoresArg).map(([team, score]) => {
    const totalTime = allTeamResponsesArg[team].reduce((sum, r) => sum + r.timeTaken, 0);
    return { team, score, totalTime };
  }).sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score;
    return a.totalTime - b.totalTime; // Tie breaker: faster total time wins
  });
  
  // Display individual team performance
  if (scoreResults) {
    scoreResults.innerHTML = "<h4>📊 Team Performance:</h4>";
    teamOrder.forEach((item, index) => {
      const teamResponsesData = allTeamResponsesArg[item.team];
      const correctCount = teamResponsesData.filter(r => r.isCorrect).length;
      const avgTime = (item.totalTime / teamResponsesData.length).toFixed(1);
      
      scoreResults.innerHTML += `
        <div style="margin-bottom: 15px; padding: 10px; background: #f9f9f9; border-radius: 10px; border-left: 4px solid ${index === 0 ? '#FFD700' : index === 1 ? '#C0C0C0' : index === 2 ? '#CD7F32' : '#467096'}">
          <strong>${index === 0 ? '🥇 ' : index === 1 ? '🥈 ' : index === 2 ? '🥉 ' : ''}${item.team}</strong><br>
          📝 Score: ${item.score} points | ✅ Correct: ${correctCount}/${teamResponsesData.length}<br>
          ⏱️ Average response time: ${avgTime} seconds
        </div>
      `;
    });
  }

  // Display starting order
  if (orderResults) {
    orderResults.innerHTML = "<h4>🎲 Starting Order (Based on Quiz Performance):</h4><ol>";
    teamOrder.forEach((item, index) => {
      orderResults.innerHTML += `<li><strong>${item.team}</strong> (${item.score} points)`;
      if (index === 0) orderResults.innerHTML += " - 🥇 First move advantage!";
      if (index === teamOrder.length - 1) orderResults.innerHTML += " - 🥲 Last pick";
      orderResults.innerHTML += `</li>`;
    });
    orderResults.innerHTML += "</ol>";
  }
  
  // Add AI information if included
  if (includeAI && orderResults) {
    const savedConfig = localStorage.getItem("ventureGameConfig");
    let aiDifficulty = "medium";
    if (savedConfig) {
      const config = JSON.parse(savedConfig);
      aiDifficulty = config.aiDifficulty || "medium";
    }
    orderResults.innerHTML += `<p style="margin-top: 15px; padding: 10px; background: #f0f0f0; border-radius: 10px;">
      🤖 <strong>AI Opponent:</strong> Playing at ${aiDifficulty?.toUpperCase() || 'MEDIUM'} difficulty<br>
      🎯 The AI will adapt its strategy based on your quiz performance!
    </p>`;
  }
  
  // Hide question container, show results
  container.style.display = "none";
  progress.style.display = "none";
  quizActions.style.display = "none";
  resultsDiv.style.display = "block";

  // Update AI text
  const aiText = document.getElementById("AI-text");
  if (aiText) {
    aiText.innerHTML = `🎉 Quiz complete! Based on your performance, I've calculated the starting order. ${teamOrder[0]?.team || "The first team"} takes the lead with ${teamOrder[0]?.score || 0} points! Click 'Begin Game' to start your Venture journey!`;
  }
  
  // Store results in localStorage
  localStorage.setItem("quizResults", JSON.stringify({
    teamOrder: teamOrder,
    teamScores: teamScoresArg,
    teamResponses: allTeamResponsesArg,
    timestamp: new Date().toISOString()
  }));

  // Add start game button listener
  const startGameQuizBtn = document.getElementById("start-game-quiz");
  if (startGameQuizBtn) {
    startGameQuizBtn.onclick = () => {
      const quizOverlay = document.getElementById("quiz-overlay");
      if (quizOverlay) {
        quizOverlay.remove();
      }
      alert(`🎮 Game is ready!\n\nStarting Order:\n${teamOrder.map((t, i) => `${i+1}. ${t.team} (${t.score} points)`).join('\n')}\n\nThe board will now be set up according to your quiz results.`);
    };
  }
}

// Game timer variables
let gameTimerInterval = null;
let gameTimeRemaining = 0;
let gameStartTime = null;
let isGameTimed = false;

function startGameTimer(gameLength) {
  if (window.location.pathname !== "/game") {
    return
  }
  console.log("startGameTimer called with gameLength:", gameLength);

  // Remove existing timer if any
  const existingTimer = document.getElementById("game-timer");
  if (existingTimer) existingTimer.remove();
  
  // Create timer display
  const timerDisplay = document.createElement("div");
  timerDisplay.id = "game-timer";
  
  const stageIndicator = document.getElementById("stage-indicator");
  stageIndicator.appendChild(timerDisplay);
  
  if (gameLength === "short") {
    isGameTimed = true;
    gameTimeRemaining = 20 * 60; // 20 minutes in seconds
    updateGameTimerDisplay();
    gameTimerInterval = setInterval(() => {
      if (gameTimeRemaining > 0) {
        gameTimeRemaining--;
        updateGameTimerDisplay();
        
        // Warning when 5 minutes left
        if (gameTimeRemaining <= 300) {
          timerDisplay.classList.add("warning");
        }
        
        if (gameTimeRemaining <= 0) {
          clearInterval(gameTimerInterval);
          gameTimerInterval = null;
          alert("TIME'S UP! The game has ended.");
          // Add game end logic here
        }
      }
    }, 1000);
  } else if (gameLength === "medium") {
    isGameTimed = true;
    gameTimeRemaining = 60 * 60; // 1 hour in seconds
    updateGameTimerDisplay();
    gameTimerInterval = setInterval(() => {
      if (gameTimeRemaining > 0) {
        gameTimeRemaining--;
        updateGameTimerDisplay();
        
        if (gameTimeRemaining <= 600) {
          timerDisplay.classList.add("warning");
        }
        
        if (gameTimeRemaining <= 0) {
          clearInterval(gameTimerInterval);
          gameTimerInterval = null;
          alert("TIME'S UP! The game has ended.");
        }
      }
    }, 1000);
  } else {
    // Freeplay - show elapsed time
    isGameTimed = false;
    gameStartTime = Date.now();
    updateElapsedTimeDisplay();
    gameTimerInterval = setInterval(() => {
      updateElapsedTimeDisplay();
    }, 1000);
  }
}

function updateGameTimerDisplay() {
  const timerDisplay = document.getElementById("game-timer");
  if (timerDisplay && isGameTimed) {
    const minutes = Math.floor(gameTimeRemaining / 60);
    const seconds = gameTimeRemaining % 60;
    timerDisplay.textContent = `Time Remaining: ${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
}

function updateElapsedTimeDisplay() {
  const timerDisplay = document.getElementById("game-timer");
  if (timerDisplay && !isGameTimed && gameStartTime) {
    const elapsed = Math.floor((Date.now() - gameStartTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    timerDisplay.textContent = `Elapsed Time: ${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
}

function stopGameTimer() {
  if (gameTimerInterval) {
    clearInterval(gameTimerInterval);
    gameTimerInterval = null;
  }
  const timerDisplay = document.getElementById("game-timer");
  if (timerDisplay) timerDisplay.remove();
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
