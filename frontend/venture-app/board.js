import Phaser from 'phaser';

// Define the game configuration
const config = {
    type: Phaser.AUTO,
    width: 800,
    height: 600,
    parent: 'board-container',
    scene: {
        preload: preload,
        create: create,
        update: update
    }
};

// Create a Phaser game instance
const game = new Phaser.Game(config);

// Preload assets
function preload() {
    this.load.image('Game Board', 'images/game_board.png');
}

// Create the map
function create() {
    this.add.image(400, 300, 'Game Board');
}

// Update the game loop
function update() {
    // Add any information to update or any animations here
}