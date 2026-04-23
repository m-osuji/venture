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
        width: window.innerWidth,
        height: window.innerHeight,
        parent: container,
        backgroundColor: '#ffffff',
        scale: {
            mode: Phaser.Scale.RESIZE,
            autoCenter: Phaser.Scale.CENTER_BOTH
        },
        input: {
            mouse: {
                target: document.getElementById('board-container')
            },
            touch: {
                target: document.getElementById('board-container')
            }
        },
        scene: {
            preload,
            create,
            update
        }
    };

    setTimeout(() => {
        game = new Phaser.Game(config);
    }, 50);
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
    this.load.image('board', '/images/game_board.png');
    this.load.on('filecomplete-image-board', () => {
        console.log('Board image loaded successfully');
    });
    this.load.on('loaderror', (file) => {
        console.error('FAILED TO LOAD:', file.src);
    });
}

// Create the map
function create() {
    const board = this.add.image(0, 0, 'board');

    const resize = (width, height) => {
        console.log("Resizing to:", width, height);

        board.setPosition(width / 2, height / 2);

        const scaleX = width / board.width;
        const scaleY = height / board.height;
        const scale = Math.min(scaleX, scaleY);

        board.setScale(scale);
    };

    resize(this.scale.width, this.scale.height);

    this.scale.on('resize', (gameSize) => {
        resize(gameSize.width, gameSize.height);
    });

    // Scroll fix
    this.input.on('wheel', (pointer, gameObjects, deltaX, deltaY) => {
        window.scrollBy(0, deltaY);
    });

    this.input.on('pointerdown', (pointer) => {
        console.log(`Clicked at: ${pointer.x}, ${pointer.y}`);
    });
}

// Update the game loop
function update() {
    // Add any information to update or any animations here
}