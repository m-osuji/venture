import * as Phaser from 'phaser';

let game = null;

export function startGame() {
    // Prevent multiple instances
    if (game) return;

    const container = document.getElementById('board-container');

    // Safety check (important for SPA routing)
    if (!container) {
        console.warn("No #board-container found. Phaser not started.");
        return;
    }

    // Define the game configuration
    const config = {
        type: Phaser.AUTO,
        width: 800,
        height: 600,
        parent: 'board-container',
        backgroundColor: '#1e1e1e',
        scene: {
            preload,
            create,
            update
        }
    };

    game = new Phaser.Game(config);
    console.log("Phaser game started");
}

// Called when leaving /game
export function stopGame() {
    if (game) {
        game.destroy(true); // true = remove canvas from DOM
        game = null;
        console.log("Phaser game destroyed");
    }
}

// Create a Phaser game instance
//const game = new Phaser.Game(config);

// Preload assets
function preload() {
    this.load.image('board', 'images/game_board.png');
}

// Create the map
function create() {
    const board = this.add.image(400, 300, 'board');
    board.setDisplaySize(800, 600);
    console.log("Board loaded");
    // Testing mouse scroll
    this.input.mouse.disableContextMenu();
    this.input.on('wheel', (pointer, gameObjects, deltaX, deltaY) => {
        window.scrollBy(0, deltaY);
    });
    //
    this.input.on('pointerdown', (pointer) => {
        console.log(`Clicked at: ${pointer.x}, ${pointer.y}`);
    });
}

// Update the game loop
function update() {
    // Add any information to update or any animations here
}