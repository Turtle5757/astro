const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

const hud = {
  health: document.getElementById('health'),
  xp: document.getElementById('xp'),
  level: document.getElementById('level')
};

let keys = {};
let mouse = {x: 0, y: 0, pressed: false};

// Player
const player = {
  x: canvas.width/2,
  y: canvas.height/2,
  radius: 15,
  speed: 5,
  health: 100,
  xp: 0,
  level: 1,
  bullets: []
};

// Enemies
const enemies = [];
const enemyTypes = ["Chaser","Shooter","Dasher","Tank","Orbiter","Splitter"];

// Bosses
const bosses = ["Juggernaut","Sentinel","Hive"];
let bossSpawned = false;

// Skill tree
const skills = {
  damage: 0,
  health: 0,
  speed: 0,
  fireRate: 0
};

// Prestige
let prestige = 0;

// Key/mouse events
document.addEventListener('keydown', e => keys[e.key.toLowerCase()] = true);
document.addEventListener('keyup', e => keys[e.key.toLowerCase()] = false);
canvas.addEventListener('mousemove', e => {
  const rect = canvas.getBoundingClientRect();
  mouse.x = e.clientX - rect.left;
  mouse.y = e.clientY - rect.top;
});
canvas.addEventListener('mousedown', () => mouse.pressed = true);
canvas.addEventListener('mouseup', () => mouse.pressed = false);

// HUD buttons
const skillMenu = document.getElementById('menu');
document.getElementById('skillButton').addEventListener('click', () => skillMenu.classList.remove('hidden'));
document.getElementById('closeSkill').addEventListener('click', () => skillMenu.classList.add('hidden'));
document.getElementById('prestigeButton').addEventListener('click', () => {
  prestige++;
  player.level = 1;
  player.xp = 0;
  player.health = 100;
  alert('Prestige increased! Current Prestige: ' + prestige);
  saveGame();
});

// Skill tree buttons
const skillDiv = document.getElementById('skills');
for (let skill in skills) {
  const btn = document.createElement('button');
  btn.innerText = `${skill} (${skills[skill]})`;
  btn.className = 'skillBtn';
  btn.onclick = () => { skills[skill]++; btn.innerText = `${skill} (${skills[skill]})`; saveGame(); };
  skillDiv.appendChild(btn);
}

// Bullet class
class Bullet {
  constructor(x,y,dx,dy){
    this.x = x;
    this.y = y;
    this.dx = dx;
    this.dy = dy;
    this.radius = 5;
  }
  update(){
    this.x += this.dx;
    this.y += this.dy;
  }
  draw(){
    ctx.beginPath();
    ctx.arc(this.x,this.y,this.radius,0,Math.PI*2);
    ctx.fillStyle = 'yellow';
    ctx.fill();
  }
}

// Enemy class
class Enemy {
  constructor(x,y,type){
    this.x = x;
    this.y = y;
    this.type = type;
    this.radius = 15 + Math.random()*10;
    this.speed = 1 + Math.random()*2;
    this.health = 20 + Math.random()*30;
    this.angle = Math.random()*Math.PI*2;
  }
  update(){
    switch(this.type){
      case "Chaser":
        const dx = player.x - this.x;
        const dy = player.y - this.y;
        const dist = Math.hypot(dx,dy);
        this.x += (dx/dist)*this.speed;
        this.y += (dy/dist)*this.speed;
        break;
      case "Shooter":
        // stays in place for simplicity
        break;
      case "Orbiter":
        this.angle += 0.05;
        this.x += Math.cos(this.angle)*this.speed;
        this.y += Math.sin(this.angle)*this.speed;
        break;
      case "Dasher":
        if(Math.random()<0.02){
          const dx = player.x - this.x;
          const dy = player.y - this.y;
          const dist = Math.hypot(dx,dy);
          this.x += (dx/dist)*this.speed*5;
          this.y += (dy/dist)*this.speed*5;
        }
        break;
      case "Tank":
        this.speed = 0.5;
        const tdx = player.x - this.x;
        const tdy = player.y - this.y;
        const tdist = Math.hypot(tdx,tdy);
        this.x += (tdx/tdist)*this.speed;
        this.y += (tdy/tdist)*this.speed;
        break;
      case "Splitter":
        this.x += Math.random()*2-1;
        this.y += Math.random()*2-1;
        break;
    }
  }
  draw(){
    ctx.beginPath();
    ctx.arc(this.x,this.y,this.radius,0,Math.PI*2);
    ctx.fillStyle = 'red';
    ctx.fill();
  }
}

// Spawn enemies
function spawnEnemy(){
  const x = Math.random()*canvas.width;
  const y = Math.random()*canvas.height;
  const type = enemyTypes[Math.floor(Math.random()*enemyTypes.length)];
  enemies.push(new Enemy(x,y,type));
}

// Game loop
function update(){
  // Movement
  if(keys['w']) player.y -= player.speed + skills.speed;
  if(keys['s']) player.y += player.speed + skills.speed;
  if(keys['a']) player.x -= player.speed + skills.speed;
  if(keys['d']) player.x += player.speed + skills.speed;

  // Shooting
  if(mouse.pressed){
    const angle = Math.atan2(mouse.y-player.y, mouse.x-player.x);
    player.bullets.push(new Bullet(player.x,player.y,Math.cos(angle)*10,Math.sin(angle)*10));
    mouse.pressed = false; // semi-auto fire, modify for full auto
  }

  // Update bullets
  player.bullets.forEach((b,i)=>{
    b.update();
    // Check collision with enemies
    enemies.forEach((e,j)=>{
      const dist = Math.hypot(b.x-e.x,b.y-e.y);
      if(dist < b.radius + e.radius){
        e.health -= 10 + skills.damage;
        if(e.health <= 0){
          player.xp += 10;
          enemies.splice(j,1);
          if(player.xp >= player.level*50){
            player.level++;
            player.xp = 0;
          }
        }
        player.bullets.splice(i,1);
      }
    });
    // Remove offscreen
    if(b.x < 0 || b.x > canvas.width || b.y < 0 || b.y > canvas.height){
      player.bullets.splice(i,1);
    }
  });

  // Update enemies
  enemies.forEach(e => e.update());

  // Update HUD
  hud.health.innerText = `Health: ${player.health}`;
  hud.xp.innerText = `XP: ${player.xp}`;
  hud.level.innerText = `Level: ${player.level}`;
}

// Draw loop
function draw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);

  // Draw player
  ctx.beginPath();
  ctx.arc(player.x,player.y,player.radius,0,Math.PI*2);
  ctx.fillStyle = 'lime';
  ctx.fill();

  // Draw bullets
  player.bullets.forEach(b => b.draw());

  // Draw enemies
  enemies.forEach(e => e.draw());
}

// Main loop
function loop(){
  if(Math.random()<0.02) spawnEnemy(); // spawn rate
  update();
  draw();
  requestAnimationFrame(loop);
}

loop();

// Save/load system
function saveGame(){
  const data = {
    player,
    skills,
    prestige
  };
  localStorage.setItem('shooterSave',JSON.stringify(data));
}

function loadGame(){
  const data = JSON.parse(localStorage.getItem('shooterSave'));
  if(data){
    Object.assign(player,data.player);
    Object.assign(skills,data.skills);
    prestige = data.prestige;
  }
}

loadGame();
setInterval(saveGame,5000);
