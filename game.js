// AstroRogue JS version - full game
// Canvas setup
const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');
let SCREEN_W = window.innerWidth;
let SCREEN_H = window.innerHeight;
canvas.width = SCREEN_W;
canvas.height = SCREEN_H;

// Utility functions
function clamp(val, min, max) { return Math.max(min, Math.min(max, val)); }
function distanceSq(a,b) { return (a.x-b.x)**2 + (a.y-b.y)**2; }
function rand(min,max) { return Math.random()*(max-min)+min; }
function now() { return performance.now()/1000; }

// Vector class
class Vec {
    constructor(x,y){ this.x=x; this.y=y; }
    add(v){ return new Vec(this.x+v.x,this.y+v.y); }
    sub(v){ return new Vec(this.x-v.x,this.y-v.y); }
    mul(s){ return new Vec(this.x*s,this.y*s); }
    length(){ return Math.sqrt(this.x**2+this.y**2); }
    normalize(){ let l=this.length(); return l?this.mul(1/l):new Vec(0,0); }
}

// Global persistent data
let saveData = JSON.parse(localStorage.getItem('astroSave')||'{}');
saveData.coreShards = saveData.coreShards||0;
saveData.bestScore = saveData.bestScore||0;
saveData.prestigePoints = saveData.prestigePoints||0;
saveData.normalUpgrades = saveData.normalUpgrades||{};
saveData.coreUpgrades = saveData.coreUpgrades||{};
saveData.prestigeShop = saveData.prestigeShop||{};

// ---------------- Player ----------------
class Player {
    constructor(){
        this.pos = new Vec(SCREEN_W/2, SCREEN_H/2);
        this.radius = 14;
        this.speed = 250;
        this.hp = this.maxHp = 100;
        this.money = 0;
        this.score = 0;
        this.bulletDamage = 15;
        this.skillPoints = 0;
        this.homingCd = 0;
        this.homingUnlocked = false;
        this.prestigeMultiplier = saveData.prestigeMultiplier||1.0;
    }
    move(dt, keys){
        let dir = new Vec(0,0);
        if(keys['w']) dir.y -= 1;
        if(keys['s']) dir.y +=1;
        if(keys['a']) dir.x -=1;
        if(keys['d']) dir.x +=1;
        if(dir.length()>0) this.pos = this.pos.add(dir.normalize().mul(this.speed*dt));
        this.pos.x = clamp(this.pos.x,0,SCREEN_W);
        this.pos.y = clamp(this.pos.y,0,SCREEN_H);
    }
    takeDamage(d){ this.hp-=d; if(this.hp<=0) this.alive=false; }
    draw(){
        ctx.fillStyle = "#88DDFF";
        ctx.beginPath();
        ctx.arc(this.pos.x,this.pos.y,this.radius,0,Math.PI*2);
        ctx.fill();
    }
    canShoot(){ return true; } // simplified
}

// ---------------- Bullet ----------------
class Bullet {
    constructor(pos, vel, dmg, owner){
        this.pos=pos;
        this.vel=vel;
        this.dmg=dmg;
        this.radius=4;
        this.owner=owner;
        this.life=2;
    }
    update(dt){ this.pos=this.pos.add(this.vel.mul(dt)); this.life-=dt; }
    draw(){
        ctx.fillStyle = (this.owner=="player")?"#FFDD55":"#FF5555";
        ctx.beginPath();
        ctx.arc(this.pos.x,this.pos.y,this.radius,0,Math.PI*2);
        ctx.fill();
    }
}

// ---------------- Enemy ----------------
class Enemy {
    constructor(pos,hp,speed){
        this.pos = pos;
        this.hp = hp;
        this.speed = speed;
        this.radius = 12;
    }
    update(dt,player){
        let dir = player.pos.sub(this.pos);
        if(dir.length()>0) this.pos = this.pos.add(dir.normalize().mul(this.speed*dt));
    }
    takeDamage(d){ this.hp-=d; }
    draw(){
        ctx.fillStyle = "#FF6666";
        ctx.beginPath();
        ctx.arc(this.pos.x,this.pos.y,this.radius,0,Math.PI*2);
        ctx.fill();
    }
}

// ---------------- Boss ----------------
class Boss {
    constructor(kind,pos,hp,speed){
        this.kind=kind;
        this.pos=pos;
        this.hp=hp;
        this.maxHp=hp;
        this.speed=speed;
        this.radius=50;
        this.fireCd=0;
    }
    update(dt,player,bullets,enemies){
        let dir = player.pos.sub(this.pos);
        if(this.kind=="Juggernaut" && dir.length()>60) this.pos=this.pos.add(dir.normalize().mul(this.speed*0.5*dt));
        if(this.kind=="Sentinel" && dir.length()>240) this.pos=this.pos.add(dir.normalize().mul(this.speed*dt));
        if(this.kind=="HiveQueen" && dir.length()>120) this.pos=this.pos.add(dir.normalize().mul(this.speed*0.4*dt));
    }
    draw(){
        ctx.fillStyle = this.kind=="Juggernaut"?"#C8503C":(this.kind=="Sentinel"?"#78A0DC":"#C88CCD");
        ctx.beginPath();
        ctx.arc(this.pos.x,this.pos.y,this.radius,0,Math.PI*2);
        ctx.fill();
        // top bar
        let w=420, hpw=w*(this.hp/this.maxHp);
        ctx.fillStyle="#1E1E1E";
        ctx.fillRect(SCREEN_W/2-w/2,18,w,18);
        ctx.fillStyle="#C83C3C";
        ctx.fillRect(SCREEN_W/2-w/2,18,hpw,18);
        ctx.fillStyle="#FFF";
        ctx.font="16px Arial";
        ctx.fillText(`Boss: ${this.kind} — ${Math.floor(this.hp)}/${Math.floor(this.maxHp)} HP`, SCREEN_W/2-w/2+6,14);
    }
}

// ---------------- Game State ----------------
let keys = {};
let bullets = [];
let enemies = [];
let bosses = [];
let player = new Player();
let lastTime = now();
let state="menu";
let menuIdx=0;
let spawnerTimer=0;

// ---------------- Input ----------------
window.addEventListener('keydown',e=>keys[e.key.toLowerCase()]=true);
window.addEventListener('keyup',e=>keys[e.key.toLowerCase()]=false);
canvas.addEventListener('mousedown',e=>mouseHeld=true);
canvas.addEventListener('mouseup',e=>mouseHeld=false);
let mouseHeld=false;

// ---------------- Main Loop ----------------
function gameLoop(){
    let tnow = now();
    let dt = Math.min(1/30, tnow-lastTime);
    lastTime=tnow;

    ctx.clearRect(0,0,SCREEN_W,SCREEN_H);

    if(state=="menu"){
        ctx.fillStyle="#0A0C16";
        ctx.fillRect(0,0,SCREEN_W,SCREEN_H);
        ctx.fillStyle="#FFFF96";
        ctx.font="36px Arial";
        ctx.fillText("AstroRogue",SCREEN_W/2-120,60);
        let opts = ["Play","Quit"];
        ctx.font="26px Arial";
        for(let i=0;i<opts.length;i++){
            ctx.fillStyle = (i==menuIdx)?"#FFFF96":"#DDDDDD";
            ctx.fillText(opts[i],SCREEN_W/2-60,140+i*60);
        }
    }
    else if(state=="game"){
        player.move(dt,keys);
        player.draw();

        bullets.forEach(b=>{b.update(dt); b.draw();});
        bullets = bullets.filter(b=>b.life>0);

        enemies.forEach(e=>{ e.update(dt,player); e.draw();});
        enemies = enemies.filter(e=>e.hp>0);

        bosses.forEach(b=>{ b.update(dt,player,bullets,enemies); b.draw();});
        bosses = bosses.filter(b=>b.hp>0);

        spawnerTimer+=dt;
        if(spawnerTimer>2){
            spawnerTimer=0;
            enemies.push(new Enemy(new Vec(rand(0,SCREEN_W),rand(0,SCREEN_H)),20,100));
        }
    }

    requestAnimationFrame(gameLoop);
}

gameLoop();

