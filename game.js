const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const keys = {};
const mouse = { x: 0, y: 0, pressed: false };

// Player
const player = {
    x: canvas.width/2,
    y: canvas.height/2,
    radius: 15,
    speed: 4,
    health: 100,
    xp: 0,
    level: 1,
    bullets: [],
    upgrades: [],
    fireRate: 10,
    fireCooldown: 0
};

// Enemy types
const enemies = [];
const enemyTypes = ["Chaser", "Shooter", "Dasher", "Tank", "Orbiter", "Splitter"];

// Bosses
const bosses = [
    { name: "Juggernaut", health: 500, x: 100, y: 100, attackCooldown: 0 },
    { name: "Sentinel", health: 400, x: 700, y: 100, attackCooldown: 0 },
    { name: "Hive", health: 300, x: 400, y: 500, attackCooldown: 0 }
];

// Upgrades (original + extras)
const allUpgrades = [
    "Faster Shooting", "Double Damage", "Health Regen", "Shield",
    "Speed Boost", "Homing Bullets", "Piercing Shots", "Extra Life"
];

// Event listeners
document.addEventListener('keydown', e => keys[e.key] = true);
document.addEventListener('keyup', e => keys[e.key] = false);

canvas.addEventListener('mousemove', e => {
    const rect = canvas.getBoundingClientRect();
    mouse.x = e.clientX - rect.left;
    mouse.y = e.clientY - rect.top;
});
canvas.addEventListener('mousedown', () => mouse.pressed = true);
canvas.addEventListener('mouseup', () => mouse.pressed = false);

// Spawn enemy
function spawnEnemy() {
    const type = enemyTypes[Math.floor(Math.random()*enemyTypes.length)];
    const enemy = {
        x: Math.random()*canvas.width,
        y: Math.random()*canvas.height,
        radius: 15,
        type: type,
        health: type==="Tank" ? 50 : 20,
        speed: type==="Dasher" ? 6 : 2
    };
    enemies.push(enemy);
}

// Shoot
function shoot() {
    if(player.fireCooldown <= 0){
        const angle = Math.atan2(mouse.y - player.y, mouse.x - player.x);
        player.bullets.push({ x: player.x, y: player.y, angle: angle, speed: 10, damage: player.upgrades.includes("Double Damage") ? 20 : 10 });
        player.fireCooldown = player.fireRate;
    }
}

// Update
function update() {
    // Player movement
    if(keys['w'] || keys['ArrowUp']) player.y -= player.speed;
    if(keys['s'] || keys['ArrowDown']) player.y += player.speed;
    if(keys['a'] || keys['ArrowLeft']) player.x -= player.speed;
    if(keys['d'] || keys['ArrowRight']) player.x += player.speed;

    // Fire bullets
    if(mouse.pressed) shoot();
    if(player.fireCooldown > 0) player.fireCooldown--;

    // Update bullets
    player.bullets.forEach((b, i) => {
        b.x += Math.cos(b.angle) * b.speed;
        b.y += Math.sin(b.angle) * b.speed;
        if(b.x<0 || b.x>canvas.width || b.y<0 || b.y>canvas.height) player.bullets.splice(i,1);
    });

    // Enemy AI: target player
    enemies.forEach(enemy => {
        const dx = player.x - enemy.x;
        const dy = player.y - enemy.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        const nx = dx/dist;
        const ny = dy/dist;
        enemy.x += nx * enemy.speed;
        enemy.y += ny * enemy.speed;
    });

    // Enemy collisions
    enemies.forEach((enemy, ei) => {
        player.bullets.forEach((b, bi) => {
            const dx = b.x - enemy.x;
            const dy = b.y - enemy.y;
            if(Math.sqrt(dx*dx + dy*dy) < 15){
                enemy.health -= b.damage;
                if(!player.upgrades.includes("Piercing Shots")) player.bullets.splice(bi,1);
                if(enemy.health <= 0){
                    enemies.splice(ei,1);
                    player.xp += 10;
                    if(Math.random()<0.2) dropUpgrade(enemy.x, enemy.y);
                }
            }
        });

        // Enemy hits player
        const dx = player.x - enemy.x;
        const dy = player.y - enemy.y;
        if(Math.sqrt(dx*dx + dy*dy) < 20){
            player.health -= 0.5;
        }
    });

    // Boss behavior
    bosses.forEach(boss => {
        // Boss attacks player every 60 frames
        if(boss.attackCooldown <= 0){
            shootBossBullet(boss);
            boss.attackCooldown = 60;
        } else boss.attackCooldown--;

        // Check bullet collision
        player.bullets.forEach((b, bi) => {
            const dx = b.x - boss.x;
            const dy = b.y - boss.y;
            if(Math.sqrt(dx*dx + dy*dy) < 25){
                boss.health -= b.damage;
                player.bullets.splice(bi,1);
            }
        });

        if(boss.health <= 0){
            // Boss defeated
            player.xp += 100;
            boss.health = 0;
        }
    });

    // Spawn enemies if below 10
    if(enemies.length < 10) spawnEnemy();

    // Player health regen
    if(player.upgrades.includes("Health Regen") && player.health < 100) player.health += 0.1;

    // Update UI
    document.getElementById('health').innerText = `Health: ${Math.floor(player.health)}`;
    document.getElementById('xp').innerText = `XP: ${player.xp}`;

    // Update upgrades
    const upgradeList = document.getElementById('upgradeList');
    upgradeList.innerHTML = '';
    player.upgrades.forEach(u => {
        const li = document.createElement('li');
        li.textContent = u;
        upgradeList.appendChild(li);
    });

    // Game over
    if(player.health <= 0){
        alert("Game Over!");
        window.location.reload();
    }
}

// Boss shoot
function shootBossBullet(boss){
    const angle = Math.atan2(player.y - boss.y, player.x - boss.x);
    enemies.push({ x: boss.x, y: boss.y, radius: 5, type: "BossBullet", speed: 8, angle: angle, damage: 5 });
}

// Upgrade drops
const upgradeDrops = [];
function dropUpgrade(x, y){
    const upgrade = allUpgrades[Math.floor(Math.random()*allUpgrades.length)];
    upgradeDrops.push({ x, y, upgrade });
}

// Check pickup
function checkPickups(){
    upgradeDrops.forEach((u, i) => {
        const dx = player.x - u.x;
        const dy = player.y - u.y;
        if(Math.sqrt(dx*dx + dy*dy) < 20){
            if(!player.upgrades.includes(u.upgrade)) player.upgrades.push(u.upgrade);
            upgradeDrops.splice(i,1);
        }
    });
}

// Draw
function draw(){
    ctx.clearRect(0,0,canvas.width,canvas.height);

    // Player
    ctx.fillStyle = 'cyan';
    ctx.beginPath();
    ctx.arc(player.x, player.y, player.radius, 0, Math.PI*2);
    ctx.fill();

    // Bullets
    ctx.fillStyle = 'yellow';
    player.bullets.forEach(b => {
        ctx.beginPath();
        ctx.arc(b.x, b.y, 5, 0, Math.PI*2);
        ctx.fill();
    });

    // Enemies
    enemies.forEach(enemy => {
        if(enemy.type === "BossBullet") ctx.fillStyle = 'orange';
        else ctx.fillStyle = 'red';
        ctx.beginPath();
        ctx.arc(enemy.x, enemy.y, enemy.radius, 0, Math.PI*2);
        ctx.fill();
    });

    // Upgrade drops
    upgradeDrops.forEach(u => {
        ctx.fillStyle = 'green';
        ctx.beginPath();
        ctx.rect(u.x-5, u.y-5, 10, 10);
        ctx.fill();
    });

    // Bosses
    bosses.forEach(boss => {
        ctx.fillStyle = 'purple';
        ctx.beginPath();
        ctx.arc(boss.x, boss.y, 25, 0, Math.PI*2);
        ctx.fill();
        ctx.fillStyle = 'white';
        ctx.fillText(boss.name, boss.x-20, boss.y-30);
    });
}

// Main loop
function loop(){
    update();
    checkPickups();
    draw();
    requestAnimationFrame(loop);
}

loop();
