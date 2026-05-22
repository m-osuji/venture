// Reusable Tournament Module
export class TournamentQuiz {
    constructor(teamNames, questionBank, getCorrectLetter, getRandomQuestions, options = {}) {
        this.teamNames = teamNames;
        this.questionBank = questionBank;
        this.getCorrectLetter = getCorrectLetter;
        this.getRandomQuestions = getRandomQuestions;
        this.aiTeams = new Set(options.aiTeams || []);
        this.aiDifficulty = String(options.aiDifficulty || "medium").toLowerCase();
        this.matchups = [];
        this.currentMatchupIndex = 0;
        this.currentQuestionIndex = 0;
        this.teamScores = {}; // Track wins (matchup wins)
        this.teamCorrectAnswers = {}; // Track total correct answers
        this.teamTotalTime = {}; // Track total response time in milliseconds
        this.teamResponseCount = {}; // Track number of responses for averaging
        this.tournamentResults = [];
        this.countdownInterval = null;
        this.currentTimeRemaining = 30;
        this.questionActive = true;
        this.currentQuestions = [];
        this.currentMatchup = null;
        this.matchupTeam1Score = 0;
        this.matchupTeam2Score = 0;
        this.currentMatchupResults = [];
        this.onComplete = null;
        this.tieBreakerNeeded = false;
        this.teamsInTie = [];
        
        // Track per-question answer times for each team
        this.questionTeamAnswers = new Map(); // teamName -> { answeredAt: timestamp, isCorrect: bool }
        this.currentQuestionStartTime = null;
        this.aiAnswerTimeouts = [];
        
        // Key mappings
        this.keyToOption = {
            '1': { team: 1, option: 'a' },
            '2': { team: 1, option: 'b' },
            '3': { team: 1, option: 'c' },
            '4': { team: 1, option: 'd' },
            '6': { team: 2, option: 'a' },
            '7': { team: 2, option: 'b' },
            '8': { team: 2, option: 'c' },
            '9': { team: 2, option: 'd' }
        };
        
        // Initialize
        this.init();
    }
    
    init() {
        // Initialize team stats
        this.teamNames.forEach(team => {
            this.teamScores[team] = 0; // Matchup wins
            this.teamCorrectAnswers[team] = 0; // Total correct answers
            this.teamTotalTime[team] = 0; // Total response time (ms)
            this.teamResponseCount[team] = 0; // Number of responses
        });
        
        // Generate matchups
        for (let i = 0; i < this.teamNames.length; i++) {
            for (let j = i + 1; j < this.teamNames.length; j++) {
                this.matchups.push({
                    team1: this.teamNames[i],
                    team2: this.teamNames[j],
                    team1Score: 0,
                    team2Score: 0,
                    completed: false,
                    results: []
                });
            }
        }
    }
    
    selectRandomQuestions() {
        return this.getRandomQuestions(3, 'all');
    }
    
    start(onComplete) {
        this.onComplete = onComplete;
        this.createOverlay();
        this.startMatchup();
        this.setupEventListeners();
    }
    
    createOverlay() {
        this.overlay = document.getElementById('tournament-overlay');
        if (!this.overlay) {
            this.overlay = document.createElement('div');
            this.overlay.id = 'tournament-overlay';
            this.overlay.className = 'game-setup-overlay';
            this.overlay.innerHTML = document.getElementById('tournament-template')?.innerHTML || this.getDefaultTemplate();
            document.body.appendChild(this.overlay);
        }
        this.overlay.style.display = "flex";
    }
    
    getDefaultTemplate() {
        return `
            <div class="tournament-layout">
                <!-- Left Panel - Team 1 -->
                <div id="team1-panel" class="tournament-team-panel team1-panel">
                    <h3>TEAM 1</h3>
                    <div class="team-score">Score: <span id="team1-score">0</span></div>
                    <div class="team-total-time">Total Time: <span id="team1-time">0.0</span>s</div>
                    <div class="team-keys">Use keys: 1 2 3 4</div>
                </div>
                
                <!-- Center - Quiz Content -->
                <div class="setup-card quiz-card">
                    <div class="quiz-header">
                        <h2>TOURNAMENT CHALLENGE</h2>
                        <div id="question-timer" class="question-timer">Time: 30s</div>
                    </div>
                    <div id="tournament-progress" class="tournament-progress">Matchup X of Y</div>
                    <div id="question-area" class="question-area">
                        <div id="question-text" class="question-text">Loading question...</div>
                        <div id="options-area" class="options-area">
                            <div id="option-a" class="competition-option" data-option="a">A. </div>
                            <div id="option-b" class="competition-option" data-option="b">B. </div>
                            <div id="option-c" class="competition-option" data-option="c">C. </div>
                            <div id="option-d" class="competition-option" data-option="d">D. </div>
                        </div>
                    </div>
                    <div id="round-result" class="round-result" style="display: none;"></div>
                    <div class="setup-actions">
                        <button id="next-question-btn" class="setup-btn-primary" style="display: none;">Next Question</button>
                        <button id="next-matchup-btn" class="setup-btn-primary" style="display: none;">Next Matchup</button>
                    </div>
                </div>
                
                <!-- Right Panel - Team 2 -->
                <div id="team2-panel" class="tournament-team-panel team2-panel">
                    <h3>TEAM 2</h3>
                    <div class="team-score">Score: <span id="team2-score">0</span></div>
                    <div class="team-total-time">Total Time: <span id="team2-time">0.0</span>s</div>
                    <div class="team-keys">Use keys: 6 7 8 9</div>
                </div>
            </div>
        `;
    }
    
    startMatchup() {
        this.currentMatchup = this.matchups[this.currentMatchupIndex];
        this.currentQuestionIndex = 0;
        this.matchupTeam1Score = 0;
        this.matchupTeam2Score = 0;
        this.questionActive = true;
        this.currentQuestions = this.selectRandomQuestions();
        this.currentMatchupResults = [];
        
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
        this.currentTimeRemaining = 30;
        
        const timerElement = document.getElementById("question-timer");
        if (timerElement) {
            timerElement.style.display = "block";
            timerElement.textContent = "Time: 30s";
            timerElement.style.background = "var(--main-orange)";
            timerElement.style.animation = "none";
        }
        
        const team1Panel = document.getElementById("team1-panel");
        const team2Panel = document.getElementById("team2-panel");
        if (team1Panel) team1Panel.querySelector("h3").innerHTML = `TEAM 1: ${this.currentMatchup.team1}`;
        if (team2Panel) team2Panel.querySelector("h3").innerHTML = `TEAM 2: ${this.currentMatchup.team2}`;
        if (team1Panel) {
            const keys = team1Panel.querySelector(".team-keys");
            if (keys) {
                keys.textContent = this.isAiTeam(this.currentMatchup.team1)
                    ? "IBM Granite AI is answering automatically"
                    : "Use keys: 1 2 3 4";
            }
        }
        if (team2Panel) {
            const keys = team2Panel.querySelector(".team-keys");
            if (keys) {
                keys.textContent = this.isAiTeam(this.currentMatchup.team2)
                    ? "IBM Granite AI is answering automatically"
                    : "Use keys: 6 7 8 9";
            }
        }
        
        this.updateScores();
        this.updateTotalTimeDisplay();
        this.updateTournamentProgress();
        this.displayQuestion();
        
        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) nextMatchupBtn.style.display = "none";
    }
    
    updateScores() {
        document.getElementById("team1-score").textContent = this.matchupTeam1Score;
        document.getElementById("team2-score").textContent = this.matchupTeam2Score;
    }
    
    updateTotalTimeDisplay() {
        const team1TimeSec = (this.teamTotalTime[this.currentMatchup?.team1] || 0) / 1000;
        const team2TimeSec = (this.teamTotalTime[this.currentMatchup?.team2] || 0) / 1000;
        const team1TimeEl = document.getElementById("team1-time");
        const team2TimeEl = document.getElementById("team2-time");
        if (team1TimeEl) team1TimeEl.textContent = team1TimeSec.toFixed(1);
        if (team2TimeEl) team2TimeEl.textContent = team2TimeSec.toFixed(1);
    }
    
    updateTournamentProgress() {
        const progressDiv = document.getElementById("tournament-progress");
        if (progressDiv) {
            progressDiv.innerHTML = `Matchup ${this.currentMatchupIndex + 1} of ${this.matchups.length} | Best of 3 Questions`;
        }
    }
    
    recordAnswerTime(teamName, isCorrect) {
        // This method is now handled in handleAnswer for more precise timing
        // Keeping for compatibility but logic moved
    }

    isAiTeam(teamName) {
        return this.aiTeams.has(teamName);
    }

    clearAiAnswerTimeouts() {
        this.aiAnswerTimeouts.forEach((timeoutId) => clearTimeout(timeoutId));
        this.aiAnswerTimeouts = [];
    }

    getAiAccuracyChance(question) {
        const questionDifficulty = String(question?.difficulty || "medium").toLowerCase();
        const baseByDifficulty = {
            easy: 0.58,
            medium: 0.74,
            hard: 0.88
        };
        const questionModifier = {
            easy: 0.16,
            medium: 0.0,
            hard: -0.12
        };
        const baseChance = baseByDifficulty[this.aiDifficulty] ?? 0.74;
        return Math.max(0.2, Math.min(0.97, baseChance + (questionModifier[questionDifficulty] ?? 0)));
    }

    randomWrongOption(correctOption) {
        const distractors = ["a", "b", "c", "d"].filter((option) => option !== correctOption);
        return distractors[Math.floor(Math.random() * distractors.length)] || "a";
    }

    getAiDelayMs() {
        if (this.aiDifficulty === "easy") {
            return 9000 + Math.floor(Math.random() * 9000);
        }
        if (this.aiDifficulty === "hard") {
            return 2500 + Math.floor(Math.random() * 4500);
        }
        return 5000 + Math.floor(Math.random() * 7000);
    }

    scheduleAiAnswers(question) {
        if (!this.currentMatchup) {
            return;
        }

        const correctOption = window.currentCorrectAnswer;
        [
            { teamNumber: 1, teamName: this.currentMatchup.team1 },
            { teamNumber: 2, teamName: this.currentMatchup.team2 }
        ].forEach(({ teamNumber, teamName }) => {
            if (!this.isAiTeam(teamName)) {
                return;
            }

            const timeoutId = setTimeout(() => {
                if (!this.questionActive) {
                    return;
                }
                const chosenOption = Math.random() <= this.getAiAccuracyChance(question)
                    ? correctOption
                    : this.randomWrongOption(correctOption);
                this.handleAnswer(teamNumber, chosenOption);
            }, this.getAiDelayMs());

            this.aiAnswerTimeouts.push(timeoutId);
        });
    }
    
    displayQuestion() {
        if (this.currentQuestionIndex >= this.currentQuestions.length) {
            this.endMatchup();
            return;
        }
        
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
        
        this.questionActive = true;
        window.team1Locked = false;
        window.team2Locked = false;
        
        // Reset per-question tracking
        this.questionTeamAnswers.clear();
        this.clearAiAnswerTimeouts();
        
        // Record the start time for this question
        this.currentQuestionStartTime = Date.now();
        
        const question = this.currentQuestions[this.currentQuestionIndex];
        const correctLetter = this.getCorrectLetter(question.correct);
        window.currentCorrectAnswer = correctLetter;
        
        // Debug logging
        console.log(`Question ${this.currentQuestionIndex + 1}: Correct answer is ${correctLetter} (${question.correct})`);
        
        document.getElementById("question-text").innerHTML = `Question ${this.currentQuestionIndex + 1} of ${this.currentQuestions.length}: ${question.content}`;
        document.getElementById("option-a").innerHTML = `A. ${question.options.a}`;
        document.getElementById("option-b").innerHTML = `B. ${question.options.b}`;
        document.getElementById("option-c").innerHTML = `C. ${question.options.c}`;
        document.getElementById("option-d").innerHTML = `D. ${question.options.d}`;
        
        document.getElementById("round-result").style.display = "none";
        document.getElementById("next-question-btn").style.display = "none";
        
        const buzzerStatus = document.getElementById("buzzer-status");
        if (buzzerStatus) {
            buzzerStatus.innerHTML = "Both teams answer - fastest correct answer wins!";
            buzzerStatus.style.background = "#2c3e50";
        }
        
        const options = document.querySelectorAll(".competition-option");
        options.forEach(opt => {
            opt.style.background = "#f0f0f0";
            opt.style.border = "2px solid #ddd";
            opt.style.cursor = "pointer";
            opt.style.opacity = "1";
        });
        
        const timerElement = document.getElementById("question-timer");
        if (timerElement) {
            timerElement.style.display = "block";
            timerElement.style.background = "var(--main-orange)";
            timerElement.style.animation = "none";
            timerElement.textContent = "Time: 30s";
        }
        
        this.startCountdown();
        this.scheduleAiAnswers(question);
    }
    
    startCountdown() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
        
        this.currentTimeRemaining = 30;
        
        const timerElement = document.getElementById("question-timer");
        if (timerElement) {
            timerElement.style.display = "block";
            timerElement.textContent = "Time: 30s";
            timerElement.style.background = "var(--main-orange)";
            timerElement.style.animation = "none";
        }
        
        this.countdownInterval = setInterval(() => {
            if (!this.questionActive) return;
            
            this.currentTimeRemaining--;
            
            const timerEl = document.getElementById("question-timer");
            if (timerEl) {
                timerEl.textContent = `Time: ${this.currentTimeRemaining}s`;
                
                if (this.currentTimeRemaining <= 10 && this.currentTimeRemaining > 0) {
                    timerEl.style.background = "#e74c3c";
                    timerEl.style.animation = "pulse 0.5s infinite";
                } else if (this.currentTimeRemaining <= 20 && this.currentTimeRemaining > 0) {
                    timerEl.style.background = "#f39c12";
                    timerEl.style.animation = "none";
                } else if (this.currentTimeRemaining > 0) {
                    timerEl.style.background = "var(--main-orange)";
                    timerEl.style.animation = "none";
                } else if (this.currentTimeRemaining === 0) {
                    timerEl.style.background = "#8b0000";
                    timerEl.style.animation = "none";
                }
            }
            
            if (this.currentTimeRemaining <= 0) {
                clearInterval(this.countdownInterval);
                this.countdownInterval = null;
                
                if (this.questionActive) {
                    const timerEl = document.getElementById("question-timer");
                    if (timerEl) timerEl.style.display = "none";
                    
                    this.questionActive = false;
                    
                    // Record times for any teams that didn't answer (they get full time)
                    const team1Name = this.currentMatchup.team1;
                    const team2Name = this.currentMatchup.team2;
                    
                    if (!window.team1Locked && this.currentQuestionStartTime) {
                        const timeSpent = 30000; // Full 30 seconds if no answer
                        this.teamTotalTime[team1Name] += timeSpent;
                        this.teamResponseCount[team1Name]++;
                        console.log(`${team1Name} did not answer, recorded ${timeSpent}ms`);
                    }
                    
                    if (!window.team2Locked && this.currentQuestionStartTime) {
                        const timeSpent = 30000; // Full 30 seconds if no answer
                        this.teamTotalTime[team2Name] += timeSpent;
                        this.teamResponseCount[team2Name]++;
                        console.log(`${team2Name} did not answer, recorded ${timeSpent}ms`);
                    }
                    
                    this.currentQuestionStartTime = null;
                    
                    const buzzerStatus = document.getElementById("buzzer-status");
                    if (buzzerStatus) {
                        buzzerStatus.innerHTML = "Time's up! Moving to next question.";
                        buzzerStatus.style.background = "#f39c12";
                    }
                    
                    const roundResult = document.getElementById("round-result");
                    if (roundResult) {
                        roundResult.innerHTML = `<span style="color: orange; font-weight: bold;">Time's up! No points awarded for this question.</span>`;
                        roundResult.style.display = "block";
                    }
                    
                    const nextBtn = document.getElementById("next-question-btn");
                    if (nextBtn) nextBtn.style.display = "block";
                    
                    if (this.currentQuestions[this.currentQuestionIndex]) {
                        this.currentMatchupResults.push({
                            questionNumber: this.currentQuestionIndex + 1,
                            question: this.currentQuestions[this.currentQuestionIndex].content,
                            correctAnswer: this.currentQuestions[this.currentQuestionIndex].correct,
                            correctAnswerText: this.currentQuestions[this.currentQuestionIndex].options[this.currentQuestions[this.currentQuestionIndex].correct],
                            winningTeam: "None",
                            winningTeamId: 0,
                            timeOut: true
                        });
                    }
                    
                    const options = document.querySelectorAll(".competition-option");
                    options.forEach(opt => {
                        opt.style.cursor = "not-allowed";
                        opt.style.opacity = "0.5";
                    });
                    
                    if (this.currentQuestions[this.currentQuestionIndex]) {
                        const question = this.currentQuestions[this.currentQuestionIndex];
                        const correctLetter = this.getCorrectLetter(question.correct);
                        const correctElement = document.getElementById(`option-${correctLetter}`);
                        if (correctElement) {
                            correctElement.style.background = "#27ae60";
                            correctElement.style.border = "2px solid #1e7e34";
                            correctElement.style.color = "white";
                        }
                    }
                    
                    this.updateTotalTimeDisplay();
                }
            }
        }, 1000);
    }
    
    handleAnswer(team, selectedOption) {
        if (!this.questionActive) return false;
        
        const question = this.currentQuestions[this.currentQuestionIndex];
        const isCorrect = (selectedOption === window.currentCorrectAnswer);
        const teamName = team === 1 ? this.currentMatchup.team1 : this.currentMatchup.team2;
        
        // Check if this team already answered this question
        if (this.questionTeamAnswers.has(teamName)) {
            console.log(`${teamName} already answered this question`);
            return false;
        }
        
        // Record the answer time for this team (individual timing)
        let timeSpent = 0;
        if (this.currentQuestionStartTime) {
            timeSpent = Date.now() - this.currentQuestionStartTime;
            this.teamTotalTime[teamName] += timeSpent;
            this.teamResponseCount[teamName]++;
            if (isCorrect) {
                this.teamCorrectAnswers[teamName]++;
            }
            this.questionTeamAnswers.set(teamName, { timeSpent, isCorrect });
            console.log(`${teamName} answered in ${timeSpent}ms, correct: ${isCorrect}`);
        }
        
        // Lock this team from answering again
        if (team === 1) window.team1Locked = true;
        if (team === 2) window.team2Locked = true;
        
        if (isCorrect) {
            // Correct answer - award point
            if (team === 1) {
                this.matchupTeam1Score++;
                const buzzerStatus = document.getElementById("buzzer-status");
                if (buzzerStatus) {
                    buzzerStatus.innerHTML = `${this.currentMatchup.team1} answered correctly! +1 point (${(timeSpent/1000).toFixed(1)}s)`;
                    buzzerStatus.style.background = "#27ae60";
                }
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${this.currentMatchup.team1} earns the point! (${(timeSpent/1000).toFixed(1)}s)</span>`;
                }
            } else {
                this.matchupTeam2Score++;
                const buzzerStatus = document.getElementById("buzzer-status");
                if (buzzerStatus) {
                    buzzerStatus.innerHTML = `${this.currentMatchup.team2} answered correctly! +1 point (${(timeSpent/1000).toFixed(1)}s)`;
                    buzzerStatus.style.background = "#27ae60";
                }
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${this.currentMatchup.team2} earns the point! (${(timeSpent/1000).toFixed(1)}s)</span>`;
                }
            }
            
            this.updateScores();
            this.updateTotalTimeDisplay();
            
            this.currentMatchupResults.push({
                questionNumber: this.currentQuestionIndex + 1,
                question: question.content,
                correctAnswer: question.correct,
                correctAnswerText: question.options[window.currentCorrectAnswer],
                winningTeam: team === 1 ? this.currentMatchup.team1 : this.currentMatchup.team2,
                winningTeamId: team,
                responseTimeMs: timeSpent
            });
            
            // End the question when someone answers correctly
            this.stopCountdown();
            this.questionActive = false;
            
            const roundResult = document.getElementById("round-result");
            if (roundResult) roundResult.style.display = "block";
            
            const nextBtn = document.getElementById("next-question-btn");
            if (nextBtn) nextBtn.style.display = "block";
            
            const correctLetter = window.currentCorrectAnswer;
            const correctElement = document.getElementById(`option-${correctLetter}`);
            if (correctElement) {
                correctElement.style.background = "#27ae60";
                correctElement.style.border = "2px solid #1e7e34";
                correctElement.style.color = "white";
            }
            
            const options = document.querySelectorAll(".competition-option");
            options.forEach(opt => {
                opt.style.cursor = "not-allowed";
                opt.style.opacity = "0.5";
            });
            
            return true;
        } else {
            // Wrong answer - show message but continue for other team
            if (team === 1) {
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: red;">WRONG! ${this.currentMatchup.team1} answered incorrectly (${(timeSpent/1000).toFixed(1)}s). ${this.currentMatchup.team2} can still answer.</span>`;
                    roundResult.style.display = "block";
                }
                if (window.team2Locked) {
                    // Both teams answered and both were wrong
                    this.handleDoubleWrong();
                }
            } else if (team === 2) {
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: red;">WRONG! ${this.currentMatchup.team2} answered incorrectly (${(timeSpent/1000).toFixed(1)}s). ${this.currentMatchup.team1} can still answer.</span>`;
                    roundResult.style.display = "block";
                }
                if (window.team1Locked) {
                    // Both teams answered and both were wrong
                    this.handleDoubleWrong();
                }
            }
            return false;
        }
    }
    
    handleDoubleWrong() {
        if (window.team1Locked && window.team2Locked && this.questionActive) {
            // Both teams answered and both were wrong
            // Their times have already been recorded
            
            this.stopCountdown();
            this.questionActive = false;
            
            const buzzerStatus = document.getElementById("buzzer-status");
            if (buzzerStatus) {
                buzzerStatus.innerHTML = "Both teams answered wrong! Moving to next question.";
                buzzerStatus.style.background = "#f39c12";
            }
            
            const roundResult = document.getElementById("round-result");
            if (roundResult) {
                roundResult.innerHTML = `<span style="color: orange; font-weight: bold;">Both teams were wrong! No points awarded for this question.</span>`;
                roundResult.style.display = "block";
            }
            
            const nextBtn = document.getElementById("next-question-btn");
            if (nextBtn) nextBtn.style.display = "block";
            
            this.currentMatchupResults.push({
                questionNumber: this.currentQuestionIndex + 1,
                question: this.currentQuestions[this.currentQuestionIndex].content,
                correctAnswer: this.currentQuestions[this.currentQuestionIndex].correct,
                correctAnswerText: this.currentQuestions[this.currentQuestionIndex].options[window.currentCorrectAnswer],
                winningTeam: "Neither",
                winningTeamId: 0
            });
            
            const options = document.querySelectorAll(".competition-option");
            options.forEach(opt => {
                opt.style.cursor = "not-allowed";
                opt.style.opacity = "0.5";
            });
            
            const question = this.currentQuestions[this.currentQuestionIndex];
            const correctLetter = this.getCorrectLetter(question.correct);
            const correctElement = document.getElementById(`option-${correctLetter}`);
            if (correctElement) {
                correctElement.style.background = "#27ae60";
                correctElement.style.border = "2px solid #1e7e34";
                correctElement.style.color = "white";
            }
            
            this.updateTotalTimeDisplay();
        }
    }
    
    stopCountdown() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
    }
    
    nextQuestion() {
        this.stopCountdown();
        this.clearAiAnswerTimeouts();
        this.currentQuestionIndex++;
        if (this.currentQuestionIndex < this.currentQuestions.length) {
            this.displayQuestion();
        } else {
            this.endMatchup();
        }
    }
    
    endMatchup() {
        const winner = this.matchupTeam1Score > this.matchupTeam2Score ? this.currentMatchup.team1 : 
                       this.matchupTeam2Score > this.matchupTeam1Score ? this.currentMatchup.team2 : "Tie";
        
        // Get total times for this matchup's teams
        const team1TotalTimeSec = (this.teamTotalTime[this.currentMatchup.team1] || 0) / 1000;
        const team2TotalTimeSec = (this.teamTotalTime[this.currentMatchup.team2] || 0) / 1000;
        
        if (winner !== "Tie") {
            this.teamScores[winner] += 1;
        }
        
        this.matchups[this.currentMatchupIndex].team1Score = this.matchupTeam1Score;
        this.matchups[this.currentMatchupIndex].team2Score = this.matchupTeam2Score;
        this.matchups[this.currentMatchupIndex].completed = true;
        this.matchups[this.currentMatchupIndex].winner = winner;
        this.matchups[this.currentMatchupIndex].results = this.currentMatchupResults;
        
        this.tournamentResults.push({
            matchup: `${this.currentMatchup.team1} vs ${this.currentMatchup.team2}`,
            winner: winner,
            score: `${this.matchupTeam1Score} - ${this.matchupTeam2Score}`,
            team1TotalTime: team1TotalTimeSec,
            team2TotalTime: team2TotalTimeSec,
            details: this.currentMatchupResults
        });
        
        document.getElementById("question-area").style.display = "none";
        document.getElementById("next-question-btn").style.display = "none";
        
        let resultHtml = `
            <div style="text-align: center;">
                <h3>MATCHUP COMPLETE</h3>
                <div style="font-size: 20px; margin: 15px 0;">
                    ${this.currentMatchup.team1}: ${this.matchupTeam1Score} correct (${team1TotalTimeSec.toFixed(1)}s total)<br>
                    ${this.currentMatchup.team2}: ${this.matchupTeam2Score} correct (${team2TotalTimeSec.toFixed(1)}s total)
                </div>
        `;
        
        if (winner !== "Tie") {
            resultHtml += `<div style="font-size: 24px; font-weight: bold; color: #27ae60;">WINNER: ${winner}</div>`;
        } else {
            // Tie - show time comparison
            if (team1TotalTimeSec < team2TotalTimeSec) {
                resultHtml += `<div style="font-size: 24px; font-weight: bold; color: #27ae60;">TIE BREAKER: ${this.currentMatchup.team1} wins on time! (${team1TotalTimeSec.toFixed(1)}s vs ${team2TotalTimeSec.toFixed(1)}s)</div>`;
            } else if (team2TotalTimeSec < team1TotalTimeSec) {
                resultHtml += `<div style="font-size: 24px; font-weight: bold; color: #27ae60;">TIE BREAKER: ${this.currentMatchup.team2} wins on time! (${team2TotalTimeSec.toFixed(1)}s vs ${team1TotalTimeSec.toFixed(1)}s)</div>`;
            } else {
                resultHtml += `<div style="font-size: 24px; font-weight: bold; color: #f39c12;">IT'S A COMPLETE TIE! (Same score and total time)</div>`;
            }
        }
        
        resultHtml += `</div>`;
        
        const roundResult = document.getElementById("round-result");
        if (roundResult) {
            roundResult.innerHTML = resultHtml;
            roundResult.style.display = "block";
        }
        
        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) {
            nextMatchupBtn.style.display = "block";
            nextMatchupBtn.textContent = this.currentMatchupIndex + 1 < this.matchups.length ? "Next Matchup" : "View Tournament Results";
        }
    }
    
    nextMatchup() {
        this.clearAiAnswerTimeouts();
        this.currentMatchupIndex++;
        
        if (this.currentMatchupIndex < this.matchups.length) {
            document.getElementById("question-area").style.display = "block";
            document.getElementById("round-result").style.display = "none";
            document.getElementById("next-matchup-btn").style.display = "none";
            this.startMatchup();
        } else {
            this.endTournament();
        }
    }
    
    calculateTeamRankings() {
        // Create array of team stats - use TOTAL TIME (lower is better) for tie-breaking
        const teamStats = this.teamNames.map(team => ({
            team: team,
            correctAnswers: this.teamCorrectAnswers[team] || 0,
            totalTime: this.teamTotalTime[team] || 0,
            responseCount: this.teamResponseCount[team] || 0,
            avgTime: this.teamResponseCount[team] > 0 ? this.teamTotalTime[team] / this.teamResponseCount[team] : Infinity,
            matchupWins: this.teamScores[team] || 0
        }));
        
        console.log("Team Stats for Ranking:", teamStats);
        
        // Sort by: 1) Most correct answers, 2) Lowest total time (faster overall)
        teamStats.sort((a, b) => {
            // First compare by correct answers (descending)
            if (b.correctAnswers !== a.correctAnswers) {
                return b.correctAnswers - a.correctAnswers;
            }
            // If correct answers are tied, compare by TOTAL TIME (lower is better)
            // Teams with no responses get Infinity and go to the end
            if (a.totalTime !== b.totalTime) {
                if (a.totalTime === Infinity) return 1;
                if (b.totalTime === Infinity) return -1;
                return a.totalTime - b.totalTime;
            }
            // If still tied, compare by matchup wins
            if (b.matchupWins !== a.matchupWins) {
                return b.matchupWins - a.matchupWins;
            }
            return 0;
        });
        
        // Check for ties (teams with same correct answers and same total time)
        const tiedTeams = [];
        for (let i = 0; i < teamStats.length - 1; i++) {
            if (teamStats[i].correctAnswers === teamStats[i + 1].correctAnswers && 
                teamStats[i].totalTime === teamStats[i + 1].totalTime) {
                if (!tiedTeams.includes(teamStats[i].team)) tiedTeams.push(teamStats[i].team);
                if (!tiedTeams.includes(teamStats[i + 1].team)) tiedTeams.push(teamStats[i + 1].team);
            }
        }
        
        if (tiedTeams.length > 0) {
            console.log("Tie detected between teams:", tiedTeams);
            this.teamsInTie = tiedTeams;
            this.tieBreakerNeeded = true;
        }
        
        return teamStats;
    }
    
    async runTieBreaker(tiedTeams) {
        console.log("Running tie-breaker for teams:", tiedTeams);
        
        // Create a temporary tournament for tied teams
        const tieBreakerMatchups = [];
        for (let i = 0; i < tiedTeams.length; i++) {
            for (let j = i + 1; j < tiedTeams.length; j++) {
                tieBreakerMatchups.push({
                    team1: tiedTeams[i],
                    team2: tiedTeams[j],
                    team1Score: 0,
                    team2Score: 0,
                    results: []
                });
            }
        }
        
        // Store original overlay
        const originalOverlay = this.overlay;
        
        // Create a new promise that resolves when tie-breaker is complete
        return new Promise((resolve) => {
            let currentMatchupIndex = 0;
            let tieBreakerScores = {};
            tiedTeams.forEach(team => { tieBreakerScores[team] = 0; });
            
            function playNextMatchup() {
                if (currentMatchupIndex >= tieBreakerMatchups.length) {
                    // All tie-breaker matchups complete
                    const sortedTiedTeams = Object.entries(tieBreakerScores)
                        .sort((a, b) => b[1] - a[1])
                        .map(entry => entry[0]);
                    resolve(sortedTiedTeams);
                    return;
                }
                
                const matchup = tieBreakerMatchups[currentMatchupIndex];
                
                // Create a temporary overlay for tie-breaker
                const tempOverlay = document.createElement('div');
                tempOverlay.className = 'game-setup-overlay';
                tempOverlay.innerHTML = `
                    <div class="setup-card quiz-card">
                        <h2>TIE-BREAKER ROUND</h2>
                        <div style="text-align: center; margin-bottom: 20px;">
                            <p>Teams are tied! Answer 3 questions to break the tie.</p>
                            <p style="font-size: 14px; color: #666;">Faster correct answers win points!</p>
                        </div>
                        <div class="teams-panel">
                            <div class="team-panel team1-panel">
                                <h3>${matchup.team1}</h3>
                                <div class="team-score">Score: <span id="tb-team1-score">0</span></div>
                                <div class="team-total-time">Total Time: <span id="tb-team1-time">0.0</span>s</div>
                                <div class="team-keys">Use keys: 1 2 3 4</div>
                            </div>
                            <div class="team-panel team2-panel">
                                <h3>${matchup.team2}</h3>
                                <div class="team-score">Score: <span id="tb-team2-score">0</span></div>
                                <div class="team-total-time">Total Time: <span id="tb-team2-time">0.0</span>s</div>
                                <div class="team-keys">Use keys: 6 7 8 9</div>
                            </div>
                        </div>
                        <div id="tb-question-area" class="question-area">
                            <div id="tb-question-text" class="question-text">Loading...</div>
                            <div id="tb-options-area" class="options-area">
                                <div id="tb-option-a" class="competition-option">A. </div>
                                <div id="tb-option-b" class="competition-option">B. </div>
                                <div id="tb-option-c" class="competition-option">C. </div>
                                <div id="tb-option-d" class="competition-option">D. </div>
                            </div>
                        </div>
                        <div class="setup-actions">
                            <button id="tb-next-btn" class="setup-btn-primary" style="display: none;">Next Question</button>
                        </div>
                    </div>
                `;
                document.body.appendChild(tempOverlay);
                tempOverlay.style.display = "flex";
                
                let tbQuestions = this.getRandomQuestions(3, 'all');
                let tbCurrentQuestionIndex = 0;
                let tbTeam1Score = 0;
                let tbTeam2Score = 0;
                let tbTeam1TotalTime = 0;
                let tbTeam2TotalTime = 0;
                let tbQuestionActive = true;
                let tbCountdownInterval = null;
                let tbTimeRemaining = 30;
                let tbQuestionStartTime = null;
                let tbTeam1Locked = false;
                let tbTeam2Locked = false;
                
                function updateTBScores() {
                    document.getElementById("tb-team1-score").textContent = tbTeam1Score;
                    document.getElementById("tb-team2-score").textContent = tbTeam2Score;
                    document.getElementById("tb-team1-time").textContent = (tbTeam1TotalTime / 1000).toFixed(1);
                    document.getElementById("tb-team2-time").textContent = (tbTeam2TotalTime / 1000).toFixed(1);
                }
                
                function displayTBQuestion() {
                    if (tbCurrentQuestionIndex >= tbQuestions.length) {
                        // Matchup complete - determine winner by score, then time
                        tempOverlay.remove();
                        
                        if (tbTeam1Score > tbTeam2Score) {
                            tieBreakerScores[matchup.team1] += 1;
                        } else if (tbTeam2Score > tbTeam1Score) {
                            tieBreakerScores[matchup.team2] += 1;
                        } else {
                            // Tie in score - use total time
                            if (tbTeam1TotalTime < tbTeam2TotalTime) {
                                tieBreakerScores[matchup.team1] += 1;
                            } else if (tbTeam2TotalTime < tbTeam1TotalTime) {
                                tieBreakerScores[matchup.team2] += 1;
                            }
                            // If complete tie, no points awarded
                        }
                        
                        currentMatchupIndex++;
                        playNextMatchup();
                        return;
                    }
                    
                    if (tbCountdownInterval) clearInterval(tbCountdownInterval);
                    tbQuestionActive = true;
                    tbTeam1Locked = false;
                    tbTeam2Locked = false;
                    tbQuestionStartTime = Date.now();
                    
                    const question = tbQuestions[tbCurrentQuestionIndex];
                    const correctAnswer = this.getCorrectLetter(question.correct);
                    
                    document.getElementById("tb-question-text").innerHTML = `Question ${tbCurrentQuestionIndex + 1} of 3: ${question.content}`;
                    document.getElementById("tb-option-a").innerHTML = `A. ${question.options.a}`;
                    document.getElementById("tb-option-b").innerHTML = `B. ${question.options.b}`;
                    document.getElementById("tb-option-c").innerHTML = `C. ${question.options.c}`;
                    document.getElementById("tb-option-d").innerHTML = `D. ${question.options.d}`;
                    
                    document.getElementById("tb-next-btn").style.display = "none";
                    
                    // Reset option styles
                    document.querySelectorAll("#tb-options-area .competition-option").forEach(opt => {
                        opt.style.background = "#f0f0f0";
                        opt.style.border = "2px solid #ddd";
                        opt.style.cursor = "pointer";
                        opt.style.opacity = "1";
                    });
                    
                    tbTimeRemaining = 30;
                    let timerEl = document.getElementById("tb-timer");
                    if (!timerEl) {
                        timerEl = document.createElement('div');
                        timerEl.id = "tb-timer";
                        timerEl.className = "question-timer";
                        const header = document.querySelector("#tb-question-area");
                        if (header) header.parentNode.insertBefore(timerEl, header);
                    }
                    timerEl.textContent = "Time: 30s";
                    timerEl.style.background = "var(--main-orange)";
                    timerEl.style.display = "block";
                    
                    tbCountdownInterval = setInterval(() => {
                        if (!tbQuestionActive) return;
                        tbTimeRemaining--;
                        timerEl.textContent = `Time: ${tbTimeRemaining}s`;
                        if (tbTimeRemaining <= 10 && tbTimeRemaining > 0) {
                            timerEl.style.background = "#e74c3c";
                        } else if (tbTimeRemaining <= 20 && tbTimeRemaining > 0) {
                            timerEl.style.background = "#f39c12";
                        } else if (tbTimeRemaining > 0) {
                            timerEl.style.background = "var(--main-orange)";
                        }
                        
                        if (tbTimeRemaining <= 0) {
                            clearInterval(tbCountdownInterval);
                            tbQuestionActive = false;
                            timerEl.style.display = "none";
                            
                            // Record times for unanswered teams
                            if (!tbTeam1Locked && tbQuestionStartTime) {
                                tbTeam1TotalTime += 30000;
                            }
                            if (!tbTeam2Locked && tbQuestionStartTime) {
                                tbTeam2TotalTime += 30000;
                            }
                            
                            updateTBScores();
                            document.getElementById("tb-next-btn").style.display = "block";
                            
                            // Highlight correct answer
                            const correctElement = document.getElementById(`tb-option-${correctAnswer}`);
                            if (correctElement) {
                                correctElement.style.background = "#27ae60";
                                correctElement.style.border = "2px solid #1e7e34";
                                correctElement.style.color = "white";
                            }
                        }
                    }, 1000);
                    
                    const handleTBAnswer = (team, selectedOption) => {
                        if (!tbQuestionActive) return;
                        if ((team === 1 && tbTeam1Locked) || (team === 2 && tbTeam2Locked)) return;
                        
                        const isCorrect = (selectedOption === correctAnswer);
                        const timeSpent = tbQuestionStartTime ? Date.now() - tbQuestionStartTime : 30000;
                        
                        if (team === 1) {
                            tbTeam1Locked = true;
                            tbTeam1TotalTime += timeSpent;
                            if (isCorrect) {
                                tbTeam1Score++;
                                tbQuestionActive = false;
                                clearInterval(tbCountdownInterval);
                                timerEl.style.display = "none";
                                document.getElementById("tb-next-btn").style.display = "block";
                            }
                        } else {
                            tbTeam2Locked = true;
                            tbTeam2TotalTime += timeSpent;
                            if (isCorrect) {
                                tbTeam2Score++;
                                tbQuestionActive = false;
                                clearInterval(tbCountdownInterval);
                                timerEl.style.display = "none";
                                document.getElementById("tb-next-btn").style.display = "block";
                            }
                        }
                        
                        updateTBScores();
                        
                        // Highlight correct answer when question ends
                        if (isCorrect || (tbTeam1Locked && tbTeam2Locked)) {
                            const correctElement = document.getElementById(`tb-option-${correctAnswer}`);
                            if (correctElement) {
                                correctElement.style.background = "#27ae60";
                                correctElement.style.border = "2px solid #1e7e34";
                                correctElement.style.color = "white";
                            }
                            document.querySelectorAll("#tb-options-area .competition-option").forEach(opt => {
                                opt.style.cursor = "not-allowed";
                                opt.style.opacity = "0.5";
                            });
                        }
                    };
                    
                    const tbKeyHandler = (e) => {
                        const key = e.key;
                        const mapping = {
                            '1': { team: 1, option: 'a' },
                            '2': { team: 1, option: 'b' },
                            '3': { team: 1, option: 'c' },
                            '4': { team: 1, option: 'd' },
                            '6': { team: 2, option: 'a' },
                            '7': { team: 2, option: 'b' },
                            '8': { team: 2, option: 'c' },
                            '9': { team: 2, option: 'd' }
                        };
                        if (mapping[key] && tbQuestionActive) {
                            e.preventDefault();
                            handleTBAnswer(mapping[key].team, mapping[key].option);
                        }
                    };
                    
                    document.addEventListener("keydown", tbKeyHandler);
                    
                    const nextBtn = document.getElementById("tb-next-btn");
                    nextBtn.onclick = () => {
                        document.removeEventListener("keydown", tbKeyHandler);
                        tbCurrentQuestionIndex++;
                        displayTBQuestion();
                    };
                }
                
                displayTBQuestion();
            }
            
            playNextMatchup();
        });
    }
    
    endTournament() {
        // Calculate rankings based on correct answers and total time
        const rankedTeams = this.calculateTeamRankings();
        
        console.log("Final Rankings (based on correct answers and total time):", rankedTeams);
        
        // Format the ranked teams for the original startMarketSelection function
        const formattedForMarketSelection = rankedTeams.map((team, index) => ({
            team: team.team,
            score: team.correctAnswers,  // Use correct answers as the score for ranking
            wins: team.matchupWins,
            correctAnswers: team.correctAnswers,
            totalTime: (team.totalTime / 1000).toFixed(2),
            avgTime: team.avgTime !== Infinity ? (team.avgTime / 1000).toFixed(2) : 'N/A'
        }));
        
        this.clearAiAnswerTimeouts();
        this.overlay.remove();
        this.removeEventListeners();
        
        // Check if tie-breaker is needed
        if (this.tieBreakerNeeded && this.teamsInTie.length > 0) {
            console.log("Tie-breaker required for teams:", this.teamsInTie);
            alert("A tie has been detected! Running tie-breaker rounds...");
            
            this.runTieBreaker(this.teamsInTie).then((sortedTiedTeams) => {
                // Update rankings with tie-breaker results
                const finalRankings = [];
                for (const team of formattedForMarketSelection) {
                    if (this.teamsInTie.includes(team.team)) {
                        const position = sortedTiedTeams.indexOf(team.team);
                        finalRankings.push({ ...team, tieBreakerOrder: position });
                    } else {
                        finalRankings.push(team);
                    }
                }
                // Re-sort with tie-breaker order
                finalRankings.sort((a, b) => {
                    if (a.tieBreakerOrder !== undefined && b.tieBreakerOrder !== undefined) {
                        return a.tieBreakerOrder - b.tieBreakerOrder;
                    }
                    if (a.tieBreakerOrder !== undefined) return 1;
                    if (b.tieBreakerOrder !== undefined) return -1;
                    return b.score - a.score;
                });
                
                console.log("Final Rankings after tie-breaker:", finalRankings);
                if (this.onComplete) {
                    this.onComplete(finalRankings, this.tournamentResults);
                }
            });
        } else {
            if (this.onComplete) {
                this.onComplete(formattedForMarketSelection, this.tournamentResults);
            }
        }
    }
    
    setupEventListeners() {
        this.boundHandleAnswer = this.handleAnswer.bind(this);
        this.boundNextQuestion = this.nextQuestion.bind(this);
        this.boundNextMatchup = this.nextMatchup.bind(this);
        this.boundKeyDown = this.onKeyDown.bind(this);
        
        document.addEventListener("keydown", this.boundKeyDown);
        
        const nextQuestionBtn = document.getElementById("next-question-btn");
        if (nextQuestionBtn) nextQuestionBtn.onclick = this.boundNextQuestion;
        
        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) nextMatchupBtn.onclick = this.boundNextMatchup;
    }
    
    removeEventListeners() {
        document.removeEventListener("keydown", this.boundKeyDown);
    }
    
    onKeyDown(event) {
        const key = event.key;
        if (this.keyToOption[key] && this.questionActive) {
            const { team, option } = this.keyToOption[key];
            const teamName = team === 1 ? this.currentMatchup?.team1 : this.currentMatchup?.team2;
            if (teamName && this.isAiTeam(teamName)) {
                event.preventDefault();
                return;
            }
            if ((team === 1 && window.team1Locked) || (team === 2 && window.team2Locked)) {
                return;
            }
            event.preventDefault();
            this.handleAnswer(team, option);
        }
    }
}
