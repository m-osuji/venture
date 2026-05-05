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
function startGameHandler() {
  const teamCount = parseInt(document.getElementById("teamCountSelect").value);
  const teamNames = [];
  
  // Collect all team names
  for (let i = 0; i < teamCount; i++) {
    const teamInput = document.getElementById(`teamName${i}`);
    const teamName = teamInput ? teamInput.value.trim() : `Team ${String.fromCharCode(65 + i)}`;
    teamNames.push(teamName || `Team ${String.fromCharCode(65 + i)}`);
  }

  const aiYesRadio = document.getElementById("AI-player-yes");
  const includeAI = aiYesRadio ? aiYesRadio.checked : false;

  // Get difficulty (only if AI is included)
  let difficulty = null;
  
  if (includeAI) {
    // Get the selected difficulty from the DOM instead of using a closure
    const selectedBtn = document.querySelector('.difficulty-btn.selected');
    if (selectedBtn) {
      difficulty = selectedBtn.getAttribute('data-difficulty');
    } else {
      difficulty = "medium"; // default
    }
  }
  
  // Store game configuration
  const gameConfig = {
    teamCount: teamCount,
    teamNames: teamNames,
    includeAI: includeAI,
    aiDifficulty: difficulty,
    timestamp: new Date().toISOString()
  };
  
  // Close the overlay
  const setupOverlay = document.getElementById("game-setup-overlay");
  if (setupOverlay) {
    setupOverlay.style.display = "none";
  }
  
  // Convert object to JSON string and save to browser's localStorage
  localStorage.setItem("ventureGameConfig", JSON.stringify(gameConfig));
  
  // You can add more game initialization logic here
  console.log("Game configuration:", gameConfig);

  // Explanation of initial quiz
  initQuizSetup()
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
  aiText.innerHTML = "Take quiz to decide game order";

  // Make sure text and button are visible
  aiText.style.display = "block";
  aiButton.style.display = "block";
  aiText.classList.remove("fade-out");
  aiButton.classList.remove("fade-out");

  // Remove existing event listeners and add new one for quiz
  const newButton = aiButton.cloneNode(true);
  aiButton.parentNode.replaceChild(newButton, aiButton);
  
  newButton.addEventListener("click", () => {
    startTeamQuiz();
  });
}

// Tournament system with round robin between all teams
function startTeamQuiz() {
  const savedConfig = localStorage.getItem("ventureGameConfig");
  if (!savedConfig) {
    console.error("No game configuration found");
    return;
  }
  
  const gameConfig = JSON.parse(savedConfig);
  const teamNames = gameConfig.teamNames;
  const includeAI = gameConfig.includeAI;

  if (teamNames.length < 2) {
    alert("Tournament requires at least 2 teams. Please restart game setup.");
    return;
  }

  // Generate all possible matchups (round robin)
  const matchups = [];
  for (let i = 0; i < teamNames.length; i++) {
    for (let j = i + 1; j < teamNames.length; j++) {
      matchups.push({
        team1: teamNames[i],
        team2: teamNames[j],
        team1Score: 0,
        team2Score: 0,
        completed: false,
        results: []
      });
    }
  }

  let currentMatchupIndex = 0;
  let currentQuestionIndex = 0;
  let teamScores = {};
  let tournamentResults = [];
  
  // Initialize team scores
  teamNames.forEach(team => {
    teamScores[team] = 0;
  });

  // Quiz questions with correct answers
  const questions = [
    {
      text: "What does SWOT analysis stand for?",
      options: {
        a: "Strengths, Weaknesses, Opportunities, Threats",
        b: "Strategy, Workforce, Operations, Technology",
        c: "Sales, Wealth, Organization, Trade",
        d: "Strengths, Weaknesses, Objectives, Targets"
      },
      correct: "a"
    },
    {
      text: "What is the primary goal of market segmentation?",
      options: {
        a: "To target all customers equally",
        b: "To divide a market into distinct groups with similar needs",
        c: "To eliminate competition",
        d: "To reduce product quality"
      },
      correct: "b"
    },
    {
      text: "Which of the following is a fixed cost for a business?",
      options: {
        a: "Raw materials",
        b: "Rent",
        c: "Shipping costs",
        d: "Sales commissions"
      },
      correct: "b"
    },
    {
      text: "What is the break-even point?",
      options: {
        a: "When total revenue equals total costs",
        b: "When a business makes maximum profit",
        c: "When a business closes operations",
        d: "When demand exceeds supply"
      },
      correct: "a"
    },
    {
      text: "What is the purpose of a mission statement?",
      options: {
        a: "To calculate financial projections",
        b: "To define a company's purpose and goals",
        c: "To list employee benefits",
        d: "To advertise products"
      },
      correct: "b"
    },
    {
      text: "Which of these is a variable cost?",
      options: {
        a: "Rent",
        b: "Salaries",
        c: "Raw materials",
        d: "Insurance"
      },
      correct: "c"
    },
    {
      text: "What does ROI stand for?",
      options: {
        a: "Return on Investment",
        b: "Rate of Interest",
        c: "Risk of Inflation",
        d: "Revenue on Income"
      },
      correct: "a"
    }
  ];

  // Create tournament overlay
  const tournamentOverlay = document.createElement("div");
  tournamentOverlay.id = "tournament-overlay";
  tournamentOverlay.className = "game-setup-overlay";
  tournamentOverlay.innerHTML = `
    <div class="setup-card quiz-card" style="max-width: 900px;">
      <h2>TOURNAMENT CHALLENGE</h2>
      <div id="tournament-progress" style="margin-bottom: 15px; padding: 10px; background: #2c3e50; color: white; border-radius: 8px; text-align: center;">
        Matchup X of Y
      </div>
      <div style="display: flex; justify-content: space-between; gap: 20px; margin-bottom: 20px;">
        <div id="team1-panel" style="flex: 1; text-align: center; padding: 20px; background: #e8f4f8; border-radius: 10px;">
          <h3>TEAM 1</h3>
          <div style="font-size: 32px; font-weight: bold; margin: 10px 0;">Score: <span id="team1-score">0</span></div>
          <div style="font-size: 14px; background: #2c3e50; color: white; padding: 10px; border-radius: 8px;">
            Use keys: 1 2 3 4
          </div>
        </div>
        <div id="team2-panel" style="flex: 1; text-align: center; padding: 20px; background: #f8e8e8; border-radius: 10px;">
          <h3>TEAM 2</h3>
          <div style="font-size: 32px; font-weight: bold; margin: 10px 0;">Score: <span id="team2-score">0</span></div>
          <div style="font-size: 14px; background: #2c3e50; color: white; padding: 10px; border-radius: 8px;">
            Use keys: 6 7 8 9
          </div>
        </div>
      </div>
      <div id="question-area" style="background: #f9f9f9; border-radius: 10px; padding: 20px; margin-bottom: 20px;">
        <div id="question-text" style="font-size: 20px; font-weight: bold; margin-bottom: 20px;">Loading question...</div>
        <div id="options-area" style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
          <div id="option-a" class="competition-option" data-option="a">A. </div>
          <div id="option-b" class="competition-option" data-option="b">B. </div>
          <div id="option-c" class="competition-option" data-option="c">C. </div>
          <div id="option-d" class="competition-option" data-option="d">D. </div>
        </div>
      </div>
      <div id="round-result" style="text-align: center; padding: 15px; margin-bottom: 20px; border-radius: 8px; display: none;"></div>
      <div class="setup-actions">
        <button id="next-question-btn" class="setup-btn-primary" style="display: none;">Next Question</button>
        <button id="next-matchup-btn" class="setup-btn-primary" style="display: none;">Next Matchup</button>
      </div>
    </div>
  `;

  document.body.appendChild(tournamentOverlay);
  tournamentOverlay.style.display = "flex";

  let currentMatchup = null;
  let matchupQuestionsRemaining = 3; // Each matchup has 3 questions
  let matchupTeam1Score = 0;
  let matchupTeam2Score = 0;
  let questionActive = true;
  let currentQuestions = [];
  let currentMatchupResults = [];

  // Key mappings
  const keyToOption = {
    '1': { team: 1, option: 'a' },
    '2': { team: 1, option: 'b' },
    '3': { team: 1, option: 'c' },
    '4': { team: 1, option: 'd' },
    '6': { team: 2, option: 'a' },
    '7': { team: 2, option: 'b' },
    '8': { team: 2, option: 'c' },
    '9': { team: 2, option: 'd' }
  };

  function updateTournamentProgress() {
    const progressDiv = document.getElementById("tournament-progress");
    if (progressDiv) {
      progressDiv.innerHTML = `Matchup ${currentMatchupIndex + 1} of ${matchups.length} | Best of 3 Questions`;
    }
  }

  function selectRandomQuestions() {
    // Select 3 random questions for this matchup
    const shuffled = [...questions];
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }
    return shuffled.slice(0, 3);
  }

  function startMatchup() {
    currentMatchup = matchups[currentMatchupIndex];
    currentQuestionIndex = 0;
    matchupTeam1Score = 0;
    matchupTeam2Score = 0;
    questionActive = true;
    currentQuestions = selectRandomQuestions();
    currentMatchupResults = [];
    
    // Update display names
    const team1Panel = document.getElementById("team1-panel");
    const team2Panel = document.getElementById("team2-panel");
    if (team1Panel) team1Panel.querySelector("h3").innerHTML = `TEAM 1: ${currentMatchup.team1}`;
    if (team2Panel) team2Panel.querySelector("h3").innerHTML = `TEAM 2: ${currentMatchup.team2}`;
    
    updateScores();
    updateTournamentProgress();
    displayQuestion();
    
    document.getElementById("next-matchup-btn").style.display = "none";
  }

  function updateScores() {
    document.getElementById("team1-score").textContent = matchupTeam1Score;
    document.getElementById("team2-score").textContent = matchupTeam2Score;
  }

  function displayQuestion() {
    if (currentQuestionIndex >= currentQuestions.length) {
      endMatchup();
      return;
    }

    questionActive = true;
    // Reset team lock flags for new question
    window.team1Locked = false;
    window.team2Locked = false;
    
    const question = currentQuestions[currentQuestionIndex];
    
    document.getElementById("question-text").innerHTML = `Question ${currentQuestionIndex + 1} of ${currentQuestions.length}: ${question.text}`;
    document.getElementById("option-a").innerHTML = `A. ${question.options.a}`;
    document.getElementById("option-b").innerHTML = `B. ${question.options.b}`;
    document.getElementById("option-c").innerHTML = `C. ${question.options.c}`;
    document.getElementById("option-d").innerHTML = `D. ${question.options.d}`;
    
    document.getElementById("round-result").style.display = "none";
    document.getElementById("next-question-btn").style.display = "none";
    document.getElementById("buzzer-status").innerHTML = "First to answer correctly wins the point!";
    document.getElementById("buzzer-status").style.background = "#2c3e50";
    
    // Reset option styles
    const options = document.querySelectorAll(".competition-option");
    options.forEach(opt => {
      opt.style.background = "#f0f0f0";
      opt.style.border = "2px solid #ddd";
      opt.style.cursor = "pointer";
      opt.style.opacity = "1";
    });
  }

  function handleAnswer(team, selectedOption) {
    if (!questionActive) return false;
    
    const question = currentQuestions[currentQuestionIndex];
    const isCorrect = (selectedOption === question.correct);
    
    if (isCorrect) {
      questionActive = false;
      
      if (team === 1) {
        matchupTeam1Score++;
        document.getElementById("buzzer-status").innerHTML = `${currentMatchup.team1} answered correctly! +1 point`;
        document.getElementById("buzzer-status").style.background = "#27ae60";
        document.getElementById("round-result").innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${currentMatchup.team1} earns the point!</span>`;
      } else {
        matchupTeam2Score++;
        document.getElementById("buzzer-status").innerHTML = `${currentMatchup.team2} answered correctly! +1 point`;
        document.getElementById("buzzer-status").style.background = "#27ae60";
        document.getElementById("round-result").innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${currentMatchup.team2} earns the point!</span>`;
      }
      
      updateScores();
      
      currentMatchupResults.push({
        questionNumber: currentQuestionIndex + 1,
        question: question.text,
        correctAnswer: question.correct,
        correctAnswerText: question.options[question.correct],
        winningTeam: team === 1 ? currentMatchup.team1 : currentMatchup.team2,
        winningTeamId: team
      });
      
      document.getElementById("round-result").style.display = "block";
      document.getElementById("next-question-btn").style.display = "block";
      
      // Highlight correct answer
      const correctOptionId = `option-${question.correct}`;
      const correctElement = document.getElementById(correctOptionId);
      if (correctElement) {
        correctElement.style.background = "#27ae60";
        correctElement.style.border = "2px solid #1e7e34";
        correctElement.style.color = "white";
      }
      
      // Disable all options
      const options = document.querySelectorAll(".competition-option");
      options.forEach(opt => {
        opt.style.cursor = "not-allowed";
        opt.style.opacity = "0.5";
      });
      
      return true;
    } else {
      // Wrong answer - team is locked out for this question only
      
      if (team === 1) {
        document.getElementById("buzzer-status").innerHTML = `${currentMatchup.team1} answered WRONG! ${currentMatchup.team2} can still answer.`;
        document.getElementById("buzzer-status").style.background = "#e74c3c";
        document.getElementById("round-result").innerHTML = `<span style="color: red;">WRONG! ${currentMatchup.team1} loses this turn. ${currentMatchup.team2} can still answer.</span>`;
        
        // Disable Team 1's options by removing their event listener functionality
        // Instead of disabling all options, we track that team1 has answered wrong
        // Store that team1 is locked for this question
        if (!window.team1Locked) window.team1Locked = false;
        window.team1Locked = true;
        
        // Re-enable options for team 2 only
        const options = document.querySelectorAll(".competition-option");
        options.forEach(opt => {
          opt.style.cursor = "pointer";
          opt.style.opacity = "1";
        });
        
      } else if (team === 2) {
        document.getElementById("buzzer-status").innerHTML = `${currentMatchup.team2} answered WRONG! ${currentMatchup.team1} can still answer.`;
        document.getElementById("buzzer-status").style.background = "#e74c3c";
        document.getElementById("round-result").innerHTML = `<span style="color: red;">WRONG! ${currentMatchup.team2} loses this turn. ${currentMatchup.team1} can still answer.</span>`;
        
        // Store that team2 is locked for this question
        if (!window.team2Locked) window.team2Locked = false;
        window.team2Locked = true;
        
        // Re-enable options for team 1 only
        const options = document.querySelectorAll(".competition-option");
        options.forEach(opt => {
          opt.style.cursor = "pointer";
          opt.style.opacity = "1";
        });
      }
      
      document.getElementById("round-result").style.display = "block";
      // DO NOT hide next question button - keep it hidden until someone answers correctly
      // The question remains active for the other team
      
      return false;
    }
  }

  function nextQuestion() {
    currentQuestionIndex++;
    if (currentQuestionIndex < currentQuestions.length) {
      displayQuestion();
    } else {
      endMatchup();
    }
  }

  function endMatchup() {
    const winner = matchupTeam1Score > matchupTeam2Score ? currentMatchup.team1 : 
                   matchupTeam2Score > matchupTeam1Score ? currentMatchup.team2 : "Tie";
    
    // Update overall tournament scores
    if (winner !== "Tie") {
      teamScores[winner] += 1;
    }
    
    // Store matchup result
    matchups[currentMatchupIndex].team1Score = matchupTeam1Score;
    matchups[currentMatchupIndex].team2Score = matchupTeam2Score;
    matchups[currentMatchupIndex].completed = true;
    matchups[currentMatchupIndex].winner = winner;
    matchups[currentMatchupIndex].results = currentMatchupResults;
    
    tournamentResults.push({
      matchup: `${currentMatchup.team1} vs ${currentMatchup.team2}`,
      winner: winner,
      score: `${matchupTeam1Score} - ${matchupTeam2Score}`,
      details: currentMatchupResults
    });
    
    document.getElementById("question-area").style.display = "none";
    document.getElementById("next-question-btn").style.display = "none";
    
    let resultHtml = `
      <div style="text-align: center;">
        <h3>MATCHUP COMPLETE</h3>
        <div style="font-size: 20px; margin: 15px 0;">
          ${currentMatchup.team1}: ${matchupTeam1Score}<br>
          ${currentMatchup.team2}: ${matchupTeam2Score}
        </div>
        <div style="font-size: 24px; font-weight: bold; color: ${winner !== "Tie" ? "#27ae60" : "#f39c12"};">
          ${winner !== "Tie" ? `WINNER: ${winner}` : "IT'S A TIE!"}
        </div>
      </div>
    `;
    
    document.getElementById("round-result").innerHTML = resultHtml;
    document.getElementById("round-result").style.display = "block";
    
    if (currentMatchupIndex + 1 < matchups.length) {
      document.getElementById("next-matchup-btn").style.display = "block";
      document.getElementById("next-matchup-btn").textContent = "Next Matchup";
    } else {
      document.getElementById("next-matchup-btn").style.display = "block";
      document.getElementById("next-matchup-btn").textContent = "View Tournament Results";
    }
  }

  function nextMatchup() {
    currentMatchupIndex++;
    
    if (currentMatchupIndex < matchups.length) {
      // Reset UI for next matchup
      document.getElementById("question-area").style.display = "block";
      document.getElementById("round-result").style.display = "none";
      document.getElementById("next-matchup-btn").style.display = "none";
      startMatchup();
    } else {
      // Tournament complete - go to market selection
      endTournament();
    }
  }

  function endTournament() {
    // Rank teams by tournament score
    const rankedTeams = Object.entries(teamScores)
      .map(([team, score]) => ({ team, score }))
      .sort((a, b) => b.score - a.score);
    
    tournamentOverlay.remove();
    
    // Start market selection in order of ranking
    startMarketSelection(rankedTeams);
  }

  // Market selection after tournament
  function startMarketSelection(rankedTeams) {
    const markets = [
      { id: "tech", name: "Technology Market", bonus: "Innovation boost - +2 research points per round" },
      { id: "finance", name: "Finance Market", bonus: "Capital advantage - Start with 50% more currency" },
      { id: "retail", name: "Retail Market", bonus: "Customer loyalty - 20% discount on all purchases" },
      { id: "energy", name: "Energy Market", bonus: "Resource efficiency - 30% reduced operating costs" },
      { id: "healthcare", name: "Healthcare Market", bonus: "Stability bonus - Immunity to market crashes" }
    ];
    
    let currentTeamIndex = 0;
    const selectedMarkets = {};
    const availableMarkets = [...markets];
    
    const marketOverlay = document.createElement("div");
    marketOverlay.id = "market-overlay";
    marketOverlay.className = "game-setup-overlay";
    marketOverlay.innerHTML = `
      <div class="setup-card" style="max-width: 600px;">
        <h2>Market Selection Draft</h2>
        <div id="draft-progress" style="margin-bottom: 20px; padding: 10px; background: #2c3e50; color: white; border-radius: 8px;">
          Team 1 of X
        </div>
        <div id="current-team" style="text-align: center; margin-bottom: 20px;">
          <h3 id="current-team-name">Team Name</h3>
          <p>Select your starting market</p>
        </div>
        <div id="markets-list" style="margin-bottom: 20px;">
          <!-- Markets will be listed here -->
        </div>
        <div id="selection-feedback" style="text-align: center; padding: 10px; margin-bottom: 10px; border-radius: 8px; display: none;"></div>
        <div class="setup-actions">
          <button id="confirm-market-btn" class="setup-btn-primary" style="display: none;">Confirm Selection</button>
        </div>
      </div>
    `;
    
    document.body.appendChild(marketOverlay);
    marketOverlay.style.display = "flex";
    
    function updateDraftProgress() {
      const progressDiv = document.getElementById("draft-progress");
      if (progressDiv) {
        progressDiv.innerHTML = `Draft Pick ${currentTeamIndex + 1} of ${rankedTeams.length} | ${rankedTeams[currentTeamIndex].team}'s turn`;
      }
      document.getElementById("current-team-name").innerHTML = `${rankedTeams[currentTeamIndex].team}<br><span style="font-size: 14px; color: #666;">Tournament Score: ${rankedTeams[currentTeamIndex].score} wins</span>`;
    }
    
    function displayMarkets() {
      const marketsList = document.getElementById("markets-list");
      if (!marketsList) return;
      
      marketsList.innerHTML = "";
      availableMarkets.forEach((market, index) => {
        const marketDiv = document.createElement("div");
        marketDiv.className = "market-option";
        marketDiv.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 15px; margin: 10px 0; background: #f9f9f9; border: 2px solid #ddd; border-radius: 10px; cursor: pointer;">
            <div>
              <strong style="font-size: 18px;">${market.name}</strong><br>
              <span style="font-size: 14px; color: #666;">${market.bonus}</span>
            </div>
            <button class="select-market-btn" data-market-id="${market.id}" data-market-name="${market.name}" style="background: ${currentTeamIndex === 0 ? '#EE672B' : '#467096'}; color: white; border: none; padding: 8px 20px; border-radius: 5px; cursor: pointer;">Select</button>
          </div>
        `;
        marketsList.appendChild(marketDiv);
      });
      
      // Add event listeners to select buttons
      document.querySelectorAll(".select-market-btn").forEach(btn => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          const marketId = btn.getAttribute("data-market-id");
          const marketName = btn.getAttribute("data-market-name");
          selectMarket(marketId, marketName);
        });
      });
    }
    
    function selectMarket(marketId, marketName) {
      const currentTeam = rankedTeams[currentTeamIndex].team;
      selectedMarkets[currentTeam] = { id: marketId, name: marketName };
      
      // Remove selected market from available list
      const marketIndex = availableMarkets.findIndex(m => m.id === marketId);
      if (marketIndex !== -1) availableMarkets.splice(marketIndex, 1);
      
      const feedback = document.getElementById("selection-feedback");
      if (feedback) {
        feedback.style.display = "block";
        feedback.style.background = "#d4edda";
        feedback.style.color = "#155724";
        feedback.innerHTML = `${currentTeam} selected ${marketName}!`;
        setTimeout(() => {
          feedback.style.display = "none";
        }, 1500);
      }
      
      currentTeamIndex++;
      
      if (currentTeamIndex < rankedTeams.length) {
        updateDraftProgress();
        displayMarkets();
      } else {
        // All teams have selected markets
        finishMarketSelection();
      }
    }
    
    function finishMarketSelection() {
      const finalResults = {
        tournamentRankings: rankedTeams,
        marketSelections: selectedMarkets,
        allMatchups: tournamentResults,
        timestamp: new Date().toISOString()
      };
      
      localStorage.setItem("tournamentResults", JSON.stringify(finalResults));
      localStorage.setItem("marketSelections", JSON.stringify(selectedMarkets));
      
      marketOverlay.remove();
      
      // Update AI text
      const aiText = document.getElementById("AI-text");
      if (aiText) {
        let rankingText = rankedTeams.map((t, i) => `${i+1}. ${t.team} (${t.score} wins)`).join("\n");
        aiText.innerHTML = `Tournament complete! Final rankings:\n${rankingText}\n\nMarkets have been selected. Click the button below to begin the game!`;
      }
      
      // Show final results
      alert(`Tournament Complete!\n\nFinal Rankings:\n${rankedTeams.map((t, i) => `${i+1}. ${t.team} (${t.score} wins)`).join("\n")}\n\nMarkets have been assigned based on draft order.\n\nThe game will now begin!`);
      
      // Re-enable the AI confirm button for game start
      const aiButton = document.getElementById("AI-confirm");
      if (aiButton) {
        const newButton = aiButton.cloneNode(true);
        aiButton.parentNode.replaceChild(newButton, aiButton);
        newButton.textContent = "Start Game";
        newButton.addEventListener("click", () => {
          alert("Game is starting with your tournament rankings and market selections!");
        });
      }
    }
    
    updateDraftProgress();
    displayMarkets();
  }

  // Keyboard event listener
  function onKeyDown(event) {
    const key = event.key;
    if (keyToOption[key] && questionActive) {
      const { team, option } = keyToOption[key];
      
      // Check if this team is locked from answering
      if ((team === 1 && window.team1Locked) || (team === 2 && window.team2Locked)) {
        // Team already answered wrong this question
        return;
      }
      
      event.preventDefault();
      handleAnswer(team, option);
    }
  }

  // Setup event listeners
  document.addEventListener("keydown", onKeyDown);
  
  const nextQuestionBtn = document.getElementById("next-question-btn");
  if (nextQuestionBtn) {
    nextQuestionBtn.onclick = () => nextQuestion();
  }
  
  const nextMatchupBtn = document.getElementById("next-matchup-btn");
  if (nextMatchupBtn) {
    nextMatchupBtn.onclick = () => nextMatchup();
  }

  // Add buzzer status element if not present
  const buzzerStatus = document.createElement("div");
  buzzerStatus.id = "buzzer-status";
  buzzerStatus.style.marginBottom = "20px";
  buzzerStatus.style.padding = "15px";
  buzzerStatus.style.background = "#2c3e50";
  buzzerStatus.style.color = "white";
  buzzerStatus.style.borderRadius = "10px";
  buzzerStatus.style.fontWeight = "bold";
  buzzerStatus.style.textAlign = "center";
  
  const questionArea = document.getElementById("question-area");
  if (questionArea) {
    questionArea.parentNode.insertBefore(buzzerStatus, questionArea);
  }

  // Start the first matchup
  startMatchup();
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