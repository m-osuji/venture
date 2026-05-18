// Reusable Tournament Module
export class TournamentQuiz {
    constructor(teamNames, questionBank, getCorrectLetter, getRandomQuestions) {
        this.teamNames = teamNames;
        this.questionBank = questionBank;
        this.getCorrectLetter = getCorrectLetter;
        this.getRandomQuestions = getRandomQuestions;
        this.matchups = [];
        this.currentMatchupIndex = 0;
        this.currentQuestionIndex = 0;
        this.teamScores = {};
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
        // Initialize team scores
        this.teamNames.forEach(team => {
            this.teamScores[team] = 0;
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
        
        this.updateScores();
        this.updateTournamentProgress();
        this.displayQuestion();
        
        const nextMatchupBtn = document.getElementById("next-matchup-btn");
        if (nextMatchupBtn) nextMatchupBtn.style.display = "none";
    }
    
    updateScores() {
        document.getElementById("team1-score").textContent = this.matchupTeam1Score;
        document.getElementById("team2-score").textContent = this.matchupTeam2Score;
    }
    
    updateTournamentProgress() {
        const progressDiv = document.getElementById("tournament-progress");
        if (progressDiv) {
            progressDiv.innerHTML = `Matchup ${this.currentMatchupIndex + 1} of ${this.matchups.length} | Best of 3 Questions`;
        }
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
        
        const question = this.currentQuestions[this.currentQuestionIndex];
        window.currentCorrectAnswer = this.getCorrectLetter(question.correct);
        
        document.getElementById("question-text").innerHTML = `Question ${this.currentQuestionIndex + 1} of ${this.currentQuestions.length}: ${question.content}`;
        document.getElementById("option-a").innerHTML = `A. ${question.options.a}`;
        document.getElementById("option-b").innerHTML = `B. ${question.options.b}`;
        document.getElementById("option-c").innerHTML = `C. ${question.options.c}`;
        document.getElementById("option-d").innerHTML = `D. ${question.options.d}`;
        
        document.getElementById("round-result").style.display = "none";
        document.getElementById("next-question-btn").style.display = "none";
        
        const buzzerStatus = document.getElementById("buzzer-status");
        if (buzzerStatus) {
            buzzerStatus.innerHTML = "First to answer correctly wins the point!";
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
                            question: this.currentQuestions[this.currentQuestionIndex].text,
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
                }
            }
        }, 1000);
    }
    
    handleAnswer(team, selectedOption) {
        if (!this.questionActive) return false;
        
        const question = this.currentQuestions[this.currentQuestionIndex];
        const isCorrect = (selectedOption === window.currentCorrectAnswer);
        
        if (isCorrect) {
            this.stopCountdown();
            this.questionActive = false;
            
            if (team === 1) {
                this.matchupTeam1Score++;
                const buzzerStatus = document.getElementById("buzzer-status");
                if (buzzerStatus) {
                    buzzerStatus.innerHTML = `${this.currentMatchup.team1} answered correctly! +1 point`;
                    buzzerStatus.style.background = "#27ae60";
                }
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${this.currentMatchup.team1} earns the point!</span>`;
                }
            } else {
                this.matchupTeam2Score++;
                const buzzerStatus = document.getElementById("buzzer-status");
                if (buzzerStatus) {
                    buzzerStatus.innerHTML = `${this.currentMatchup.team2} answered correctly! +1 point`;
                    buzzerStatus.style.background = "#27ae60";
                }
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: green; font-weight: bold;">CORRECT! ${this.currentMatchup.team2} earns the point!</span>`;
                }
            }
            
            this.updateScores();
            
            this.currentMatchupResults.push({
                questionNumber: this.currentQuestionIndex + 1,
                question: question.text,
                correctAnswer: question.correct,
                correctAnswerText: question.options[window.currentCorrectAnswer],
                winningTeam: team === 1 ? this.currentMatchup.team1 : this.currentMatchup.team2,
                winningTeamId: team
            });
            
            const roundResult = document.getElementById("round-result");
            if (roundResult) roundResult.style.display = "block";
            
            const nextBtn = document.getElementById("next-question-btn");
            if (nextBtn) nextBtn.style.display = "block";
            
            const correctLetter = this.getCorrectLetter(question.correct);
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
            if (team === 1) {
                window.team1Locked = true;
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: red;">WRONG! ${this.currentMatchup.team1} loses this turn. ${this.currentMatchup.team2} can still answer.</span>`;
                    roundResult.style.display = "block";
                }
                if (window.team2Locked) this.handleDoubleWrong();
            } else if (team === 2) {
                window.team2Locked = true;
                const roundResult = document.getElementById("round-result");
                if (roundResult) {
                    roundResult.innerHTML = `<span style="color: red;">WRONG! ${this.currentMatchup.team2} loses this turn. ${this.currentMatchup.team1} can still answer.</span>`;
                    roundResult.style.display = "block";
                }
                if (window.team1Locked) this.handleDoubleWrong();
            }
            return false;
        }
    }
    
    handleDoubleWrong() {
        if (window.team1Locked && window.team2Locked && this.questionActive) {
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
            details: this.currentMatchupResults
        });
        
        document.getElementById("question-area").style.display = "none";
        document.getElementById("next-question-btn").style.display = "none";
        
        let resultHtml = `
            <div style="text-align: center;">
                <h3>MATCHUP COMPLETE</h3>
                <div style="font-size: 20px; margin: 15px 0;">
                    ${this.currentMatchup.team1}: ${this.matchupTeam1Score}<br>
                    ${this.currentMatchup.team2}: ${this.matchupTeam2Score}
                </div>
                <div style="font-size: 24px; font-weight: bold; color: ${winner !== "Tie" ? "#27ae60" : "#f39c12"};">
                    ${winner !== "Tie" ? `WINNER: ${winner}` : "IT'S A TIE!"}
                </div>
            </div>
        `;
        
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
    
    endTournament() {
        const rankedTeams = Object.entries(this.teamScores)
            .map(([team, score]) => ({ team, score }))
            .sort((a, b) => b.score - a.score);
        
        this.overlay.remove();
        this.removeEventListeners();
        
        if (this.onComplete) {
            this.onComplete(rankedTeams, this.tournamentResults);
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
            if ((team === 1 && window.team1Locked) || (team === 2 && window.team2Locked)) {
                return;
            }
            event.preventDefault();
            this.handleAnswer(team, option);
        }
    }
}