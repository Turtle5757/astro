# main.py
"""
AstroRogue — Top-down shooter with:
- Mouse aim, hold LMB to shoot
- Many enemy types + bosses
- XP orbs -> levels -> skill points -> skill tree
- Normal upgrade tree (money), Core upgrade tree (Core Shards), Skill tree
- Prestige system; Core upgrades & Core Shards persist
- Player clamped to screen; bullets removed off-screen
Save file: save.json
Requires: pygame
Run: python main.py
"""
from collections import defaultdict
import math, random, time, json, os, sys
import pygame

# ---------------------------
# Config / Tunables
# ---------------------------
SCREEN_W, SCREEN_H = 1200, 760
FPS = 60
SAVE_PATH = "save.json"

# Gameplay tuning
BASE_SPAWN_INTERVAL = 1.8
BOSS_INTERVAL = 55.0
ENEMY_CAP = 40
PRESTIGE_THRESHOLD = 6000
XP_PER_LEVEL_BASE = 100  # XP required for level 1; grows linearly

# Save defaults
DEFAULT_SAVE = {
    "normal_upgrades": {},   # id -> level
    "core_upgrades": {},     # id -> level or bought flag (persist)
    "skill_tree": {},        # id -> bought in persistent slot? (we'll keep skill resets per-run)
    "prestige_points": 0,
    "prestige_multiplier": 1.0,
    "prestige_shop": {},     # permanent perks bought with prestige points
    "core_shards": 0,
    "best_score": 0,
    "adv_upgrades": {},      # alias for core/advanced persistent purchases
}

# ---------------------------
# Persistence
# ---------------------------
def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            return default.copy()
    return default.copy()

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

save_data = load_json(SAVE_PATH, DEFAULT_SAVE)

# ---------------------------
# Pygame init
# ---------------------------
pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("AstroRogue")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont("Arial", 16)
BIG = pygame.font.SysFont("Arial", 36)
SMALL = pygame.font.SysFont("Arial", 14)
vec = pygame.math.Vector2

def draw_text(surf, s, pos, size=16, c=(255,255,255)):
    font = pygame.font.SysFont("Arial", size)
    surf.blit(font.render(s, True, c), pos)

# ---------------------------
# Utility helpers
# ---------------------------
def clamp(v, a, b): return max(a, min(b, v))
def now_time(): return time.time()

# ---------------------------
# Upgrade trees data (tiered layouts)
# We'll do Normal tree (money), Core tree (core shards), Skill tree (skill points)
# Each node: id, name, pos, base_cost, max_level, prereqs list of (id, min_level), desc, effect(player, level)
# ---------------------------

# Normal upgrades (money)
NORMAL_UPGRADES = {
    "root_speed":    {"name":"Engine I", "pos":(SCREEN_W//2, SCREEN_H-140), "base_cost":100, "max_level":3, "prereqs":[], "desc":"+8% speed per level"},
    "speed_2":       {"name":"Engine II", "pos":(SCREEN_W//2 - 200, SCREEN_H-320), "base_cost":220, "max_level":3, "prereqs":[("root_speed",1)], "desc":"+10% speed per level"},
    "speed_3":       {"name":"Engine III", "pos":(SCREEN_W//2 + 200, SCREEN_H-320), "base_cost":420, "max_level":2, "prereqs":[("speed_2",1)], "desc":"+12% speed per level"},
    "fire_1":        {"name":"AutoFeed I", "pos":(SCREEN_W//2 - 380, SCREEN_H-520), "base_cost":120, "max_level":3, "prereqs":[("root_speed",1)], "desc":"+12% fire rate per level"},
    "damage_1":      {"name":"Rounds I", "pos":(SCREEN_W//2 - 120, SCREEN_H-520), "base_cost":140, "max_level":3, "prereqs":[("root_speed",1)], "desc":"+6 damage per level"},
    "hp_1":          {"name":"Plating I", "pos":(SCREEN_W//2 + 140, SCREEN_H-520), "base_cost":160, "max_level":4, "prereqs":[("root_speed",1)], "desc":"+25 HP per level"},
    "money_1":       {"name":"Scavenger", "pos":(SCREEN_W//2 + 380, SCREEN_H-520), "base_cost":150, "max_level":4, "prereqs":[("hp_1",1)], "desc":"+10% money per level"},
    "bullet_speed":  {"name":"Light Rounds", "pos":(SCREEN_W//2 - 240, SCREEN_H-700), "base_cost":200, "max_level":2, "prereqs":[("fire_1",1)], "desc":"+20% bullet speed per level"},
    "homing":        {"name":"Homing Missiles", "pos":(SCREEN_W//2 + 0, SCREEN_H-700), "base_cost":420, "max_level":1, "prereqs":[("damage_1",2)], "desc":"Unlock homing (H)"},
    "shield_on_spawn":{"name":"Spawn Shield", "pos":(SCREEN_W//2 + 240, SCREEN_H-700), "base_cost":380, "max_level":1, "prereqs":[("hp_1",2)], "desc":"Gain 1-time shield at spawn"},
}

NORMAL_CONNECTIONS = [
    ("root_speed","speed_2"), ("root_speed","speed_3"),
    ("root_speed","fire_1"), ("root_speed","damage_1"), ("root_speed","hp_1"),
    ("fire_1","bullet_speed"), ("damage_1","homing"), ("hp_1","money_1"), ("hp_1","shield_on_spawn"),
]

def normal_cost(uid, level):
    return int(NORMAL_UPGRADES[uid]["base_cost"] * (1.9 ** level))

# Core upgrades (Core Shards) — persistent across prestige
CORE_UPGRADES = {
    "core_pierce1": {"name":"Pierce I","pos":(180,160),"cost":2,"max_level":1,"prereqs":[],"desc":"Pierce 1 enemy"},
    "core_pierce2": {"name":"Pierce II","pos":(380,80),"cost":4,"max_level":1,"prereqs":[("core_pierce1",1)],"desc":"Pierce 2 enemies"},
    "core_double":  {"name":"Double Shot","pos":(580,160),"cost":5,"max_level":1,"prereqs":[("core_pierce1",1)],"desc":"Shoot double bullets"},
    "core_explode": {"name":"Explosive Rounds","pos":(780,80),"cost":6,"max_level":1,"prereqs":[("core_double",1)],"desc":"Bullets explode on hit"},
    "core_shield":  {"name":"Shield Regen","pos":(980,160),"cost":6,"max_level":1,"prereqs":[("core_double",1)],"desc":"Regenerate shield slowly"},
}

CORE_CONNS = [("core_pierce1","core_pierce2"),("core_pierce1","core_double"),("core_double","core_explode"),("core_double","core_shield")]

# Skill tree (skill points earned in-run). This resets between runs but can be used mid-run
SKILL_TREE = {
    "skill_evasion": {"name":"Evasion","pos":(SCREEN_W-300,200),"cost":1,"max_level":3,"prereqs":[],"desc":"Chance to dodge damage"},
    "skill_crit":    {"name":"Critical","pos":(SCREEN_W-300,320),"cost":1,"max_level":3,"prereqs":[("skill_evasion",1)],"desc":"Chance to deal 150% damage"},
    "skill_regen":   {"name":"Regeneration","pos":(SCREEN_W-300,440),"cost":1,"max_level":2,"prereqs":[("skill_crit",1)],"desc":"Slow HP regen"},
    "skill_shield":  {"name":"Quick Shield","pos":(SCREEN_W-300,560),"cost":1,"max_level":1,"prereqs":[("skill_regen",1)],"desc":"Small shield cooldown reduction"},
}

SKILL_CONN = [("skill_evasion","skill_crit"),("skill_crit","skill_regen"),("skill_regen","skill_shield")]

# Prestige shop (spend prestige points)
PRESTIGE_SHOP = {
    "ps_dmg5": ("+5% Damage", 1, "Permanent +5% damage"),
    "ps_money10": ("+10% Money", 2, "Permanent +10% money"),
    "ps_fire5": ("+5% Fire Rate", 2, "Permanent +5% fire rate"),
}

# Advanced/persistent effects for core upgrades and prestige purchases will be interpreted in player.apply_persistent_bonuses()

# ---------------------------
# Player, bullets, enemies, bosses, xp orbs
# ---------------------------
class Player:
    def __init__(self):
        # base stats
        self._base_speed = 220.0
        self._base_fire = 5.0
        self._base_damage = 14
        self._base_hp = 100
        self._base_bspeed = 520.0
        self._base_money_mult = 1.0

        # dynamic stats
        self.speed = self._base_speed
        self.fire_rate = self._base_fire
        self.bullet_damage = self._base_damage
        self.max_health = self._base_hp
        self.health = self.max_health
        self.bullet_speed = self._base_bspeed
        self.money_mult = self._base_money_mult

        self.pos = vec(SCREEN_W/2, SCREEN_H/2)
        self.vel = vec(0,0)
        self.radius = 14
        self.angle = 0.0
        self.last_shot = 0.0

        # progression
        self.score = 0
        self.money = 0
        self.level = 1
        self.xp = 0
        self.xp_next = XP_PER_LEVEL_BASE
        self.skill_points = 0

        # flags
        self.homing_unlocked = False
        self.homing_cd = 0.0
        self.shield_on_spawn = False
        self.shield_active = False

        # apply persistent save-based bonuses (core upgrades & prestige shop)
        self.apply_persistent_bonuses()
        # apply normal upgrades for current run
        self.apply_normal_upgrades()

        self.alive = True

    def clamp_to_screen(self):
        self.pos.x = clamp(self.pos.x, self.radius, SCREEN_W - self.radius)
        self.pos.y = clamp(self.pos.y, self.radius, SCREEN_H - self.radius)

    def apply_persistent_bonuses(self):
        # core upgrades (persist)
        cu = save_data.get("core_upgrades", {})
        # default adjustments will be applied in shoot/damage handling; but we use flags here
        self._persist = {}
        if cu.get("core_pierce1"): self._persist["pierce"] = max(self._persist.get("pierce",0),1)
        if cu.get("core_pierce2"): self._persist["pierce"] = max(self._persist.get("pierce",0),2)
        if cu.get("core_pierce3"): self._persist["pierce"] = max(self._persist.get("pierce",0),3)
        if cu.get("core_double"): self._persist["double_shot"] = True
        if cu.get("core_explode"): self._persist["explode"] = True
        if cu.get("core_shield"): self._persist["shield_regen"] = True
        # prestige shop perks
        ps = save_data.get("prestige_shop", {})
        if ps.get("ps_dmg5"): self.bullet_damage = int(self.bullet_damage * 1.05)
        if ps.get("ps_money10"): self.money_mult *= 1.10
        if ps.get("ps_fire5"): self.fire_rate *= 1.05
        # prestige multiplier
        self.prestige_multiplier = save_data.get("prestige_multiplier", 1.0)

    def apply_normal_upgrades(self):
        # reset to base then apply upgrades levels from save_data["normal_upgrades"]
        self.speed = self._base_speed
        self.fire_rate = self._base_fire
        self.bullet_damage = self._base_damage
        self.max_health = self._base_hp
        self.bullet_speed = self._base_bspeed
        self.money_mult = self._base_money_mult
        self.homing_unlocked = False
        self.shield_on_spawn = False

        for uid, lvl in save_data.get("normal_upgrades", {}).items():
            if uid not in NORMAL_UPGRADES: continue
            # apply simplistic effects based on id patterns (keeps code short)
            if "speed" in uid:
                self.speed = self._base_speed * (1.08 ** lvl)
            if "fire" in uid:
                self.fire_rate = self._base_fire * (1.12 ** lvl)
            if "damage" in uid:
                self.bullet_damage = self._base_damage + (6 * lvl)
            if "hp" in uid:
                self.max_health = self._base_hp + (25 * lvl)
            if "money" in uid:
                self.money_mult = self._base_money_mult * (1.10 ** lvl)
            if "bullet_speed" in uid:
                self.bullet_speed = self._base_bspeed * (1.20 ** lvl)
            if uid == "homing" and lvl > 0:
                self.homing_unlocked = True
            if uid == "shield_on_spawn" and lvl > 0:
                self.shield_on_spawn = True
        self.health = min(self.health, self.max_health)

    def spawn_reset(self):
        self.pos = vec(SCREEN_W/2, SCREEN_H/2)
        self.vel = vec(0,0)
        self.health = self.max_health
        self.alive = True
        self.shield_active = self.shield_on_spawn
        self.last_shot = 0.0
        self.homing_cd = 0.0
        self.xp = 0
        self.level = 1
        self.skill_points = 0
        self.xp_next = XP_PER_LEVEL_BASE

    def update(self, dt, keys):
        move = vec(0,0)
        if keys[pygame.K_w] or keys[pygame.K_UP]: move.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]: move.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]: move.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]: move.x += 1
        if move.length_squared() > 0:
            self.vel += move.normalize() * self.speed * dt
        self.vel *= 0.97
        self.pos += self.vel * dt
        self.clamp_to_screen()
        self.homing_cd = max(0, self.homing_cd - dt)
        # level up if XP reached
        while self.xp >= self.xp_next:
            self.xp -= self.xp_next
            self.level += 1
            self.skill_points += 1
            # next xp grows linearly
            self.xp_next += XP_PER_LEVEL_BASE
        # passive shield regen if core upgrade present
        if save_data.get("core_upgrades", {}).get("core_shield"):
            # small regen over time
            self.health = min(self.max_health, self.health + 0.5 * dt)

    def aim_at_mouse(self):
        mx,my = pygame.mouse.get_pos()
        dirv = vec(mx,my) - self.pos
        if dirv.length_squared() > 0.001:
            self.angle = math.degrees(math.atan2(-dirv.y, dirv.x))

    def can_shoot(self, t):
        return (t - self.last_shot) >= (1.0 / self.fire_rate)

    def shoot(self, t):
        # returns list of bullets produced
        self.last_shot = t
        ang = math.radians(self.angle)
        dirv = vec(math.cos(ang), -math.sin(ang))
        pos = self.pos + dirv*(self.radius+8)
        vel = dirv*self.bullet_speed + self.vel*0.2
        bullets = []
        # double shot core upgrade?
        if save_data.get("core_upgrades", {}).get("core_double"):
            b1 = Bullet(pos, vel.rotate(-6), int(self.bullet_damage), "player")
            b2 = Bullet(pos, vel.rotate(6), int(self.bullet_damage), "player")
            bullets.extend([b1,b2])
        else:
            bullets.append(Bullet(pos, vel, int(self.bullet_damage), "player"))
        # apply pierce
        pierce = 0
        if save_data.get("core_upgrades", {}).get("core_pierce2"): pierce = 2
        elif save_data.get("core_upgrades", {}).get("core_pierce1"): pierce = 1
        for b in bullets:
            b.pierce = pierce
            if save_data.get("core_upgrades", {}).get("core_explode"):
                b.explode = True
        return bullets

    def draw(self, surf):
        ang = math.radians(self.angle)
        fwd = vec(math.cos(ang), -math.sin(ang))
        right = fwd.rotate(120)
        left = fwd.rotate(-120)
        pts = [(self.pos + fwd*self.radius).xy, (self.pos + right*self.radius).xy, (self.pos + left*self.radius).xy]
        pygame.draw.polygon(surf, (180,220,255), pts)
        # HUD
        pygame.draw.rect(surf, (30,30,30), (12,12,320,22))
        hpw = int(320 * (self.health/self.max_health))
        pygame.draw.rect(surf, (200,60,60), (12,12,hpw,22))
        draw_text(surf, f"HP: {int(self.health)}/{int(self.max_health)}", (340,10), 16)
        draw_text(surf, f"Score: {self.score}", (12,40), 18)
        draw_text(surf, f"Money: {self.money}", (12,62), 18)
        draw_text(surf, f"Core Shards: {save_data.get('core_shards',0)}", (12,84), 16)
        draw_text(surf, f"Level: {self.level}  XP: {int(self.xp)}/{self.xp_next}", (12,104), 16)
        draw_text(surf, f"Skill pts: {self.skill_points}", (12,126), 16)
        draw_text(surf, f"Prestige pts: {save_data.get('prestige_points',0)}", (12,146), 14)
        if self.shield_active:
            pygame.draw.circle(surf, (90,180,255), (int(self.pos.x), int(self.pos.y)), int(self.radius*1.6), 2)

    def take_damage(self, dmg):
        # chance to dodge via skill tree? apply simple check if skill_evasion bought in active skill nodes (stored in run_skills)
        # run_skills global var used in skill tree implementation
        if RUN_STATE.get("run_skills", {}).get("skill_evasion",0) > 0:
            chance = 0.06 * RUN_STATE["run_skills"]["skill_evasion"]  # 6% per point
            if random.random() < chance:
                return  # dodged
        # shield
        if self.shield_active:
            self.shield_active = False
            return
        # take damage
        crit_mult = 1.0
        if RUN_STATE.get("run_skills", {}).get("skill_crit",0) > 0:
            chance = 0.05 * RUN_STATE["run_skills"]["skill_crit"]
            if random.random() < chance:
                crit_mult = 1.5
        self.health -= dmg * crit_mult
        if self.health <= 0:
            self.alive = False

class Bullet:
    def __init__(self, pos, vel, dmg, owner="enemy"):
        self.pos = vec(pos)
        self.vel = vec(vel)
        self.dmg = dmg
        self.owner = owner
        self.radius = 4
        self.life = 4.0
        self.pierce = 0
        self.explode = False

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt
        # bullets destroyed if off-screen (requirement)
        if not (0 <= self.pos.x <= SCREEN_W and 0 <= self.pos.y <= SCREEN_H):
            self.life = -1

    def draw(self, surf):
        col = (255,230,120) if self.owner=="player" else (255,120,120)
        pygame.draw.circle(surf, col, (int(self.pos.x), int(self.pos.y)), self.radius)

class XPOrb:
    def __init__(self, pos, amount):
        self.pos = vec(pos)
        self.amount = amount
        self.radius = 8
        self.life = 12.0
        self.collected = False
        self.spawn_time = now_time()

    def update(self, dt, player):
        # slowly drift downwards and attract to player with proximity
        dirp = player.pos - self.pos
        d = dirp.length()
        if d < 140:
            self.pos += dirp.normalize() * (120 * dt)
        else:
            self.pos.y += 10 * dt
        self.life -= dt
        if d < (self.radius + player.radius + 6):
            # auto-collect
            player.xp += self.amount
            self.collected = True

    def draw(self, surf):
        pygame.draw.circle(surf, (120,200,255), (int(self.pos.x), int(self.pos.y)), self.radius)
        draw_text(surf, f"{self.amount}", (int(self.pos.x)-6,int(self.pos.y)-8), 12)

# Enemy types
class Enemy:
    def __init__(self, pos, hp, speed, color=(220,100,100), score_reward=20, xp_reward=12):
        self.pos = vec(pos)
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.radius = 16
        self.vel = vec(random.uniform(-1,1), random.uniform(-1,1)).normalize() * speed
        self.color = color
        self.score_reward = score_reward
        self.xp_reward = xp_reward

    def update(self, dt, player):
        # basic seeker
        dirv = player.pos - self.pos
        if dirv.length_squared() > 0.01:
            self.vel += dirv.normalize() * (self.speed * 0.6) * dt
        if self.vel.length() > 0.01:
            self.vel = self.vel.normalize() * self.speed
        self.pos += self.vel * dt
        # bounce off edges (enemies can't leave screen; they bounce back)
        if self.pos.x < self.radius: 
            self.pos.x = self.radius; self.vel.x *= -1
        if self.pos.x > SCREEN_W - self.radius:
            self.pos.x = SCREEN_W - self.radius; self.vel.x *= -1
        if self.pos.y < self.radius:
            self.pos.y = self.radius; self.vel.y *= -1
        if self.pos.y > SCREEN_H - self.radius:
            self.pos.y = SCREEN_H - self.radius; self.vel.y *= -1

    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.pos.x), int(self.pos.y)), self.radius)
        hpw = int(28 * (self.hp / self.max_hp))
        pygame.draw.rect(surf, (60,60,60), (self.pos.x-14, self.pos.y-22, 28, 6))
        pygame.draw.rect(surf, (100,220,100), (self.pos.x-14, self.pos.y-22, hpw, 6))

    def take_damage(self, d):
        self.hp -= d

class Shooter(Enemy):
    def __init__(self,pos):
        super().__init__(pos, hp=44, speed=78, color=(220,140,100), score_reward=30, xp_reward=16)
        self.fire_cd = 0
        self.fire_rate = 1.0

    def update(self, dt, player):
        to_player = player.pos - self.pos
        dist = to_player.length()
        if dist < 180:
            perp = to_player.rotate(90).normalize()
            self.vel = perp * self.speed
        else:
            if dist > 260:
                self.vel = to_player.normalize() * self.speed
            else:
                self.vel *= 0.95
        self.pos += self.vel * dt
        self.fire_cd -= dt

    def try_shoot(self, bullets, player):
        if self.fire_cd <= 0:
            dirv = (player.pos - self.pos)
            if dirv.length_squared() > 0.01:
                dirv = dirv.normalize()
                bullets.append(Bullet(self.pos + dirv*22, dirv*260, 8, "enemy"))
                self.fire_cd = 1.0 / self.fire_rate

class Dasher(Enemy):
    def __init__(self,pos):
        super().__init__(pos, hp=28, speed=160, color=(220,80,150), score_reward=35, xp_reward=18)
        self.charge_cd = random.uniform(1.0,3.0)
        self.dashing = False
        self.dash_time = 0.0

    def update(self, dt, player):
        self.charge_cd -= dt
        if self.dashing:
            self.pos += self.vel * dt * 2.2
            self.dash_time -= dt
            if self.dash_time <= 0:
                self.dashing = False
        else:
            # move slowly to player
            dirv = (player.pos - self.pos)
            if dirv.length_squared() > 0.01:
                self.vel = dirv.normalize() * (self.speed * 0.45)
            self.pos += self.vel * dt
            if self.charge_cd <= 0:
                # dash
                dirv = (player.pos - self.pos)
                if dirv.length_squared() > 0.01:
                    self.vel = dirv.normalize() * self.speed
                    self.dashing = True
                    self.dash_time = 0.6
                    self.charge_cd = random.uniform(2.0,4.0)
        # clamp & bounce
        if self.pos.x < self.radius:
            self.pos.x = self.radius; self.vel.x *= -1
        if self.pos.x > SCREEN_W - self.radius:
            self.pos.x = SCREEN_W - self.radius; self.vel.x *= -1
        if self.pos.y < self.radius:
            self.pos.y = self.radius; self.vel.y *= -1
        if self.pos.y > SCREEN_H - self.radius:
            self.pos.y = SCREEN_H - self.radius; self.vel.y *= -1

class Tank(Enemy):
    def __init__(self,pos):
        super().__init__(pos, hp=170, speed=36, color=(120,80,200), score_reward=60, xp_reward=36)
        self.radius = 28

class Orbiter(Enemy):
    def __init__(self,pos, center=None):
        # orbits near player; center will be updated each frame
        super().__init__(pos, hp=36, speed=100, color=(120,200,220), score_reward=42, xp_reward=22)
        self.orbit_radius = random.uniform(90,160)
        self.angle = random.uniform(0,360)
        self.center = center  # usually player
        self.orbit_speed = random.uniform(40,80)

    def update(self, dt, player):
        self.center = player.pos
        self.angle += self.orbit_speed * dt
        rad = math.radians(self.angle)
        self.pos = self.center + vec(math.cos(rad), math.sin(rad)) * self.orbit_radius

class Splitter(Enemy):
    def __init__(self,pos):
        super().__init__(pos, hp=60, speed=120, color=(220,200,80), score_reward=48, xp_reward=26)
        self.split_on_death = True

# Boss class
class Boss:
    def __init__(self, kind, pos, hp, speed):
        self.kind = kind
        self.pos = vec(pos)
        self.hp = hp
        self.max_hp = hp
        self.speed = speed
        self.radius = 60
        self.timer = 0.0
        self.fire_cd = 0.0

    def update(self, dt, player, bullets, enemies):
        self.timer += dt
        dirp = player.pos - self.pos
        if self.kind == "Juggernaut":
            # slow approach + radial shots
            if dirp.length() > 60:
                self.pos += dirp.normalize() * (self.speed*0.5) * dt
            self.fire_cd -= dt
            if self.fire_cd <= 0:
                self.fire_cd = 2.6
                for i in range(16):
                    ang = math.radians(i*22.5)
                    dv = vec(math.cos(ang), math.sin(ang))
                    bullets.append(Bullet(self.pos + dv*40, dv*180, 12, "enemy"))
        elif self.kind == "Sentinel":
            # ranged targeted shooter
            if dirp.length() > 240:
                self.pos += dirp.normalize() * self.speed * dt
            self.fire_cd -= dt
            if self.fire_cd <= 0:
                self.fire_cd = 1.0
                dv = (player.pos - self.pos).normalize()
                bullets.append(Bullet(self.pos + dv*40, dv*320, 18, "enemy"))
        elif self.kind == "HiveQueen":
            # spawns minions occasionally
            if dirp.length() > 120:
                self.pos += dirp.normalize() * (self.speed*0.4) * dt
            self.fire_cd -= dt
            if self.fire_cd <= 0:
                self.fire_cd = 3.0
                for _ in range(3):
                    spawn = self.pos + vec(random.uniform(-60,60), random.uniform(-60,60))
                    enemies.append(Enemy(spawn, hp=18, speed=120))
        # clamp
        self.pos.x = clamp(self.pos.x, -self.radius, SCREEN_W + self.radius)
        self.pos.y = clamp(self.pos.y, -self.radius, SCREEN_H + self.radius)

    def draw(self, surf):
        color = (200,80,60) if self.kind=="Juggernaut" else ((120,160,220) if self.kind=="Sentinel" else (200,140,220))
        pygame.draw.circle(surf, color, (int(self.pos.x), int(self.pos.y)), self.radius)
        # top center bar
        w = 420
        hpw = int(w * (self.hp/self.max_hp))
        x = SCREEN_W//2 - w//2
        y = 18
        pygame.draw.rect(surf, (30,30,30), (x, y, w, 18))
        pygame.draw.rect(surf, (200,60,60), (x, y, hpw, 18))
        draw_text(surf, f"Boss: {self.kind} — {int(self.hp)}/{int(self.max_hp)} HP", (x+6, y-18), 16)

# ---------------------------
# Spawner & run state
# ---------------------------
class Spawner:
    def __init__(self):
        self.timer = 0.0
        self.spawn_interval = BASE_SPAWN_INTERVAL
        self.elapsed = 0.0
        self.boss_timer = 0.0
        self.post_boss_multiplier = 1.0

    def update(self, dt, enemies, bosses, player_score):
        self.elapsed += dt
        # slightly decrease spawn interval
        self.spawn_interval = max(0.5, BASE_SPAWN_INTERVAL - (self.elapsed / 140.0))
        self.timer -= dt
        if self.timer <= 0 and len(enemies) < ENEMY_CAP:
            self.timer = self.spawn_interval
            # choose enemy type probabilistically, shifting with time
            t = random.random()
            # weights change over time
            p_chaser = 0.45
            p_shooter = 0.20 + min(0.25, self.elapsed/600.0)
            p_dasher = 0.12 + min(0.18, self.elapsed/500.0)
            p_tank = 0.08 + min(0.12, self.elapsed/700.0)
            p_orbiter = 0.10
            p_split = 0.05
            side = random.choice(['top','bottom','left','right'])
            if side == 'top':
                spawn = vec(random.uniform(0,SCREEN_W), -20)
            elif side == 'bottom':
                spawn = vec(random.uniform(0,SCREEN_W), SCREEN_H+20)
            elif side == 'left':
                spawn = vec(-20, random.uniform(0,SCREEN_H))
            else:
                spawn = vec(SCREEN_W+20, random.uniform(0,SCREEN_H))
            r = random.random()
            if r < p_chaser:
                enemies.append(Enemy(spawn, hp=int(20 * self.post_boss_multiplier + self.elapsed/20), speed=100 + self.elapsed/120))
            elif r < p_chaser + p_shooter:
                enemies.append(Shooter(spawn))
            elif r < p_chaser + p_shooter + p_dasher:
                enemies.append(Dasher(spawn))
            elif r < p_chaser + p_shooter + p_dasher + p_tank:
                enemies.append(Tank(spawn))
            elif r < p_chaser + p_shooter + p_dasher + p_tank + p_orbiter:
                enemies.append(Orbiter(player.pos if 'player' in globals() else vec(SCREEN_W/2, SCREEN_H/2)))
            else:
                enemies.append(Splitter(spawn))
        # boss spawn
        self.boss_timer += dt
        if self.boss_timer >= BOSS_INTERVAL:
            self.boss_timer = 0.0
            kind = random.choice(["Juggernaut","Sentinel","HiveQueen"])
            side = random.choice(['top','bottom','left','right'])
            if side == 'top': pos = vec(random.uniform(200,SCREEN_W-200), -120)
            elif side == 'bottom': pos = vec(random.uniform(200,SCREEN_W-200), SCREEN_H + 120)
            elif side == 'left': pos = vec(-120, random.uniform(200,SCREEN_H-200))
            else: pos = vec(SCREEN_W + 120, random.uniform(200,SCREEN_H-200))
            hp = int((1200 + self.elapsed*18) * self.post_boss_multiplier)
            spd = 40 if kind=="Juggernaut" else 80 if kind=="Sentinel" else 36
            return Boss(kind, pos, hp, spd)
        return None

# ---------------------------
# UI / Tree drawing helpers
# ---------------------------
def draw_tree(surf, nodes, conns, mouse_pos, currency, currency_symbol="$", purchased_levels=None, max_level_key="max_level"):
    # draw connections first
    for a,b in conns:
        ax,ay = nodes[a]["pos"]; bx,by = nodes[b]["pos"]
        pygame.draw.line(surf, (80,80,80), (ax,ay), (bx,by), 4)
    hover = None
    for uid, info in nodes.items():
        x,y = info["pos"]
        lvl = purchased_levels.get(uid, 0) if purchased_levels is not None else 0
        maxl = info.get(max_level_key, 1)
        rect = pygame.Rect(x-34,y-34,68,68)
        # determine purchasable: check prereqs
        purchasable = False
        if lvl < maxl:
            ok = True
            for pid,minl in info.get("prereqs",[]):
                if purchased_levels.get(pid,0) < minl:
                    ok = False; break
            if ok:
                cost = (info.get("base_cost") * (1.9 ** lvl)) if "base_cost" in info else info.get("cost")
                if currency >= int(cost):
                    purchasable = True
        # color
        if lvl > 0:
            col = (120,220,140)
        elif purchasable:
            col = (220,220,120)
        else:
            col = (160,160,160)
        pygame.draw.circle(surf, col, (x,y), 30)
        pygame.draw.circle(surf, (40,40,40), (x,y), 30, 2)
        draw_text(surf, f"{info['name']}", (x-54,y-54), 14)
        draw_text(surf, f"{lvl}/{maxl}", (x-8,y-8), 14)
        if rect.collidepoint(mouse_pos):
            hover = uid
            pygame.draw.circle(surf, (255,255,255), (x,y), 30, 2)
    return hover

# ---------------------------
# Global run state (used to hold per-run skill purchases)
# ---------------------------
RUN_STATE = {
    "run_skills": {},  # skill tree nodes bought this run (id -> level)
}

# ---------------------------
# Main loop & state machine
# ---------------------------
def main():
    global player
    state = "menu"
    menu_idx = 0
    player = Player()
    player.apply_normal_upgrades()
    player.spawn_reset()
    bullets = []
    enemies = []
    bosses = []
    xp_orbs = []
    spawner = Spawner()
    last_time = now_time()
    mouse_held = False
    save_msg_timer = 0.0

    # local purchased maps for display
    normal_levels = save_data.get("normal_upgrades", {})
    core_levels = save_data.get("core_upgrades", {})
    skill_levels = {}  # per-run skills purchased

    while True:
        tnow = now_time()
        dt = min(1/30, tnow - last_time)
        last_time = tnow
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                save_json(SAVE_PATH, save_data)
                pygame.quit(); return
            if ev.type == pygame.KEYDOWN:
                if state == "menu":
                    if ev.key == pygame.K_RETURN:
                        if menu_idx == 0:
                            # start run
                            player = Player()
                            RUN_STATE["run_skills"] = {}
                            player.apply_normal_upgrades()
                            player.spawn_reset()
                            bullets = []; enemies=[]; bosses=[]; xp_orbs=[]
                            spawner = Spawner()
                            state = "game"
                        elif menu_idx == 1:
                            state = "normal_tree"
                        elif menu_idx == 2:
                            state = "core_tree"
                        elif menu_idx == 3:
                            state = "skill_tree"
                        elif menu_idx == 4:
                            state = "prestige_shop"
                        elif menu_idx == 5:
                            save_json(SAVE_PATH, save_data); pygame.quit(); return
                    elif ev.key == pygame.K_UP:
                        menu_idx = max(0, menu_idx - 1)
                    elif ev.key == pygame.K_DOWN:
                        menu_idx = min(5, menu_idx + 1)
                elif state == "game":
                    if ev.key == pygame.K_h and player.homing_unlocked and player.homing_cd <= 0:
                        # homing fires at nearest target (enemy or boss)
                        targets = bosses + enemies
                        if targets:
                            target = min(targets, key=lambda e: (e.pos - player.pos).length_squared())
                            dirv = (target.pos - player.pos).normalize()
                            bullets.append(Bullet(player.pos + dirv*20, dirv*340, int(player.bullet_damage*1.8), "player"))
                            player.homing_cd = 4.0
                    if ev.key == pygame.K_ESCAPE:
                        state = "menu"
                    if ev.key == pygame.K_TAB:
                        # quick open skill tree mid-run
                        state = "skill_tree_inrun"
                elif state in ("normal_tree","core_tree","skill_tree","skill_tree_inrun","prestige_shop"):
                    if ev.key == pygame.K_ESCAPE:
                        state = "menu"
                elif state == "gameover":
                    if ev.key == pygame.K_RETURN:
                        state = "menu"
                    if ev.key == pygame.K_p:
                        if player.score >= PRESTIGE_THRESHOLD:
                            save_data["prestige_points"] = save_data.get("prestige_points",0) + 1
                            save_data["prestige_multiplier"] = save_data.get("prestige_multiplier",1.0) + 0.05
                            save_data["normal_upgrades"] = {}
                            save_json(SAVE_PATH, save_data)
                            state = "menu"

            if ev.type == pygame.MOUSEBUTTONDOWN:
                if ev.button == 1:
                    mouse_held = True
                    mx,my = ev.pos
                    if state == "normal_tree":
                        # attempt to buy normal upgrade node by clicking node
                        hover = draw_tree(screen, NORMAL_UPGRADES, NORMAL_CONNECTIONS, (mx,my), player.money, "$", save_data.get("normal_upgrades", {}), "max_level")
                        # but we can't reliably get hover without re-drawing; instead iterate nodes
                        for uid, info in NORMAL_UPGRADES.items():
                            x,y = info["pos"]; rect = pygame.Rect(x-34,y-34,68,68)
                            if rect.collidepoint((mx,my)):
                                cur = save_data.get("normal_upgrades", {}).get(uid, 0)
                                if cur < info["max_level"]:
                                    # check prereqs
                                    ok = True
                                    for pid, minl in info["prereqs"]:
                                        if save_data.get("normal_upgrades", {}).get(pid, 0) < minl:
                                            ok = False; break
                                    cost = int(info["base_cost"] * (1.9 ** cur))
                                    if ok and player.money >= cost:
                                        save_data.setdefault("normal_upgrades", {})[uid] = cur + 1
                                        player.money -= cost
                                        player.apply_normal_upgrades()
                                        save_json(SAVE_PATH, save_data)
                                        save_msg_timer = 1.2
                    elif state == "core_tree":
                        for uid, info in CORE_UPGRADES.items():
                            x,y = info["pos"]; rect = pygame.Rect(x-34,y-34,68,68)
                            if rect.collidepoint((mx,my)):
                                cur = save_data.get("core_upgrades", {}).get(uid, 0)
                                if cur < info["max_level"]:
                                    # check prereqs
                                    ok = True
                                    for pid,minl in info.get("prereqs",[]):
                                        if save_data.get("core_upgrades",{}).get(pid,0) < minl:
                                            ok = False; break
                                    cost = info["cost"]
                                    if ok and save_data.get("core_shards",0) >= cost:
                                        save_data.setdefault("core_upgrades", {})[uid] = cur + 1
                                        save_data["core_shards"] -= cost
                                        player.apply_persistent_bonuses()
                                        player.apply_normal_upgrades()
                                        save_json(SAVE_PATH, save_data)
                                        save_msg_timer = 1.2
                    elif state == "skill_tree":
                        # buying persistent skill tree? We said skill tree is per-run, so ignore here
                        pass
                    elif state == "skill_tree_inrun":
                        # buy skill nodes with skill points
                        for uid, info in SKILL_TREE.items():
                            x,y = info["pos"]; rect = pygame.Rect(x-34,y-34,68,68)
                            if rect.collidepoint((mx,my)):
                                cur = RUN_STATE["run_skills"].get(uid, 0)
                                if cur < info["max_level"]:
                                    # prereqs
                                    ok = True
                                    for pid,minl in info["prereqs"]:
                                        if RUN_STATE["run_skills"].get(pid, 0) < minl:
                                            ok = False; break
                                    if ok and player.skill_points >= info["cost"]:
                                        RUN_STATE["run_skills"][uid] = cur + 1
                                        player.skill_points -= info["cost"]
                                        save_msg_timer = 1.2
                    elif state == "prestige_shop":
                        # buy prestige shop permanent perks
                        for i,(pid,(name,cost,desc)) in enumerate(PRESTIGE_SHOP.items()):
                            rx = 60; ry = 120 + i*70; rect = pygame.Rect(rx, ry, 760, 56)
                            if rect.collidepoint((mx,my)):
                                if save_data.get("prestige_points",0) >= cost and pid not in save_data.get("prestige_shop",{}):
                                    save_data.setdefault("prestige_shop", {})[pid] = True
                                    save_data["prestige_points"] -= cost
                                    save_json(SAVE_PATH, save_data)
                                    player.apply_persistent_bonuses()
                                    save_msg_timer = 1.2
                    elif state == "gameover":
                        # prestige button area
                        if player.score >= PRESTIGE_THRESHOLD:
                            px = SCREEN_W//2 - 120; py = 300
                            if px <= mx <= px+240 and py <= my <= py+36:
                                save_data["prestige_points"] = save_data.get("prestige_points",0) + 1
                                save_data["prestige_multiplier"] = save_data.get("prestige_multiplier",1.0) + 0.05
                                save_data["normal_upgrades"] = {}
                                save_json(SAVE_PATH, save_data)
                                state = "menu"
            if ev.type == pygame.MOUSEBUTTONUP:
                if ev.button == 1:
                    mouse_held = False

        keys = pygame.key.get_pressed()

        # -------------------------
        # Menu
        # -------------------------
        if state == "menu":
            screen.fill((10,12,22))
            draw_text(screen, "AstroRogue", (SCREEN_W//2 - 120, 36), 36)
            opts = ["Play","Normal Upgrades","Core Upgrades","Skill Tree (mid-run)","Prestige Shop","Quit"]
            for i,o in enumerate(opts):
                col = (255,255,150) if i==menu_idx else (220,220,220)
                draw_text(screen, o, (SCREEN_W//2 - 220, 140 + i*60), 26, col)
            draw_text(screen, f"Best Score: {save_data.get('best_score',0)}", (20, SCREEN_H-40))
            draw_text(screen, f"Core Shards: {save_data.get('core_shards',0)}", (20, SCREEN_H-20))
            pygame.display.flip()
            clock.tick(FPS)
            continue

        # -------------------------
        # Normal upgrade tree screen
        # -------------------------
        if state == "normal_tree":
            screen.fill((8,10,14))
            draw_text(screen, "Normal Upgrade Tree (money). Click nodes to level. Esc to return.", (20,18), 18)
            mx,my = pygame.mouse.get_pos()
            hover = draw_tree(screen, NORMAL_UPGRADES, NORMAL_CONNECTIONS, (mx,my), player.money, "$", save_data.get("normal_upgrades", {}), "max_level")
            # tooltip
            if hover:
                info = NORMAL_UPGRADES[hover]
                lvl = save_data.get("normal_upgrades", {}).get(hover, 0)
                if lvl < info["max_level"]:
                    cost = int(info["base_cost"] * (1.9**lvl))
                else:
                    cost = None
                draw_text(screen, f"{info['name']} - {info['desc']}", (20, SCREEN_H-120), 16)
                draw_text(screen, f"Level: {lvl}/{info['max_level']}", (20, SCREEN_H-96), 14)
                if cost:
                    draw_text(screen, f"Cost: {cost}", (20, SCREEN_H-72), 14)
                else:
                    draw_text(screen, "Max level", (20, SCREEN_H-72), 14)
            if save_msg_timer > 0:
                draw_text(screen, "Saved!", (SCREEN_W-120, 20), 18, (120,220,120))
            pygame.display.flip()
            save_msg_timer = max(0, save_msg_timer - dt)
            clock.tick(FPS)
            continue

        # -------------------------
        # Core upgrades tree (persistent)
        # -------------------------
        if state == "core_tree":
            screen.fill((6,12,18))
            draw_text(screen, "Core Upgrade Tree (Core Shards). Click to buy persistent upgrades. Esc to return.", (20,18), 18)
            mx,my = pygame.mouse.get_pos()
            hover = draw_tree(screen, CORE_UPGRADES, CORE_CONNS, (mx,my), save_data.get("core_shards",0), "Shards", save_data.get("core_upgrades", {}), "max_level")
            if hover:
                info = CORE_UPGRADES[hover]
                lvl = save_data.get("core_upgrades", {}).get(hover, 0)
                draw_text(screen, f"{info['name']} - {info['desc']}", (20, SCREEN_H-120), 16)
                draw_text(screen, f"Bought: {lvl}/{info['max_level']}", (20, SCREEN_H-96), 14)
                draw_text(screen, f"Cost: {info['cost']} shards", (20, SCREEN_H-72), 14)
            if save_msg_timer > 0:
                draw_text(screen, "Saved!", (SCREEN_W-120, 20), 18, (120,220,120))
            pygame.display.flip()
            save_msg_timer = max(0, save_msg_timer - dt)
            clock.tick(FPS)
            continue

        # -------------------------
        # Skill tree (mid-run)
        # -------------------------
        if state == "skill_tree_inrun":
            screen.fill((12,10,20))
            draw_text(screen, "Skill Tree (use skill points earned by leveling). Click to buy. Esc to return.", (20,18), 18)
            mx,my = pygame.mouse.get_pos()
            hover = draw_tree(screen, SKILL_TREE, SKILL_CONN, (mx,my), player.skill_points, "SP", RUN_STATE.get("run_skills", {}), "max_level")
            if hover:
                info = SKILL_TREE[hover]
                lvl = RUN_STATE.get("run_skills", {}).get(hover, 0)
                draw_text(screen, f"{info['name']} - {info['desc']}", (20, SCREEN_H-120), 16)
                draw_text(screen, f"Level: {lvl}/{info['max_level']}", (20, SCREEN_H-96), 14)
                draw_text(screen, f"Cost: {info['cost']} skill pts", (20, SCREEN_H-72), 14)
            if save_msg_timer > 0:
                draw_text(screen, "Purchased", (SCREEN_W-120, 20), 18, (120,220,120))
            pygame.display.flip()
            save_msg_timer = max(0, save_msg_timer - dt)
            clock.tick(FPS)
            continue

        # -------------------------
        # Prestige shop
        # -------------------------
        if state == "prestige_shop":
            screen.fill((8,6,12))
            draw_text(screen, "Prestige Shop - spend prestige points on permanent perks. Esc to return.", (20,18), 18)
            for i,(pid,(name,cost,desc)) in enumerate(PRESTIGE_SHOP.items()):
                rx = 60; ry = 120 + i*70
                rect = pygame.Rect(rx, ry, 760, 56)
                owned = pid in save_data.get("prestige_shop", {})
                pygame.draw.rect(screen, (60,60,60), rect)
                color = (60,200,170) if owned else (220,220,220)
                draw_text(screen, f"{name} (cost {cost}) - {'OWNED' if owned else 'BUY'}", (rx+8, ry+6), 18, color)
                draw_text(screen, desc, (rx+8, ry+30), 14, (180,180,180))
            draw_text(screen, f"Prestige pts: {save_data.get('prestige_points',0)}", (20, SCREEN_H-40))
            if save_msg_timer > 0:
                draw_text(screen, "Saved!", (SCREEN_W-120, 20), 18, (120,220,120))
            pygame.display.flip()
            save_msg_timer = max(0, save_msg_timer - dt)
            clock.tick(FPS)
            continue

        # -------------------------
        # In-game
        # -------------------------
        if state == "game":
            player.update(dt, keys)
            player.aim_at_mouse()
            # shooting
            if mouse_held and player.can_shoot(tnow):
                new_bullets = player.shoot(tnow)
                bullets.extend(new_bullets)
            # homing cooldown
            player.homing_cd = max(0, player.homing_cd - dt)
            # update bullets
            for b in bullets[:]:
                b.update(dt)
                if b.life <= 0:
                    bullets.remove(b)
            # spawn
            new_boss = spawner.update(dt, enemies, bosses, player.score)
            if new_boss:
                bosses.append(new_boss)
            # update enemies
            for e in enemies[:]:
                e.update(dt, player)
                if isinstance(e, Shooter):
                    e.try_shoot(bullets, player)
                # collisions with player
                if (e.pos - player.pos).length_squared() < (e.radius + player.radius)**2:
                    player.take_damage(18)
                    e.take_damage(999)
                if e.hp <= 0:
                    # on death, release xp orb(s) and rewards
                    reward_money = int((15 + random.randint(4,18)) * player.money_mult * player.prestige_multiplier)
                    player.money += reward_money
                    player.score += reward_money
                    # drop xp orbs
                    xp_amount = max(8, int((e.xp_reward)))
                    xp_orbs.append(XPOrb(e.pos, xp_amount))
                    # splitter spawn behavior
                    if isinstance(e, Splitter):
                        # spawn two small chasers
                        for _ in range(2):
                            enemies.append(Enemy(e.pos + vec(random.uniform(-12,12), random.uniform(-12,12)), hp=12, speed=140))
                    enemies.remove(e)
            # update bosses
            for b in bosses[:]:
                b.update(dt, player, bullets, enemies)
                # boss collision with player
                if (b.pos - player.pos).length_squared() < (b.radius + player.radius)**2:
                    player.take_damage(40)
                if b.hp <= 0:
                    # reward shards and money/score
                    shards = 3 if b.kind=="Sentinel" else (4 if b.kind=="Juggernaut" else 3)
                    shards += int(spawner.elapsed / 140.0)
                    save_data["core_shards"] = save_data.get("core_shards",0) + shards
                    player.money += int(600 * player.prestige_multiplier)
                    player.score += int(600 * player.prestige_multiplier)
                    spawner.post_boss_multiplier *= 1.08  # make enemies slightly stronger after each boss
                    bosses.remove(b)
                    save_json(SAVE_PATH, save_data)
            # bullets collide with enemies and bosses
            for b in bullets[:]:
                if b.owner == "player":
                    hit = False
                    for bo in bosses:
                        if (bo.pos - b.pos).length_squared() < (bo.radius + b.radius)**2:
                            bo.hp -= b.dmg
                            hit = True
                            if b.explode:
                                # small AoE damage
                                for e in enemies:
                                    if (e.pos - b.pos).length_squared() < (40*40):
                                        e.take_damage(int(b.dmg*0.5))
                            if b.pierce > 0:
                                b.pierce -= 1
                            else:
                                bullets.remove(b)
                            break
                    if hit: continue
                    for e in enemies[:]:
                        if (e.pos - b.pos).length_squared() < (e.radius + b.radius)**2:
                            e.take_damage(b.dmg)
                            hit = True
                            if b.explode:
                                for e2 in enemies:
                                    if (e2.pos - b.pos).length_squared() < (36*36):
                                        e2.take_damage(int(b.dmg*0.5))
                            if b.pierce > 0:
                                b.pierce -= 1
                            else:
                                if b in bullets: bullets.remove(b)
                            break
                else:
                    # enemy bullet hits player
                    if (player.pos - b.pos).length_squared() < (player.radius + b.radius)**2:
                        player.take_damage(b.dmg)
                        if b in bullets: bullets.remove(b)
            # update xp orbs
            for orb in xp_orbs[:]:
                orb.update(dt, player)
                if orb.collected or orb.life <= 0:
                    xp_orbs.remove(orb)
            # check player death
            if not player.alive:
                if player.score > save_data.get("best_score",0):
                    save_data["best_score"] = player.score
                save_json(SAVE_PATH, save_data)
                state = "gameover"
            # draw
            screen.fill((6,10,18))
            # draw bosses first (they draw their own top bar)
            for bo in bosses:
                bo.draw(screen)
            for e in enemies:
                e.draw(screen)
            for b in bullets:
                b.draw(screen)
            for orb in xp_orbs:
                orb.draw(screen)
            player.draw(screen)
            # contextual hints
            draw_text(screen, "Hold LMB to shoot. H = homing (if unlocked). TAB = Skill Tree (mid-run). Esc = Menu", (SCREEN_W-700, SCREEN_H-40), 14)
            pygame.display.flip()
            clock.tick(FPS)
            continue

        # -------------------------
        # Game Over
        # -------------------------
        if state == "gameover":
            screen.fill((18,6,8))
            draw_text(screen, "GAME OVER", (SCREEN_W//2 - 110, 80), 48, (240,80,80))
            draw_text(screen, f"Score: {player.score}", (SCREEN_W//2 - 90, 160), 28)
            draw_text(screen, "Press Enter to return to Menu.", (SCREEN_W//2 - 170, 220), 18)
            if player.score >= PRESTIGE_THRESHOLD:
                draw_text(screen, f"You are eligible to Prestige! Press P or click the button to gain 1 prestige point.", (SCREEN_W//2 - 300, 260), 16, (200,240,160))
                # clickable button
                px = SCREEN_W//2 - 120; py = 300
                pygame.draw.rect(screen, (120,200,120), (px,py,240,36))
                draw_text(screen, "Prestige (Reset normal upgrades, gain 1 prestige pt)", (px+10, py+6), 14, (8,8,8))
            pygame.display.flip()
            clock.tick(FPS)
            continue

# run
if __name__ == "__main__":
    main()
