// game.js - Part 1: Core Engine + Player + Controls
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

let gameRunning = false;

// Player
const player = {
    x: canvas.width / 2,
    y: canvas.height / 2,
    radius: 15,
    color: "#00f",
    speed: 5,
    health: 100,
    maxHealth: 100,
    xp: 0,
    level: 1
};

// Input
const keys = {};
window.addEventListener("keydown", (e) => keys[e.key] = true);
window.addEventListener("keyup", (e) => keys[e.key] = false);

// Game Loop
function gameLoop() {
    if (!gameRunning) return;
    update();
    draw();
    requestAnimationFrame(gameLoop);
}

// Update
function update() {
    // Movement
    if (keys["w"] || keys["ArrowUp"]) player.y -= player.speed;
    if (keys["s"] || keys["ArrowDown"]) player.y += player.speed;
    if (keys["a"] || keys["ArrowLeft"]) player.x -= player.speed;
    if (keys["d"] || keys["ArrowRight"]) player.x += player.speed;

    // Keep player inside canvas
    player.x = Math.max(player.radius, Math.min(canvas.width - player.radius, player.x));
    player.y = Math.max(player.radius, Math.min(canvas.height - player.radius, player.y));
}

// Draw
function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw player
    ctx.fillStyle = player.color;
    ctx.beginPath();
    ctx.arc(player.x, player.y, player.radius, 0, Math.PI * 2);
    ctx.fill();

    // Draw health bar
    ctx.fillStyle = "#fff";
    ctx.fillRect(player.x - 20, player.y - 30, 40, 5);
    ctx.fillStyle = "#f00";
    ctx.fillRect(player.x - 20, player.y - 30, 40 * (player.health / player.maxHealth), 5);
}

// Start Game
document.getElementById("start-button").addEventListener("click", () => {
    document.getElementById("main-menu").style.display = "none";
    canvas.style.display = "block";
    gameRunning = true;
    gameLoop();
});
// Enemy definitions
class Enemy {
    constructor(x, y, type = "chaser") {
        this.x = x;
        this.y = y;
        this.radius = 15;
        this.color = "#f00";
        this.speed = type === "chaser" ? 2 : 1;
        this.type = type;
        this.health = 50;
        this.maxHealth = 50;
        this.damage = 10;
    }

    update() {
        // Basic AI: move towards player
        let dx = player.x - this.x;
        let dy = player.y - this.y;
        let distance = Math.sqrt(dx * dx + dy * dy);

        if (distance > 0) {
            this.x += (dx / distance) * this.speed;
            this.y += (dy / distance) * this.speed;
        }

        // Collision with player
        if (distance < this.radius + player.radius) {
            player.health -= this.damage * 0.05; // continuous damage
            if (player.health < 0) player.health = 0;
        }
    }

    draw() {
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fill();

        // Health bar
        ctx.fillStyle = "#fff";
        ctx.fillRect(this.x - 15, this.y - 25, 30, 4);
        ctx.fillStyle = "#0f0";
        ctx.fillRect(this.x - 15, this.y - 25, 30 * (this.health / this.maxHealth), 4);
    }
}

const enemies = [];

// Spawn enemies
function spawnEnemy() {
    let x = Math.random() < 0.5 ? 0 : canvas.width;
    let y = Math.random() * canvas.height;
    let types = ["chaser", "shooter", "dasher"];
    let type = types[Math.floor(Math.random() * types.length)];
    enemies.push(new Enemy(x, y, type));
}

// Enemy loop inside update
function updateEnemies() {
    enemies.forEach((enemy, index) => {
        enemy.update();
        if (enemy.health <= 0) {
            enemies.splice(index, 1);
            player.xp += 10;
        }
    });
}

// Draw enemies
function drawEnemies() {
    enemies.forEach(enemy => enemy.draw());
}

// Integrate into main update/draw
function update() {
    // Player movement
    if (keys["w"] || keys["ArrowUp"]) player.y -= player.speed;
    if (keys["s"] || keys["ArrowDown"]) player.y += player.speed;
    if (keys["a"] || keys["ArrowLeft"]) player.x -= player.speed;
    if (keys["d"] || keys["ArrowRight"]) player.x += player.speed;

    player.x = Math.max(player.radius, Math.min(canvas.width - player.radius, player.x));
    player.y = Math.max(player.radius, Math.min(canvas.height - player.radius, player.y));

    // Update enemies
    updateEnemies();

    // Auto spawn new enemies every 3 seconds
    if (!update.lastSpawnTime) update.lastSpawnTime = Date.now();
    if (Date.now() - update.lastSpawnTime > 3000) {
        spawnEnemy();
        update.lastSpawnTime = Date.now();
    }

    // Check if player is dead
    if (player.health <= 0) {
        gameRunning = false;
        alert("You Died! Game Over.");
        location.reload();
    }
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw player
    ctx.fillStyle = player.color;
    ctx.beginPath();
    ctx.arc(player.x, player.y, player.radius, 0, Math.PI * 2);
    ctx.fill();

    // Player health bar
    ctx.fillStyle = "#fff";
    ctx.fillRect(player.x - 20, player.y - 30, 40, 5);
    ctx.fillStyle = "#f00";
    ctx.fillRect(player.x - 20, player.y - 30, 40 * (player.health / player.maxHealth), 5);

    // Draw enemies
    drawEnemies();
}
// --- Projectiles ---
class Projectile {
    constructor(x, y, targetX, targetY, damage = 20, speed = 7) {
        this.x = x;
        this.y = y;
        this.radius = 5;
        this.damage = damage;
        this.speed = speed;

        // Direction vector
        let dx = targetX - x;
        let dy = targetY - y;
        let distance = Math.sqrt(dx*dx + dy*dy);
        this.vx = (dx / distance) * speed;
        this.vy = (dy / distance) * speed;
    }

    update() {
        this.x += this.vx;
        this.y += this.vy;

        // Collision with enemies
        enemies.forEach((enemy, index) => {
            let dx = enemy.x - this.x;
            let dy = enemy.y - this.y;
            let dist = Math.sqrt(dx*dx + dy*dy);
            if (dist < enemy.radius + this.radius) {
                enemy.health -= this.damage;
                projectiles.splice(projectiles.indexOf(this), 1);
            }
        });

        // Remove if off screen
        if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) {
            projectiles.splice(projectiles.indexOf(this), 1);
        }
    }

    draw() {
        ctx.fillStyle = "#ff0";
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
        ctx.fill();
    }
}

const projectiles = [];

canvas.addEventListener("click", (e) => {
    projectiles.push(new Projectile(player.x, player.y, e.clientX, e.clientY));
});

// --- Bosses ---
class Boss extends Enemy {
    constructor(x, y, type = "juggernaut") {
        super(x, y, "boss");
        this.type = type;
        this.health = 500;
        this.maxHealth = 500;
        this.radius = 40;
        this.color = "#800080";
        this.speed = 1.5;
        this.damage = 25;
        this.attackCooldown = 0;
    }

    update() {
        // Boss AI varies by type
        if (this.type === "juggernaut") {
            // Slow chaser
            let dx = player.x - this.x;
            let dy = player.y - this.y;
            let distance = Math.sqrt(dx*dx + dy*dy);
            this.x += (dx / distance) * this.speed;
            this.y += (dy / distance) * this.speed;
        } else if (this.type === "sentinel") {
            // Shoots projectiles
            if (this.attackCooldown <= 0) {
                projectiles.push(new Projectile(this.x, this.y, player.x, player.y, 15, 5));
                this.attackCooldown = 60; // cooldown frames
            } else {
                this.attackCooldown--;
            }
        }

        // Collision damage to player
        let dx = player.x - this.x;
        let dy = player.y - this.y;
        if (Math.sqrt(dx*dx + dy*dy) < this.radius + player.radius) {
            player.health -= this.damage * 0.05;
            if (player.health < 0) player.health = 0;
        }
    }

    draw() {
        ctx.fillStyle = this.color;
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.radius, 0, Math.PI*2);
        ctx.fill();

        // Health bar
        ctx.fillStyle = "#fff";
        ctx.fillRect(this.x - 40, this.y - 50, 80, 6);
        ctx.fillStyle = "#f0f";
        ctx.fillRect(this.x - 40, this.y - 50, 80 * (this.health/this.maxHealth), 6);
    }
}

const bosses = [];

// Spawn a boss
function spawnBoss() {
    let x = Math.random() * canvas.width;
    let y = Math.random() * canvas.height;
    let types = ["juggernaut", "sentinel"];
    let type = types[Math.floor(Math.random()*types.length)];
    bosses.push(new Boss(x, y, type));
}

// --- Player Upgrades ---
const upgrades = {
    health: {level: 1, cost: 50, apply: () => player.maxHealth += 20, name: "Health Boost"},
    speed: {level: 1, cost: 50, apply: () => player.speed += 0.5, name: "Speed Boost"},
    damage: {level: 1, cost: 50, apply: () => playerDamage += 5, name: "Damage Boost"},
};

// Upgrade function
function buyUpgrade(type) {
    if (player.xp >= upgrades[type].cost) {
        player.xp -= upgrades[type].cost;
        upgrades[type].apply();
        upgrades[type].level++;
        upgrades[type].cost = Math.floor(upgrades[type].cost * 1.5);
    }
}

// --- Main Menu ---
let gameRunning = false;

function showMainMenu() {
    ctx.clearRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = "#222";
    ctx.fillRect(0,0,canvas.width,canvas.height);
    ctx.fillStyle = "#fff";
    ctx.font = "40px Arial";
    ctx.fillText("Awesome Shooter Game", canvas.width/2 - 180, canvas.height/2 - 100);
    ctx.font = "30px Arial";
    ctx.fillText("Click to Start", canvas.width/2 - 80, canvas.height/2);
    canvas.addEventListener("click", startGameOnce);
}

function startGameOnce() {
    canvas.removeEventListener("click", startGameOnce);
    gameRunning = true;
    gameLoop();
}

// --- Game Loop ---
function gameLoop() {
    if (gameRunning) {
        update();
        projectiles.forEach(p => p.update());
        draw();
        projectiles.forEach(p => p.draw());
        requestAnimationFrame(gameLoop);
    }
}

// Start menu
showMainMenu();
