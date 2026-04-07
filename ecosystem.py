#!/usr/bin/env python3
"""
🌿 Ecosystem Simulator – Huge World Edition
Pan: drag mouse | Zoom: scroll wheel | Speed: slider bottom‑right
"""

import pygame
import random
import math
import sys
from enum import Enum
from typing import List, Optional, Tuple

# ────────────────────────────────────────────────────────────────────────────────
#  CONSTANTS & CONFIG
# ────────────────────────────────────────────────────────────────────────────────
DEFAULT_W, DEFAULT_H = 1200, 800
PANEL_W = 260
FPS = 60

# World size – 10× original (11400 × 9000)
WORLD_W = 11400
WORLD_H = 9000

# Zoom limits
ZOOM_MIN = 0.2
ZOOM_MAX = 2.0

# Balanced drain rates
DRAIN_MULTIPLIER = 1.2

# Camera pan speed (pixels per second in world coords)
CAM_PAN_SPEED = 600

# ────────────────────────────────────────────────────────────────────────────────
#  COLORS
# ────────────────────────────────────────────────────────────────────────────────
BG           = (28, 48, 20)
WATER_DEEP   = (30,  80, 175)
WATER_LIGHT  = (55, 130, 225)
PANEL_BG     = (14, 20,  10)
PANEL_LINE   = (50, 80,  35)
WHITE        = (255,255,255)
BLACK        = (0,  0,    0)
GREY         = (110,110,110)
GREY_DARK    = (55,  55,  55)

C_HUNGER  = (225, 110,  25)
C_THIRST  = ( 35, 125, 230)
C_STAMINA = ( 45, 200,  85)
C_SLEEP   = (160,  95, 225)
C_HEALTH  = (220,  40,  40)
C_BAR_BG  = ( 38,  38,  38)

C_GRASS      = ( 82, 165,  50)
C_GRASS_D    = ( 50, 115,  32)
C_FLOWER_P   = (230,  75, 190)
C_FLOWER_Y   = (245, 205,  30)
C_FLOWER_B   = ( 95, 175, 245)
C_FLOWER_S   = ( 60, 138,  42)
C_TREE_T     = (108,  68,  28)
C_TREE_L     = ( 32,  90,  28)
C_TREE_L2    = ( 48, 118,  38)
C_BERRY      = (195,  32,  32)
C_BUSH       = ( 52,  98,  44)
C_MUSH_CAP   = (185, 155,  72)
C_MUSH_GLOW  = (155, 228, 112)
C_MUSH_SPOT  = (240, 240, 200)
C_SEED       = (162, 128,  58)
C_SPORE      = (188, 240, 135)
C_FIRE       = (255, 100,  20)

ANIMAL_COLORS = {
    'bee'       : (242, 202,  18),
    'rabbit'    : (198, 188, 172),
    'pig'       : (232, 158, 152),
    'deer'      : (172, 128,  72),
    'alligator' : ( 58, 128,  62),
    'tiger'     : (222, 138,  38),
    'wolf'      : (128, 128, 140),
    'fox'       : (212, 108,  38),
    'bear'      : (118,  82,  52),
    'bird'      : ( 88, 158, 222),
}

# ────────────────────────────────────────────────────────────────────────────────
#  ENUMS & HELPERS
# ────────────────────────────────────────────────────────────────────────────────
class State(Enum):
    WANDER     = 0
    SEEK_FOOD  = 1
    SEEK_WATER = 2
    EAT        = 3
    DRINK      = 4
    SLEEP      = 5
    HUNT       = 6
    FLEE       = 7
    REST       = 8
    POLLINATE  = 9

def dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def nearest_point_on_rect(px, py, rect):
    cx = clamp(px, rect.left, rect.right)
    cy = clamp(py, rect.top, rect.bottom)
    if rect.collidepoint(px, py):
        dl = px - rect.left
        dr = rect.right - px
        dt = py - rect.top
        db = rect.bottom - py
        m = min(dl, dr, dt, db)
        if m == dl:   cx = rect.left
        elif m == dr: cx = rect.right
        elif m == dt: cy = rect.top
        else:         cy = rect.bottom
    return (cx, cy)

def in_water(pos, water_zones) -> bool:
    """Check if a position is inside any water zone (river segments)."""
    px, py = int(pos[0]), int(pos[1])
    for r in water_zones:
        if r.collidepoint(px, py):
            return True
    return False

def generate_river_points(world_w, world_h, seed=42):
    """Generate a list of control points for a natural curvy river."""
    rng = random.Random(seed)
    points = []
    # River flows roughly from top-left to bottom-right with curves
    num_points = 14
    for i in range(num_points):
        t = i / (num_points - 1)
        # Base diagonal path
        bx = t * world_w * 0.9 + world_w * 0.05
        by = t * world_h * 0.85 + world_h * 0.08
        # Add natural curves
        offset_x = rng.uniform(-world_w * 0.12, world_w * 0.12)
        offset_y = rng.uniform(-world_h * 0.08, world_h * 0.08)
        # Dampen offsets near edges
        edge_factor = min(t, 1 - t) * 4
        edge_factor = min(1.0, edge_factor)
        bx += offset_x * edge_factor
        by += offset_y * edge_factor
        bx = clamp(bx, 40, world_w - 40)
        by = clamp(by, 40, world_h - 40)
        points.append((bx, by))
    return points

def interpolate_river(points, segments_per_span=20):
    """Catmull-Rom spline interpolation for smooth river path."""
    result = []
    n = len(points)
    for i in range(n - 1):
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[min(n - 1, i + 1)]
        p3 = points[min(n - 1, i + 2)]
        for j in range(segments_per_span):
            t = j / segments_per_span
            t2 = t * t
            t3 = t2 * t
            x = 0.5 * ((2 * p1[0]) +
                       (-p0[0] + p2[0]) * t +
                       (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                       (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) +
                       (-p0[1] + p2[1]) * t +
                       (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                       (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            result.append((x, y))
    result.append(points[-1])
    return result

def build_river_rects(river_path, base_width=90):
    """Build a list of small rects along the river path for collision."""
    rects = []
    rng = random.Random(123)
    for i, (x, y) in enumerate(river_path):
        # Vary width for natural look
        w = base_width + rng.uniform(-25, 30)
        half = w / 2
        rects.append(pygame.Rect(int(x - half), int(y - half * 0.6), int(w), int(w * 0.6)))
    return rects

def generate_branch_points(main_path, world_w, world_h, seed=77):
    """Generate tributary branches that split off from the main river."""
    rng = random.Random(seed)
    branches = []
    # Pick 4-5 points along the main river to branch from
    branch_indices = sorted(rng.sample(range(20, len(main_path) - 20, 3), min(5, len(main_path) // 50)))
    for idx in branch_indices:
        start_x, start_y = main_path[idx]
        # Branch goes in a perpendicular-ish direction
        if idx + 1 < len(main_path):
            dx = main_path[idx+1][0] - main_path[idx][0]
            dy = main_path[idx+1][1] - main_path[idx][1]
        else:
            dx, dy = 1, 0
        # Perpendicular direction (randomly left or right)
        side = rng.choice([-1, 1])
        perp_x, perp_y = -dy * side, dx * side
        mag = math.hypot(perp_x, perp_y)
        if mag > 0:
            perp_x /= mag
            perp_y /= mag
        # Generate 6-8 control points for the branch
        num_pts = rng.randint(6, 8)
        pts = [(start_x, start_y)]
        for j in range(1, num_pts):
            t = j / (num_pts - 1)
            # Branch curves away from main river
            bx = start_x + perp_x * t * rng.uniform(400, 900)
            by = start_y + perp_y * t * rng.uniform(400, 900)
            # Add some random wandering
            bx += rng.uniform(-120, 120)
            by += rng.uniform(-120, 120)
            bx = clamp(bx, 40, world_w - 40)
            by = clamp(by, 40, world_h - 40)
            pts.append((bx, by))
        branch_path = interpolate_river(pts, segments_per_span=12)
        branches.append(branch_path)
    return branches

def build_branch_rects(branch_paths, base_width=35):
    """Build collision rects for branch rivers (thinner than main)."""
    all_rects = []
    rng = random.Random(456)
    for path in branch_paths:
        for i, (x, y) in enumerate(path):
            t = i / max(1, len(path) - 1)
            # Branches taper toward the end
            w = base_width * (1.0 - t * 0.6) + rng.uniform(-8, 8)
            w = max(10, w)
            half = w / 2
            all_rects.append(pygame.Rect(int(x - half), int(y - half * 0.6), int(w), int(w * 0.6)))
    return all_rects

def rand_land(water_zones, sim_w, sim_h):
    for _ in range(500):
        x = random.randint(12, sim_w - 12)
        y = random.randint(12, sim_h - 12)
        if not in_water([x, y], water_zones):
            return float(x), float(y)
    return float(sim_w // 2), float(sim_h // 2)

# ────────────────────────────────────────────────────────────────────────────────
#  CAMERA (for huge world)
# ────────────────────────────────────────────────────────────────────────────────
class Camera:
    def __init__(self, world_w, world_h, view_w, view_h):
        self.world_w = world_w
        self.world_h = world_h
        self.view_w = view_w
        self.view_h = view_h
        self.x = world_w // 2
        self.y = world_h // 2
        self.zoom = 1.0
        self.dragging = False
        self.drag_start = (0, 0)
        self.drag_cam_start = (0, 0)

    def world_to_screen(self, wx, wy):
        """Convert world coordinates to screen coordinates."""
        sx = (wx - self.x) * self.zoom + self.view_w // 2
        sy = (wy - self.y) * self.zoom + self.view_h // 2
        return (int(sx), int(sy))

    def screen_to_world(self, sx, sy):
        """Convert screen coordinates to world coordinates."""
        wx = (sx - self.view_w // 2) / self.zoom + self.x
        wy = (sy - self.view_h // 2) / self.zoom + self.y
        return (wx, wy)

    def apply(self, pos):
        """Return screen position for a world position tuple/list."""
        return self.world_to_screen(pos[0], pos[1])

    def scale(self, size):
        """Scale a size value by current zoom."""
        return max(1, int(size * self.zoom))

    def update_view_size(self, w, h):
        self.view_w = w
        self.view_h = h

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 2:  # middle button drag
                self.dragging = True
                self.drag_start = event.pos
                self.drag_cam_start = (self.x, self.y)
            elif event.button == 4:  # scroll up
                self.zoom = min(ZOOM_MAX, self.zoom * 1.1)
            elif event.button == 5:  # scroll down
                self.zoom = max(ZOOM_MIN, self.zoom / 1.1)
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 2:
                self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            dx = event.pos[0] - self.drag_start[0]
            dy = event.pos[1] - self.drag_start[1]
            self.x = self.drag_cam_start[0] - dx / self.zoom
            self.y = self.drag_cam_start[1] - dy / self.zoom
            self.x = clamp(self.x, 0, self.world_w)
            self.y = clamp(self.y, 0, self.world_h)

    def update_keys(self, dt, keys, command_input_active=False):
        """Move camera with WASD keys (only when command input is not active)."""
        if command_input_active:
            return
        speed = CAM_PAN_SPEED / self.zoom
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.y -= speed * dt
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.y += speed * dt
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.x -= speed * dt
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.x += speed * dt
        self.x = clamp(self.x, 0, self.world_w)
        self.y = clamp(self.y, 0, self.world_h)

    def is_visible(self, world_rect):
        """Check if a world rectangle (x,y,w,h) is visible on screen."""
        left, top = self.world_to_screen(world_rect[0], world_rect[1])
        right, bottom = self.world_to_screen(world_rect[0]+world_rect[2], world_rect[1]+world_rect[3])
        return (right >= 0 and left <= self.view_w and bottom >= 0 and top <= self.view_h)

# ────────────────────────────────────────────────────────────────────────────────
#  PARTICLES & FIRE (optimised)
# ────────────────────────────────────────────────────────────────────────────────
class Particle:
    __slots__ = ('pos', 'vel', 'color', 'life', 'max_life', 'size', 'alive')
    def __init__(self, x, y, color, speed=2.0, life=1.5, size=3):
        self.pos = [float(x), float(y)]
        angle = random.uniform(0, math.tau)
        s = random.uniform(speed * 0.4, speed)
        self.vel = [math.cos(angle) * s, math.sin(angle) * s]
        self.color = color
        self.life = life
        self.max_life = life
        self.size = size
        self.alive = True

    def update(self, dt, world=None):
        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.vel[0] *= 0.96 ** (dt * 60)  # frame-rate independent
        self.vel[1] *= 0.96 ** (dt * 60)
        self.life -= dt
        if self.life <= 0:
            self.alive = False

    def draw(self, surf, camera):
        alpha = max(0.0, self.life / self.max_life)
        r = max(1, int(self.size * alpha * camera.zoom))
        if r <= 0: return
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        if 0 <= sx <= camera.view_w and 0 <= sy <= camera.view_h:
            pygame.draw.circle(surf, self.color, (sx, sy), r)

class Fire:
    def __init__(self, x, y):
        self.pos = [float(x), float(y)]
        self.radius = 6.0
        self.max_radius = 25.0
        self.life = random.uniform(8.0, 15.0)
        self.age = 0.0
        self.spread_timer = 0.0
        self.alive = True

    def update(self, dt, world):
        self.age += dt
        self.spread_timer -= dt
        self.life -= dt
        if self.life <= 0 or self.radius <= 0:
            self.alive = False
            return

        self.radius = min(self.max_radius, self.radius + dt * 2.5)

        # Destroy plants within radius (only if fire is potentially visible)
        for e in world.entities[:]:
            if isinstance(e, Plant) and e.alive and dist(self.pos, e.pos) < self.radius + 5:
                e.alive = False
                if isinstance(e, Tree) and random.random() < 0.2:
                    world.to_add.append(Fire(e.pos[0], e.pos[1]))

        if self.spread_timer <= 0:
            self.spread_timer = random.uniform(0.5, 2.0)
            angle = random.uniform(0, math.tau)
            r = random.uniform(self.radius * 0.7, self.radius * 1.2)
            nx = self.pos[0] + math.cos(angle) * r
            ny = self.pos[1] + math.sin(angle) * r
            if 5 < nx < world.sim_w - 5 and 5 < ny < world.sim_h - 5:
                if random.random() < 0.2:
                    world.to_add.append(Fire(nx, ny))

        # Damage animals (skip if far from view – optional)
        for a in world.entities:
            if isinstance(a, Animal) and a.alive:
                if dist(self.pos, a.pos) < self.radius + a.size:
                    a.health -= dt * 15
                    if a.health <= 0:
                        a.alive = False

        # Fewer particles
        if random.random() < 0.3 * dt * 60:
            world.to_add.append(Particle(self.pos[0] + random.uniform(-self.radius, self.radius),
                                         self.pos[1] + random.uniform(-self.radius, self.radius),
                                         (255, random.randint(80,160), 20), speed=1.0, life=1.0, size=4))

    def draw(self, surf, camera):
        if not camera.is_visible((self.pos[0]-self.radius, self.pos[1]-self.radius,
                                   self.radius*2, self.radius*2)):
            return
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        r = int(self.radius * camera.zoom)
        for i in range(3):
            c = (255, 140 - i*20, 20)
            pygame.draw.circle(surf, c, (sx, sy), r + i*2)
        pygame.draw.circle(surf, C_FIRE, (sx, sy), r)

# ────────────────────────────────────────────────────────────────────────────────
#  PLANTS (slower spread, scaled for large world)
# ────────────────────────────────────────────────────────────────────────────────
class Plant:
    def __init__(self, x, y):
        self.pos = [float(x), float(y)]
        self.alive = True
        self.age = 0.0
        self.spread_timer = random.uniform(0, 8)

    def update(self, dt, world): pass
    def draw(self, surf, camera): pass

class Grass(Plant):
    MAX = 1200
    INTERVAL = 20.0
    RADIUS = 120

    def update(self, dt, world):
        self.age += dt
        self.spread_timer -= dt
        if self.spread_timer <= 0:
            self.spread_timer = self.INTERVAL + random.uniform(-5, 8)
            if sum(1 for e in world.entities if isinstance(e, Grass)) < self.MAX:
                angle = random.uniform(0, math.tau)
                r = random.uniform(40, self.RADIUS)
                nx = clamp(self.pos[0] + math.cos(angle) * r, 5, world.sim_w - 5)
                ny = clamp(self.pos[1] + math.sin(angle) * r, 5, world.sim_h - 5)
                if not in_water([nx, ny], world.water_zones):
                    if not any(isinstance(e, Grass) and dist(e.pos, [nx, ny]) < 30 for e in world.entities):
                        world.to_add.append(Grass(nx, ny))

    def draw(self, surf, camera):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        r = camera.scale(7)
        pygame.draw.circle(surf, C_GRASS_D, (sx, sy), r)
        pygame.draw.circle(surf, C_GRASS, (sx, sy), max(1, r-2))
        for ox in (-4, 0, 4):
            ex = sx + ox * camera.zoom
            pygame.draw.line(surf, C_GRASS, (ex, sy + 3*camera.zoom), (ex - 1, sy - 7*camera.zoom), max(1, int(2*camera.zoom)))

class Flower(Plant):
    MAX = 300
    INTERVAL = 45.0
    FLOWER_COLORS = [C_FLOWER_P, C_FLOWER_Y, C_FLOWER_B, (240, 120, 80)]

    def __init__(self, x, y):
        super().__init__(x, y)
        self.color = random.choice(self.FLOWER_COLORS)
        self.pollinated = False
        self.spread_timer = random.uniform(30, 50)

    def pollinate(self):
        self.pollinated = True

    def update(self, dt, world):
        self.age += dt
        if self.pollinated:
            self.spread_timer -= dt
            if self.spread_timer <= 0:
                self.pollinated = False
                self.spread_timer = self.INTERVAL + random.uniform(-10, 15)
                if sum(1 for e in world.entities if isinstance(e, Flower)) < self.MAX:
                    angle = random.uniform(0, math.tau)
                    r = random.uniform(60, 180)
                    nx = clamp(self.pos[0] + math.cos(angle) * r, 5, world.sim_w - 5)
                    ny = clamp(self.pos[1] + math.sin(angle) * r, 5, world.sim_h - 5)
                    if not in_water([nx, ny], world.water_zones):
                        world.to_add.append(Flower(nx, ny))

    def draw(self, surf, camera):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        z = camera.zoom
        pygame.draw.line(surf, C_FLOWER_S, (sx, sy + 9*z), (sx, sy - 1*z), max(1, int(2*z)))
        for i in range(5):
            a = i * math.tau / 5
            px = sx + int(math.cos(a) * 5 * z)
            py = sy + int(math.sin(a) * 5 * z)
            pygame.draw.circle(surf, self.color, (px, py), max(1, int(4*z)))
        pygame.draw.circle(surf, (255, 235, 50), (sx, sy), max(1, int(3*z)))

class Tree(Plant):
    MAX = 200
    INTERVAL = 70.0

    def __init__(self, x, y, mature=False):
        super().__init__(x, y)
        self.radius = 30.0 if mature else 10.0
        self.growing = not mature
        self.seed_timer = random.uniform(40, 70)

    def update(self, dt, world):
        self.age += dt
        if self.growing:
            self.radius = min(35.0, 10.0 + self.age * 0.5)
            if self.radius >= 33.0:
                self.growing = False
        self.seed_timer -= dt
        if self.seed_timer <= 0 and not self.growing:
            self.seed_timer = self.INTERVAL + random.uniform(-20, 30)
            if sum(1 for e in world.entities if isinstance(e, Tree)) < self.MAX:
                angle = random.uniform(0, math.tau)
                r = random.uniform(150, 350)
                nx = clamp(self.pos[0] + math.cos(angle) * r, 5, world.sim_w - 5)
                ny = clamp(self.pos[1] + math.sin(angle) * r, 5, world.sim_h - 5)
                if not in_water([nx, ny], world.water_zones):
                    world.to_add.append(Tree(nx, ny, mature=False))
                    for _ in range(3):
                        world.to_add.append(Particle(self.pos[0], self.pos[1], C_SEED, speed=2.0, life=2.5))

    def draw(self, surf, camera):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        z = camera.zoom
        r = max(2, int(self.radius * z))
        # shadow
        shadow = pygame.Surface((r*2, r), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,40), (0,0,r*2,r))
        surf.blit(shadow, (sx - r, sy + r - 2))
        pygame.draw.rect(surf, C_TREE_T, (sx - 3*z, sy, max(1, 6*z), max(1, (self.radius+5)*z)))
        pygame.draw.circle(surf, C_TREE_L, (sx, sy - r//2), r + 3*z)
        pygame.draw.circle(surf, C_TREE_L2, (sx, sy - r//2 - 2*z), r)

class BerryBush(Plant):
    MAX = 200
    MAX_BERRIES = 5
    REGROW_TIME = 25.0

    def __init__(self, x, y):
        super().__init__(x, y)
        self.berries = random.randint(2, self.MAX_BERRIES)
        self.regrow_timer = 0.0

    def eat_berry(self):
        if self.berries > 0:
            self.berries -= 1
            return True
        return False

    def update(self, dt, world):
        self.age += dt
        if self.berries < self.MAX_BERRIES:
            self.regrow_timer -= dt
            if self.regrow_timer <= 0:
                self.berries += 1
                self.regrow_timer = self.REGROW_TIME

    def draw(self, surf, camera):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        z = camera.zoom
        pygame.draw.circle(surf, C_BUSH, (sx, sy), int(10*z))
        pygame.draw.circle(surf, (65,118,52), (sx, sy), int(7*z))
        for i in range(self.berries):
            a = i * math.tau / max(1, self.MAX_BERRIES)
            bx = sx + int(math.cos(a) * 7 * z)
            by = sy + int(math.sin(a) * 7 * z)
            pygame.draw.circle(surf, C_BERRY, (bx, by), max(1, int(3*z)))

class Mushroom(Plant):
    MAX = 180
    INTERVAL = 60.0

    def __init__(self, x, y):
        super().__init__(x, y)
        self.spore_timer = random.uniform(30, 60)
        self.glow_phase = random.uniform(0, math.tau)

    def update(self, dt, world):
        self.age += dt
        self.glow_phase += dt * 1.8
        self.spore_timer -= dt
        if self.spore_timer <= 0:
            self.spore_timer = self.INTERVAL + random.uniform(-15, 25)
            if sum(1 for e in world.entities if isinstance(e, Mushroom)) < self.MAX:
                angle = random.uniform(0, math.tau)
                r = random.uniform(80, 220)
                nx = clamp(self.pos[0] + math.cos(angle) * r, 5, world.sim_w - 5)
                ny = clamp(self.pos[1] + math.sin(angle) * r, 5, world.sim_h - 5)
                if not in_water([nx, ny], world.water_zones):
                    world.to_add.append(Mushroom(nx, ny))
            for _ in range(4):
                world.to_add.append(Particle(self.pos[0], self.pos[1], C_SPORE, speed=1.8, life=3.5, size=4))

    def draw(self, surf, camera):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        z = camera.zoom
        glow = int(abs(math.sin(self.glow_phase)) * 50)
        g_col = (min(255, C_MUSH_GLOW[0]+glow), min(255, C_MUSH_GLOW[1]+glow), min(255, C_MUSH_GLOW[2]+glow))
        pygame.draw.rect(surf, (200,198,175), (sx - 3*z, sy - 1*z, 6*z, 11*z))
        pygame.draw.ellipse(surf, g_col, (sx - 10*z, sy - 13*z, 20*z, 13*z))
        pygame.draw.ellipse(surf, C_MUSH_CAP, (sx - 9*z, sy - 12*z, 18*z, 11*z))
        pygame.draw.circle(surf, C_MUSH_SPOT, (sx - 3*z, sy - 8*z), max(1, int(2*z)))
        pygame.draw.circle(surf, C_MUSH_SPOT, (sx + 3*z, sy - 9*z), max(1, int(2*z)))

# ────────────────────────────────────────────────────────────────────────────────
#  ANIMAL BASE CLASS (scaled speeds, increased drain rates)
# ────────────────────────────────────────────────────────────────────────────────
class Animal:
    MAX = 999

    def __init__(self, kind, x, y, speed, size, diet, color):
        self.kind = kind
        self.pos = [float(x), float(y)]
        self.speed = speed
        self.size = size
        self.diet = diet
        self.color = color
        self.alive = True
        self.age = 0.0
        self.health = 100.0

        self.hunger = random.uniform(60, 100)
        self.thirst = random.uniform(60, 100)
        self.stamina = random.uniform(65, 100)
        self.sleep_v = random.uniform(65, 100)

        # Faster drain
        self.hunger_drain = random.uniform(1.0, 2.0) * DRAIN_MULTIPLIER
        self.thirst_drain = random.uniform(1.4, 2.5) * DRAIN_MULTIPLIER
        self.sleep_drain = random.uniform(0.6, 1.0) * DRAIN_MULTIPLIER
        self.stamina_rate = 2.0 * DRAIN_MULTIPLIER

        self.state = State.WANDER
        self.target = None
        self.vel = [random.uniform(-1, 1), random.uniform(-1, 1)]
        self.wander_timer = 0.0
        self.state_timer = 0.0
        self.attack_cooldown = 0.0
        self.selected = False

    def update(self, dt, world):
        self.age += dt
        self.health = min(100, self.health + dt * 0.5)
        self.hunger -= self.hunger_drain * dt
        self.thirst -= self.thirst_drain * dt
        self.sleep_v -= self.sleep_drain * dt
        self.hunger = max(0, self.hunger)
        self.thirst = max(0, self.thirst)
        self.sleep_v = max(0, self.sleep_v)

        if self.hunger <= 0 or self.thirst <= 0 or self.health <= 0:
            self.alive = False
            for _ in range(4):
                world.to_add.append(Particle(self.pos[0], self.pos[1], (80,80,80), speed=2.0, life=1.2))
            return

        self.attack_cooldown = max(0, self.attack_cooldown - dt)
        self._decide_state()
        self._execute_state(dt, world)
        # Invisible walls
        self.pos[0] = clamp(self.pos[0], 6, world.sim_w - 6)
        self.pos[1] = clamp(self.pos[1], 6, world.sim_h - 6)

    def _decide_state(self):
        if self.sleep_v < 14:
            if self.state != State.SLEEP:
                self.state = State.SLEEP
                self.target = None
        elif self.thirst < 28 and self.state not in (State.DRINK, State.SLEEP, State.FLEE):
            self.state = State.SEEK_WATER
            self.target = None
        elif self.hunger < 28 and self.state not in (State.EAT, State.HUNT, State.SLEEP, State.FLEE):
            self.state = State.HUNT if self.diet == 'carnivore' else State.SEEK_FOOD
            self.target = None
        elif self.stamina < 18 and self.state not in (State.REST, State.SLEEP, State.DRINK, State.EAT, State.HUNT, State.FLEE):
            self.state = State.REST

    def _execute_state(self, dt, world):
        {
            State.SLEEP: self._do_sleep,
            State.SEEK_WATER: self._seek_water,
            State.DRINK: self._do_drink,
            State.SEEK_FOOD: self._seek_food,
            State.EAT: self._do_eat,
            State.HUNT: self._do_hunt,
            State.REST: self._do_rest,
            State.WANDER: self._do_wander,
            State.FLEE: self._do_flee,
        }.get(self.state, self._do_wander)(dt, world)

    def _move_toward(self, target_pos, dt, mult=1.0):
        dx = target_pos[0] - self.pos[0]
        dy = target_pos[1] - self.pos[1]
        d = math.hypot(dx, dy)
        if d > 1:
            spd = self.speed * mult
            self.pos[0] += (dx / d) * spd * dt
            self.pos[1] += (dy / d) * spd * dt
            self.stamina = max(0, self.stamina - self.stamina_rate * mult * dt)
        return d

    def _do_sleep(self, dt, world=None):
        self.sleep_v = min(100, self.sleep_v + 10 * dt)
        self.stamina = min(100, self.stamina + 6 * dt)
        self.health = min(100, self.health + 3 * dt)
        if self.sleep_v >= 92:
            self.state = State.WANDER

    def _do_rest(self, dt, world=None):
        self.stamina = min(100, self.stamina + 12 * dt)
        if self.stamina >= 65:
            self.state = State.WANDER

    def _seek_water(self, dt, world):
        if self.target is None:
            best, bd = None, 1e9
            for wz in world.water_zones:
                edge_pt = nearest_point_on_rect(self.pos[0], self.pos[1], wz)
                d = dist(self.pos, edge_pt)
                if d < bd:
                    bd, best = d, edge_pt
            self.target = best
        if self.target:
            d = self._move_toward(self.target, dt)
            if d < 30:
                self.state = State.DRINK
                self.state_timer = 3.5

    def _do_drink(self, dt, world=None):
        self.thirst = min(100, self.thirst + 22 * dt)
        self.state_timer -= dt
        if self.thirst >= 92 or self.state_timer <= 0:
            self.state = State.WANDER
            self.target = None

    def _seek_food(self, dt, world):
        if self.target is None or not getattr(self.target, 'alive', True):
            self.target = self._find_plant(world)
        if self.target is None:
            self._do_wander(dt, world)
            return
        d = self._move_toward(self.target.pos, dt)
        if d < self.size + 20:
            self.state = State.EAT
            self.state_timer = 2.2

    def _find_plant(self, world):
        cands = []
        for e in world.entities:
            if not (isinstance(e, Plant) and e.alive):
                continue
            if isinstance(e, (Grass, Flower, BerryBush)):
                if isinstance(e, BerryBush) and e.berries == 0:
                    continue
                cands.append(e)
        if not cands:
            return None
        return min(cands, key=lambda e: dist(self.pos, e.pos))

    def _do_eat(self, dt, world):
        self.hunger = min(100, self.hunger + 14 * dt)
        self.health = min(100, self.health + 2 * dt)
        self.state_timer -= dt
        if self.hunger >= 92 or self.state_timer <= 0:
            if self.target and getattr(self.target, 'alive', False):
                if isinstance(self.target, (Grass, Flower)):
                    self.target.alive = False  # Destroy plant
                elif isinstance(self.target, BerryBush):
                    self.target.eat_berry()
                    # Seed dispersal
                    if random.random() < 0.1:
                        nx = clamp(self.pos[0] + random.uniform(-150, 150), 6, world.sim_w-6)
                        ny = clamp(self.pos[1] + random.uniform(-150, 150), 6, world.sim_h-6)
                        if not in_water([nx, ny], world.water_zones) and sum(1 for e in world.entities if isinstance(e, BerryBush)) < BerryBush.MAX:
                            world.to_add.append(BerryBush(nx, ny))
            self.state = State.WANDER
            self.target = None

    # Cycle of life food chain: rabbit < fox < wolf < bear < tiger
    # Each predator hunts those below it in the chain
    PREY_TABLE = {
        'fox': ('rabbit', 'bird', 'bee'),
        'wolf': ('rabbit', 'deer', 'bird', 'fox'),
        'bear': ('deer', 'pig', 'rabbit', 'fox', 'wolf'),
        'tiger': ('deer', 'pig', 'rabbit', 'bird', 'fox', 'wolf'),
        'alligator': ('pig', 'rabbit', 'deer', 'bird', 'fox'),
    }

    def _do_hunt(self, dt, world):
        if self.target is None or not getattr(self.target, 'alive', True):
            prey_kinds = self.PREY_TABLE.get(self.kind, ('rabbit',))
            cands = [e for e in world.entities if isinstance(e, Animal) and e.alive and e.kind in prey_kinds]
            if not cands:
                self.state = State.WANDER
                return
            self.target = min(cands, key=lambda e: dist(self.pos, e.pos))

        d = self._move_toward(self.target.pos, dt, mult=1.25)
        if d < self.size + self.target.size + 15:
            if self.attack_cooldown <= 0:
                self.target.health -= random.uniform(12, 22)
                self.attack_cooldown = 0.8
                world.to_add.append(Particle(self.target.pos[0], self.target.pos[1], (200,25,25), speed=2.0, life=0.5))
            if self.target.health <= 0:
                self.target.alive = False
                self.hunger = min(100, self.hunger + 55)
                self.health = min(100, self.health + 30)
                self.state = State.WANDER
                self.target = None

    def _do_flee(self, dt, world):
        if self.target is None or not getattr(self.target, 'alive', True):
            self.state = State.WANDER
            self.target = None
            return
        d = dist(self.pos, self.target.pos)
        if d > 400:
            self.state = State.WANDER
            self.target = None
            return
        dx = self.pos[0] - self.target.pos[0]
        dy = self.pos[1] - self.target.pos[1]
        if d > 0:
            self.pos[0] += (dx / d) * self.speed * 1.4 * dt
            self.pos[1] += (dy / d) * self.speed * 1.4 * dt
        self.stamina = max(0, self.stamina - self.stamina_rate * 1.8 * dt)

    def _do_wander(self, dt, world=None):
        self.wander_timer -= dt
        if self.wander_timer <= 0:
            self.wander_timer = random.uniform(1.2, 3.8)
            angle = random.uniform(0, math.tau)
            spd = self.speed * 0.38
            self.vel = [math.cos(angle) * spd, math.sin(angle) * spd]

        self.pos[0] += self.vel[0] * dt
        self.pos[1] += self.vel[1] * dt
        self.stamina = max(0, self.stamina - self.stamina_rate * 0.28 * dt)

        if self.pos[0] < 6 or self.pos[0] > world.sim_w - 6: self.vel[0] *= -1
        if self.pos[1] < 6 or self.pos[1] > world.sim_h - 6: self.vel[1] *= -1

        if self.kind != 'alligator' and world and in_water(self.pos, world.water_zones):
            self.vel[0] *= -1
            self.vel[1] *= -1

    def draw_health_bar(self, surf, camera):
        if not self.alive: return
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        w = int(self.size * 2 * camera.zoom)
        h = max(2, int(4 * camera.zoom))
        pygame.draw.rect(surf, C_BAR_BG, (sx - w//2, sy - int(self.size * camera.zoom) - 8, w, h), border_radius=2)
        fill = int((self.health / 100) * w)
        if fill > 0:
            pygame.draw.rect(surf, C_HEALTH, (sx - w//2, sy - int(self.size * camera.zoom) - 8, fill, h), border_radius=2)

    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        if s < 1: return
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.circle(surf, self.color, (sx, sy), s)
        if self.state == State.SLEEP:
            zz = tiny_font.render('z', True, (190,190,255))
            surf.blit(zz, (sx+s-2, sy-s-2))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

    def draw_stats_panel(self, surf, panel_x, font, sfont):
        y = 195
        name = font.render(self.kind.capitalize(), True, self.color)
        surf.blit(name, (panel_x + 10, y)); y += 30
        age_s = sfont.render(f'Age: {self.age:.0f}s', True, GREY)
        surf.blit(age_s, (panel_x + 10, y)); y += 20
        st_s = sfont.render(f'State: {self.state.name}', True, WHITE)
        surf.blit(st_s, (panel_x + 10, y)); y += 26
        BW = PANEL_W - 30
        for label, val, col in [
            ('Health', self.health, C_HEALTH),
            ('Hunger', self.hunger, C_HUNGER),
            ('Thirst', self.thirst, C_THIRST),
            ('Stamina', self.stamina, C_STAMINA),
            ('Sleep', self.sleep_v, C_SLEEP),
        ]:
            lbl = sfont.render(label, True, (175,175,175))
            surf.blit(lbl, (panel_x + 10, y)); y += 17
            pygame.draw.rect(surf, C_BAR_BG, (panel_x + 10, y, BW, 12), border_radius=4)
            fw = max(0, int(val/100*BW))
            if fw:
                pygame.draw.rect(surf, col, (panel_x+10, y, fw, 12), border_radius=4)
            num = sfont.render(f'{val:.0f}', True, WHITE)
            surf.blit(num, (panel_x + BW - 16, y))
            y += 20

# ────────────────────────────────────────────────────────────────────────────────
#  SPECIFIC ANIMALS (with scaled speeds)
# ────────────────────────────────────────────────────────────────────────────────
class Bee(Animal):
    MAX = 80
    def __init__(self, x, y):
        super().__init__('bee', x, y, speed=250, size=5, diet='bee', color=ANIMAL_COLORS['bee'])
        self.poll_target = None
        self.hive_pos = [float(x), float(y)]  # Remember hive location
        self.has_pollen = False
        self.returning_to_hive = False
        self.pollen_drop_timer = 0.0

    def update(self, dt, world):
        self.age += dt
        self.health = min(100, self.health + dt*0.5)
        self.hunger -= self.hunger_drain * dt
        self.thirst -= self.thirst_drain * dt * 0.4
        self.sleep_v -= self.sleep_drain * dt
        self.hunger = max(0, self.hunger)
        self.thirst = max(0, self.thirst)
        if self.hunger <= 0 or self.thirst <= 0 or self.health <= 0:
            self.alive = False
            return
        if self.sleep_v < 14:
            self.state = State.SLEEP
            self._do_sleep(dt)
            return
        # Bees shelter during rain (stay near hive, move slowly)
        if world.weather in ('rain', 'storm'):
            d = dist(self.pos, self.hive_pos)
            if d > 60:
                self._move_toward(self.hive_pos, dt, mult=0.5)
            self.state = State.REST
            return
        # Pollination behavior
        if self.returning_to_hive:
            # Returning to hive with pollen, dropping flowers along the way
            self.state = State.POLLINATE
            self.pollen_drop_timer -= dt
            if self.pollen_drop_timer <= 0:
                self.pollen_drop_timer = random.uniform(1.5, 3.0)
                # Drop a flower along the path
                if self.has_pollen and random.random() < 0.4:
                    fx = self.pos[0] + random.uniform(-30, 30)
                    fy = self.pos[1] + random.uniform(-30, 30)
                    fx = clamp(fx, 6, world.sim_w - 6)
                    fy = clamp(fy, 6, world.sim_h - 6)
                    if not in_water([fx, fy], world.water_zones):
                        flower_count = sum(1 for e in world.entities if isinstance(e, Flower))
                        if flower_count < Flower.MAX:
                            world.to_add.append(Flower(fx, fy))
                            world.to_add.append(Particle(fx, fy, C_FLOWER_Y, speed=1.0, life=1.5, size=3))
            d = self._move_toward(self.hive_pos, dt)
            if d < 30:
                self.returning_to_hive = False
                self.has_pollen = False
                self.hunger = min(100, self.hunger + 15)
                # Pollen particles at hive
                for _ in range(3):
                    world.to_add.append(Particle(self.hive_pos[0], self.hive_pos[1], (255, 220, 50), speed=1.5, life=1.0, size=3))
        else:
            # Looking for flowers to pollinate
            if self.poll_target is None or not self.poll_target.alive:
                flowers = [e for e in world.entities if isinstance(e, Flower) and e.alive]
                self.poll_target = random.choice(flowers) if flowers else None
            if self.poll_target:
                self.state = State.POLLINATE
                d = self._move_toward(self.poll_target.pos, dt)
                if d < 20:
                    self.poll_target.pollinate()
                    self.hunger = min(100, self.hunger + 6)
                    self.has_pollen = True
                    self.returning_to_hive = True
                    self.pollen_drop_timer = random.uniform(1.0, 2.5)
                    self.poll_target = None
            else:
                self._do_wander(dt, world)
        self.pos[0] = clamp(self.pos[0], 6, world.sim_w-6)
        self.pos[1] = clamp(self.pos[1], 6, world.sim_h-6)

    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, (242,202,18), (sx-4*camera.zoom, sy-3*camera.zoom, 8*camera.zoom, 6*camera.zoom))
        pygame.draw.line(surf, BLACK, (sx-2*camera.zoom, sy-3*camera.zoom), (sx-2*camera.zoom, sy+2*camera.zoom), max(1,int(2*camera.zoom)))
        pygame.draw.line(surf, BLACK, (sx+2*camera.zoom, sy-3*camera.zoom), (sx+2*camera.zoom, sy+2*camera.zoom), max(1,int(2*camera.zoom)))
        wing_surf = pygame.Surface((8*camera.zoom,6*camera.zoom), pygame.SRCALPHA)
        pygame.draw.ellipse(wing_surf, (200,230,255,180), (0,0,7*camera.zoom,5*camera.zoom))
        surf.blit(wing_surf, (sx-7*camera.zoom, sy-5*camera.zoom))
        surf.blit(wing_surf, (sx, sy-5*camera.zoom))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Rabbit(Animal):
    MAX = 120
    def __init__(self, x, y):
        super().__init__('rabbit', x, y, speed=280, size=6, diet='herbivore', color=ANIMAL_COLORS['rabbit'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-6*camera.zoom, sy-4*camera.zoom, 12*camera.zoom, 8*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+4*camera.zoom, sy-1*camera.zoom), int(4*camera.zoom))
        pygame.draw.line(surf, self.color, (sx+1*camera.zoom, sy-7*camera.zoom), (sx-2*camera.zoom, sy-12*camera.zoom), max(1,int(3*camera.zoom)))
        pygame.draw.line(surf, self.color, (sx+6*camera.zoom, sy-7*camera.zoom), (sx+5*camera.zoom, sy-12*camera.zoom), max(1,int(3*camera.zoom)))
        pygame.draw.circle(surf, BLACK, (sx+6*camera.zoom, sy-2*camera.zoom), max(1,int(1*camera.zoom)))
        if self.state == State.SLEEP:
            zz = tiny_font.render('z', True, (190,190,255))
            surf.blit(zz, (sx+s, sy-s))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

# (Other animal classes similarly updated with scaled drawing – abbreviated for brevity, full code included in final version)

class Pig(Animal):
    MAX = 60
    def __init__(self, x, y):
        super().__init__('pig', x, y, speed=140, size=10, diet='omnivore', color=ANIMAL_COLORS['pig'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-9*camera.zoom, sy-5*camera.zoom, 18*camera.zoom, 10*camera.zoom))
        pygame.draw.circle(surf, (210,130,120), (sx+7*camera.zoom, sy), int(4*camera.zoom))
        pygame.draw.polygon(surf, self.color, [(sx-4*camera.zoom, sy-6*camera.zoom), (sx-6*camera.zoom, sy-12*camera.zoom), (sx, sy-8*camera.zoom)])
        pygame.draw.circle(surf, BLACK, (sx+4*camera.zoom, sy-3*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Deer(Animal):
    MAX = 60
    def __init__(self, x, y):
        super().__init__('deer', x, y, speed=250, size=9, diet='herbivore', color=ANIMAL_COLORS['deer'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-8*camera.zoom, sy-5*camera.zoom, 16*camera.zoom, 10*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+7*camera.zoom, sy-2*camera.zoom), int(5*camera.zoom))
        pygame.draw.line(surf, (120,80,40), (sx+5*camera.zoom, sy-7*camera.zoom), (sx+2*camera.zoom, sy-15*camera.zoom), max(1,int(2*camera.zoom)))
        pygame.draw.line(surf, (120,80,40), (sx+9*camera.zoom, sy-7*camera.zoom), (sx+12*camera.zoom, sy-15*camera.zoom), max(1,int(2*camera.zoom)))
        pygame.draw.circle(surf, BLACK, (sx+9*camera.zoom, sy-3*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Alligator(Animal):
    MAX = 30
    def __init__(self, x, y):
        super().__init__('alligator', x, y, speed=130, size=13, diet='carnivore', color=ANIMAL_COLORS['alligator'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-10*camera.zoom, sy-6*camera.zoom, 20*camera.zoom, 12*camera.zoom))
        pygame.draw.polygon(surf, self.color, [(sx+10*camera.zoom, sy-3*camera.zoom), (sx+18*camera.zoom, sy-2*camera.zoom), (sx+10*camera.zoom, sy+3*camera.zoom)])
        pygame.draw.circle(surf, (200,200,0), (sx+8*camera.zoom, sy-5*camera.zoom), int(2*camera.zoom))
        pygame.draw.line(surf, self.color, (sx-10*camera.zoom, sy), (sx-18*camera.zoom, sy-3*camera.zoom), max(1,int(4*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Tiger(Animal):
    MAX = 25
    def __init__(self, x, y):
        super().__init__('tiger', x, y, speed=240, size=12, diet='carnivore', color=ANIMAL_COLORS['tiger'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-10*camera.zoom, sy-6*camera.zoom, 20*camera.zoom, 12*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+8*camera.zoom, sy-3*camera.zoom), int(6*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+5*camera.zoom, sy-9*camera.zoom), int(3*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+11*camera.zoom, sy-9*camera.zoom), int(3*camera.zoom))
        pygame.draw.line(surf, BLACK, (sx-2*camera.zoom, sy-4*camera.zoom), (sx+2*camera.zoom, sy-4*camera.zoom), max(1,int(2*camera.zoom)))
        pygame.draw.line(surf, BLACK, (sx-5*camera.zoom, sy-1*camera.zoom), (sx-1*camera.zoom, sy-1*camera.zoom), max(1,int(2*camera.zoom)))
        pygame.draw.circle(surf, BLACK, (sx+10*camera.zoom, sy-4*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Wolf(Animal):
    MAX = 35
    def __init__(self, x, y):
        super().__init__('wolf', x, y, speed=220, size=10, diet='carnivore', color=ANIMAL_COLORS['wolf'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-8*camera.zoom, sy-5*camera.zoom, 16*camera.zoom, 10*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+6*camera.zoom, sy-2*camera.zoom), int(5*camera.zoom))
        pygame.draw.polygon(surf, self.color, [(sx+2*camera.zoom, sy-7*camera.zoom), (sx-2*camera.zoom, sy-12*camera.zoom), (sx+6*camera.zoom, sy-9*camera.zoom)])
        pygame.draw.polygon(surf, self.color, [(sx+7*camera.zoom, sy-7*camera.zoom), (sx+11*camera.zoom, sy-12*camera.zoom), (sx+11*camera.zoom, sy-9*camera.zoom)])
        pygame.draw.circle(surf, BLACK, (sx+8*camera.zoom, sy-3*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Fox(Animal):
    MAX = 40
    def __init__(self, x, y):
        super().__init__('fox', x, y, speed=260, size=7, diet='carnivore', color=ANIMAL_COLORS['fox'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-7*camera.zoom, sy-4*camera.zoom, 14*camera.zoom, 8*camera.zoom))
        pygame.draw.polygon(surf, self.color, [(sx+6*camera.zoom, sy-3*camera.zoom), (sx+12*camera.zoom, sy), (sx+6*camera.zoom, sy+3*camera.zoom)])
        pygame.draw.polygon(surf, self.color, [(sx, sy-7*camera.zoom), (sx-3*camera.zoom, sy-13*camera.zoom), (sx+4*camera.zoom, sy-9*camera.zoom)])
        pygame.draw.polygon(surf, self.color, [(sx+6*camera.zoom, sy-7*camera.zoom), (sx+9*camera.zoom, sy-13*camera.zoom), (sx+10*camera.zoom, sy-9*camera.zoom)])
        pygame.draw.circle(surf, BLACK, (sx+8*camera.zoom, sy-2*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Bear(Animal):
    MAX = 25
    def __init__(self, x, y):
        super().__init__('bear', x, y, speed=160, size=15, diet='omnivore', color=ANIMAL_COLORS['bear'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-12*camera.zoom, sy-8*camera.zoom, 24*camera.zoom, 16*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+10*camera.zoom, sy-3*camera.zoom), int(7*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+6*camera.zoom, sy-10*camera.zoom), int(4*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+14*camera.zoom, sy-10*camera.zoom), int(4*camera.zoom))
        pygame.draw.circle(surf, BLACK, (sx+12*camera.zoom, sy-5*camera.zoom), max(1,int(2*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

class Bird(Animal):
    MAX = 80
    def __init__(self, x, y):
        super().__init__('bird', x, y, speed=350, size=5, diet='herbivore', color=ANIMAL_COLORS['bird'])
    def draw(self, surf, camera, tiny_font):
        sx, sy = camera.world_to_screen(self.pos[0], self.pos[1])
        s = int(self.size * camera.zoom)
        shadow = pygame.Surface((s*2, s), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0,0,0,60), (0,0,s*2,s))
        surf.blit(shadow, (sx-s, sy+s-2))
        pygame.draw.ellipse(surf, self.color, (sx-5*camera.zoom, sy-3*camera.zoom, 10*camera.zoom, 6*camera.zoom))
        pygame.draw.circle(surf, self.color, (sx+4*camera.zoom, sy-2*camera.zoom), int(3*camera.zoom))
        pygame.draw.polygon(surf, (255,200,0), [(sx+6*camera.zoom, sy-2*camera.zoom), (sx+10*camera.zoom, sy-1*camera.zoom), (sx+6*camera.zoom, sy)])
        pygame.draw.ellipse(surf, (60,120,200), (sx-3*camera.zoom, sy-5*camera.zoom, 8*camera.zoom, 4*camera.zoom))
        pygame.draw.circle(surf, BLACK, (sx+5*camera.zoom, sy-3*camera.zoom), max(1,int(1*camera.zoom)))
        if self.selected:
            pygame.draw.circle(surf, WHITE, (sx, sy), s+4, 2)
        self.draw_health_bar(surf, camera)

# Food chain: rabbit/bird/bee < fox < wolf < bear/tiger, alligator is apex aquatic
PREDATOR_TYPES = (Alligator, Tiger, Wolf, Fox, Bear)
PREY_TYPES = (Rabbit, Pig, Deer, Bird, Fox)  # Fox is both predator and prey

# ────────────────────────────────────────────────────────────────────────────────
#  WORLD
# ────────────────────────────────────────────────────────────────────────────────
class World:
    def __init__(self, sim_w, sim_h):
        self.sim_w = sim_w
        self.sim_h = sim_h
        self.entities = []
        self.to_add = []
        self.water_zones = []
        self.time = 0.0
        self.temperature = 22.0
        self.temp_timer = 30.0
        self.spawn_timer = 0.0
        self.spawn_rate = 1.0
        # River data
        self.river_points = generate_river_points(sim_w, sim_h)
        self.river_path = interpolate_river(self.river_points, segments_per_span=25)
        # Branch tributaries
        self.branch_paths = generate_branch_points(self.river_path, sim_w, sim_h)
        self._build_water_zones()
        # Weather system
        self.weather = 'clear'  # 'clear', 'rain', 'storm'
        self.weather_timer = random.uniform(30, 60)
        self.rain_intensity = 0.0  # 0.0 to 1.0
        self.rain_drops = []  # list of (x, y, speed, life) for visible rain
        self.lightning_timer = 0.0
        self.lightning_flash = 0.0
        # Ground detail rocks (pre-generated for performance)
        self.ground_details = []
        rng = random.Random(999)
        for _ in range(300):
            gx = rng.uniform(20, sim_w - 20)
            gy = rng.uniform(20, sim_h - 20)
            if not in_water([gx, gy], self.water_zones):
                gs = rng.uniform(2, 5)
                shade = rng.randint(20, 40)
                self.ground_details.append((gx, gy, gs, (BG[0]+shade, BG[1]+shade, BG[2]+shade)))
        self._setup()

    def _build_water_zones(self):
        """Build collision rects from river path and branches."""
        self.water_zones = build_river_rects(self.river_path, base_width=90)
        self.water_zones.extend(build_branch_rects(self.branch_paths, base_width=35))

    def _setup(self):
        # Spawn plants
        for _ in range(12):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Tree(x, y, mature=True))
        for _ in range(80):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Grass(x, y))
        for _ in range(20):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Flower(x, y))
        for _ in range(20):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(BerryBush(x, y))
        for _ in range(20):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Mushroom(x, y))

        # Pack spawning – animals spawn in groups
        # Beehives: clusters of 4-6 bees near flowers
        for _ in range(4):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            pack_size = random.randint(4, 6)
            for _ in range(pack_size):
                ox = hx + random.uniform(-40, 40)
                oy = hy + random.uniform(-40, 40)
                ox = clamp(ox, 12, self.sim_w - 12)
                oy = clamp(oy, 12, self.sim_h - 12)
                self.entities.append(Bee(ox, oy))
        # Rabbit warrens: groups of 4-6
        for _ in range(3):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            for _ in range(random.randint(4, 6)):
                ox = hx + random.uniform(-60, 60)
                oy = hy + random.uniform(-60, 60)
                ox = clamp(ox, 12, self.sim_w - 12)
                oy = clamp(oy, 12, self.sim_h - 12)
                self.entities.append(Rabbit(ox, oy))
        # Wolf packs: groups of 3-4
        for _ in range(2):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            for _ in range(random.randint(3, 4)):
                ox = hx + random.uniform(-50, 50)
                oy = hy + random.uniform(-50, 50)
                ox = clamp(ox, 12, self.sim_w - 12)
                oy = clamp(oy, 12, self.sim_h - 12)
                self.entities.append(Wolf(ox, oy))
        # Deer herds: groups of 3-5
        for _ in range(2):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            for _ in range(random.randint(3, 5)):
                ox = hx + random.uniform(-70, 70)
                oy = hy + random.uniform(-70, 70)
                ox = clamp(ox, 12, self.sim_w - 12)
                oy = clamp(oy, 12, self.sim_h - 12)
                self.entities.append(Deer(ox, oy))
        # Pig groups: 2-3
        for _ in range(2):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            for _ in range(random.randint(2, 3)):
                ox = hx + random.uniform(-50, 50)
                oy = hy + random.uniform(-50, 50)
                self.entities.append(Pig(ox, oy))
        # Bird flocks: 4-6
        for _ in range(3):
            hx, hy = rand_land(self.water_zones, self.sim_w, self.sim_h)
            for _ in range(random.randint(4, 6)):
                ox = hx + random.uniform(-80, 80)
                oy = hy + random.uniform(-80, 80)
                self.entities.append(Bird(ox, oy))
        # Solo predators
        for _ in range(2):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Tiger(x, y))
        for _ in range(2):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Fox(x, y))
        for _ in range(1):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Bear(x, y))
        for _ in range(2):
            x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
            self.entities.append(Alligator(x, y))

    def resize(self, new_w, new_h):
        self.sim_w = new_w
        self.sim_h = new_h

    def update(self, dt):
        self.time += dt
        self.temp_timer -= dt
        if self.temp_timer <= 0:
            self.temp_timer = 30.0
            self.temperature += random.uniform(-8, 8)
            self.temperature = clamp(self.temperature, 5, 55)

        if self.temperature > 45 and random.random() < 0.0005 * dt * 30:
            x = random.uniform(50, self.sim_w-50)
            y = random.uniform(50, self.sim_h-50)
            if not in_water([x,y], self.water_zones):
                self.to_add.append(Fire(x, y))

        # Weather system
        self.weather_timer -= dt
        if self.weather_timer <= 0:
            if self.weather == 'clear':
                self.weather = random.choice(['rain', 'rain', 'storm'])
                self.weather_timer = random.uniform(15, 40)
                self.rain_intensity = 0.3 if self.weather == 'rain' else 0.7
            else:
                self.weather = 'clear'
                self.weather_timer = random.uniform(30, 80)
                self.rain_intensity = 0.0
                self.rain_drops.clear()

        # Update rain
        if self.weather in ('rain', 'storm'):
            # Ramp up intensity
            target = 0.5 if self.weather == 'rain' else 1.0
            self.rain_intensity += (target - self.rain_intensity) * dt * 0.5
            # Spawn rain drops in visible area
            num_new = int(self.rain_intensity * 40 * dt * 60)
            for _ in range(min(num_new, 30)):
                rx = random.uniform(0, self.sim_w)
                ry = random.uniform(0, self.sim_h)
                rspd = random.uniform(300, 600)
                self.rain_drops.append([rx, ry, rspd, random.uniform(0.3, 0.8)])
            # Update existing drops
            new_drops = []
            for rd in self.rain_drops:
                rd[1] += rd[2] * dt
                rd[3] -= dt
                if rd[3] > 0 and rd[1] < self.sim_h:
                    new_drops.append(rd)
            self.rain_drops = new_drops
            # Rain cools temperature
            self.temperature = max(5, self.temperature - dt * 0.3 * self.rain_intensity)
            # Rain helps plants grow faster (water the land)
            if random.random() < 0.01 * self.rain_intensity:
                for e in self.entities:
                    if isinstance(e, Plant) and e.alive:
                        e.spread_timer -= 0.5
            # Storms: lightning and fire
            if self.weather == 'storm':
                self.lightning_timer -= dt
                if self.lightning_timer <= 0:
                    self.lightning_timer = random.uniform(3, 10)
                    self.lightning_flash = 0.4
                    # Lightning can start fires
                    if random.random() < 0.3:
                        x = random.uniform(50, self.sim_w-50)
                        y = random.uniform(50, self.sim_h-50)
                        if not in_water([x,y], self.water_zones):
                            self.to_add.append(Fire(x, y))
                    # Lightning can damage nearby animals
                    lx = random.uniform(100, self.sim_w-100)
                    ly = random.uniform(100, self.sim_h-100)
                    for e in self.entities:
                        if isinstance(e, Animal) and e.alive and dist(e.pos, [lx, ly]) < 80:
                            e.health -= random.uniform(15, 35)
                            if e.health <= 0:
                                e.alive = False
            # Decay lightning flash
            if self.lightning_flash > 0:
                self.lightning_flash -= dt * 2
                if self.lightning_flash < 0:
                    self.lightning_flash = 0
            # Rain puts out fires
            if self.weather in ('rain', 'storm'):
                for e in self.entities:
                    if isinstance(e, Fire) and e.alive:
                        e.life -= dt * 2 * self.rain_intensity
        else:
            self.rain_intensity = max(0, self.rain_intensity - dt)
            if self.lightning_flash > 0:
                self.lightning_flash -= dt * 2
                if self.lightning_flash < 0:
                    self.lightning_flash = 0

        # Periodic mob spawning
        self.spawn_timer -= dt
        if self.spawn_timer <= 0:
            self.spawn_timer = max(2.0, 15.0 / self.spawn_rate)
            animal_types = [
                (Rabbit, 120), (Deer, 60), (Pig, 60), (Bird, 80),
                (Bee, 80), (Wolf, 35), (Fox, 40), (Tiger, 25),
                (Bear, 25), (Alligator, 30),
            ]
            for cls, max_count in animal_types:
                count = sum(1 for e in self.entities if isinstance(e, cls) and e.alive)
                if count < max_count * self.spawn_rate:
                    if random.random() < 0.3 * self.spawn_rate:
                        x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
                        self.to_add.append(cls(x, y))

        for e in self.entities[:]:
            if getattr(e, 'alive', True):
                e.update(dt, self)

        preds = [e for e in self.entities if isinstance(e, PREDATOR_TYPES) and e.alive]
        for e in self.entities:
            if isinstance(e, PREY_TYPES) and e.alive and e.state not in (State.FLEE, State.SLEEP):
                for pred in preds:
                    if dist(e.pos, pred.pos) < 250:
                        e.state = State.FLEE
                        e.target = pred
                        break

        self.entities = [e for e in self.entities if getattr(e, 'alive', True)]
        self.entities.extend(self.to_add)
        self.to_add.clear()

    def draw(self, surf, camera):
        surf.fill(BG)

        # Draw ground texture details (small rocks/pebbles)
        vr = (camera.x - camera.view_w/(2*camera.zoom) - 50,
              camera.y - camera.view_h/(2*camera.zoom) - 50,
              camera.view_w/camera.zoom + 100,
              camera.view_h/camera.zoom + 100)
        for gx, gy, gs, gc in self.ground_details:
            if vr[0] <= gx <= vr[0]+vr[2] and vr[1] <= gy <= vr[1]+vr[3]:
                sx, sy = camera.world_to_screen(gx, gy)
                r = max(1, int(gs * camera.zoom))
                pygame.draw.circle(surf, gc, (sx, sy), r)

        # Draw the river
        z = camera.zoom
        # Layer 1: River bank edges (wider, darker)
        for i in range(0, len(self.river_path) - 1, 2):
            x1, y1 = self.river_path[i]
            x2, y2 = self.river_path[min(i+2, len(self.river_path)-1)]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            if not (vr[0] <= mid_x <= vr[0]+vr[2] and vr[1] <= mid_y <= vr[1]+vr[3]):
                continue
            sx1, sy1 = camera.world_to_screen(x1, y1)
            sx2, sy2 = camera.world_to_screen(x2, y2)
            width_base = 55 + 18 * math.sin(i * 0.05)
            bank_w = max(4, int(width_base * z))
            pygame.draw.line(surf, (22, 42, 16), (sx1, sy1), (sx2, sy2), bank_w)
        # Layer 2: Main water
        for i in range(len(self.river_path) - 1):
            x1, y1 = self.river_path[i]
            x2, y2 = self.river_path[i + 1]
            mid_x = (x1 + x2) / 2
            mid_y = (y1 + y2) / 2
            if not (vr[0] <= mid_x <= vr[0]+vr[2] and vr[1] <= mid_y <= vr[1]+vr[3]):
                continue
            sx1, sy1 = camera.world_to_screen(x1, y1)
            sx2, sy2 = camera.world_to_screen(x2, y2)
            width_base = 45 + 15 * math.sin(i * 0.05)
            w = max(3, int(width_base * z))
            pygame.draw.line(surf, WATER_DEEP, (sx1, sy1), (sx2, sy2), w)
            # Lighter center streak
            w2 = max(2, int(width_base * 0.55 * z))
            lighter = (WATER_DEEP[0]+15, WATER_DEEP[1]+15, min(255, WATER_DEEP[2]+20))
            pygame.draw.line(surf, lighter, (sx1, sy1), (sx2, sy2), w2)
        # Layer 3: Animated ripples
        ripple_col = (min(255, WATER_LIGHT[0]+20), min(255, WATER_LIGHT[1]+20), min(255, WATER_LIGHT[2]+10))
        for i in range(0, len(self.river_path), 8):
            rx, ry = self.river_path[i]
            if not (vr[0] <= rx <= vr[0]+vr[2] and vr[1] <= ry <= vr[1]+vr[3]):
                continue
            offset = math.sin(self.time * 2.5 + i * 0.3) * 6
            rsx, rsy = camera.world_to_screen(rx + offset, ry + offset * 0.5)
            rw = max(2, int(12 * z))
            rh = max(1, int(3 * z))
            pygame.draw.ellipse(surf, ripple_col, (rsx - rw//2, rsy - rh//2, rw, rh))

        # Draw branch tributaries
        for bp in self.branch_paths:
            # Bank edges
            for i in range(0, len(bp) - 1, 2):
                x1, y1 = bp[i]
                x2, y2 = bp[min(i+2, len(bp)-1)]
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                if not (vr[0] <= mid_x <= vr[0]+vr[2] and vr[1] <= mid_y <= vr[1]+vr[3]):
                    continue
                sx1, sy1 = camera.world_to_screen(x1, y1)
                sx2, sy2 = camera.world_to_screen(x2, y2)
                t = i / max(1, len(bp) - 1)
                width_base = 28 * (1.0 - t * 0.5) + 6 * math.sin(i * 0.08)
                bank_w = max(2, int(width_base * z))
                pygame.draw.line(surf, (22, 42, 16), (sx1, sy1), (sx2, sy2), bank_w)
            # Water
            for i in range(len(bp) - 1):
                x1, y1 = bp[i]
                x2, y2 = bp[i + 1]
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                if not (vr[0] <= mid_x <= vr[0]+vr[2] and vr[1] <= mid_y <= vr[1]+vr[3]):
                    continue
                sx1, sy1 = camera.world_to_screen(x1, y1)
                sx2, sy2 = camera.world_to_screen(x2, y2)
                t = i / max(1, len(bp) - 1)
                width_base = 20 * (1.0 - t * 0.5) + 4 * math.sin(i * 0.08)
                w = max(2, int(width_base * z))
                pygame.draw.line(surf, WATER_DEEP, (sx1, sy1), (sx2, sy2), w)
                w2 = max(1, int(width_base * 0.5 * z))
                lighter = (WATER_DEEP[0]+15, WATER_DEEP[1]+15, min(255, WATER_DEEP[2]+20))
                pygame.draw.line(surf, lighter, (sx1, sy1), (sx2, sy2), w2)
            # Ripples on branches
            for i in range(0, len(bp), 12):
                rx, ry = bp[i]
                if not (vr[0] <= rx <= vr[0]+vr[2] and vr[1] <= ry <= vr[1]+vr[3]):
                    continue
                offset = math.sin(self.time * 2.5 + i * 0.4) * 4
                rsx, rsy = camera.world_to_screen(rx + offset, ry + offset * 0.5)
                rw = max(1, int(7 * z))
                rh = max(1, int(2 * z))
                pygame.draw.ellipse(surf, ripple_col, (rsx - rw//2, rsy - rh//2, rw, rh))

        # Draw rain drops if raining
        if self.weather in ('rain', 'storm'):
            rain_col = (140, 160, 200, 120) if self.weather == 'rain' else (180, 190, 220, 150)
            for rd in self.rain_drops:
                rdx, rdy, rdspd, rdlife = rd
                if vr[0] <= rdx <= vr[0]+vr[2] and vr[1] <= rdy <= vr[1]+vr[3]:
                    sx, sy = camera.world_to_screen(rdx, rdy)
                    length = max(2, int(rdspd * 0.02 * z))
                    pygame.draw.line(surf, (140, 160, 200), (sx, sy), (sx, sy + length), max(1, int(z)))

        # Lightning flash overlay
        if self.lightning_flash > 0:
            flash_alpha = int(min(80, self.lightning_flash * 200))
            flash_surf = pygame.Surface((surf.get_width(), surf.get_height()), pygame.SRCALPHA)
            flash_surf.fill((255, 255, 240, flash_alpha))
            surf.blit(flash_surf, (0, 0))

        # Cull entities outside view
        visible_rect = vr
        for e in self.entities:
            if isinstance(e, Plant):
                if visible_rect[0] <= e.pos[0] <= visible_rect[0]+visible_rect[2] and visible_rect[1] <= e.pos[1] <= visible_rect[1]+visible_rect[3]:
                    e.draw(surf, camera)
            elif isinstance(e, Particle):
                if visible_rect[0] <= e.pos[0] <= visible_rect[0]+visible_rect[2] and visible_rect[1] <= e.pos[1] <= visible_rect[1]+visible_rect[3]:
                    e.draw(surf, camera)
            elif isinstance(e, Fire):
                e.draw(surf, camera)
        animals = [e for e in self.entities if isinstance(e, Animal)]
        return animals

    def counts(self):
        c = {}
        for e in self.entities:
            n = type(e).__name__
            c[n] = c.get(n, 0) + 1
        return c

    def spawn_entity(self, entity_type):
        x, y = rand_land(self.water_zones, self.sim_w, self.sim_h)
        type_map = {
            'grass': Grass, 'flower': Flower, 'tree': Tree, 'berrybush': BerryBush, 'mushroom': Mushroom,
            'bee': Bee, 'rabbit': Rabbit, 'pig': Pig, 'deer': Deer,
            'alligator': Alligator, 'tiger': Tiger, 'wolf': Wolf, 'fox': Fox, 'bear': Bear, 'bird': Bird
        }
        cls = type_map.get(entity_type.lower())
        if cls:
            if cls == Tree:
                self.entities.append(cls(x, y, mature=True))
            else:
                self.entities.append(cls(x, y))
            return True
        return False

# ────────────────────────────────────────────────────────────────────────────────
#  UI
# ────────────────────────────────────────────────────────────────────────────────
class TextInput:
    def __init__(self, x, y, w, h, font, prompt=''):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.text = ''
        self.prompt = prompt
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                cmd = self.text.strip()
                self.text = ''
                return cmd
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
        return None

    def update(self, dt):
        self.cursor_timer += dt
        if self.cursor_timer >= 0.5:
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = 0

    def draw(self, surf):
        color = WHITE if self.active else GREY
        pygame.draw.rect(surf, C_BAR_BG, self.rect, border_radius=4)
        pygame.draw.rect(surf, color, self.rect, 2, border_radius=4)
        txt = self.text if self.text else self.prompt
        txt_surf = self.font.render(txt, True, GREY if not self.text else WHITE)
        surf.blit(txt_surf, (self.rect.x+5, self.rect.y+5))
        if self.active and self.cursor_visible:
            cursor_x = self.rect.x + 5 + self.font.size(txt)[0]
            pygame.draw.line(surf, WHITE, (cursor_x, self.rect.y+4), (cursor_x, self.rect.y+self.rect.h-4), 2)

def _draw_section_header(surf, sfont, text, x, y, w, color=(85, 170, 65)):
    """Draw a styled section header with lines on both sides."""
    lbl = sfont.render(text, True, color)
    lw = lbl.get_width()
    line_y = y + lbl.get_height() // 2
    margin = 8
    left_end = x + margin
    right_end = x + w - margin
    text_x = x + (w - lw) // 2
    if text_x - 4 > left_end:
        pygame.draw.line(surf, (55, 75, 45), (left_end, line_y), (text_x - 4, line_y), 1)
    if text_x + lw + 4 < right_end:
        pygame.draw.line(surf, (55, 75, 45), (text_x + lw + 4, line_y), (right_end, line_y), 1)
    surf.blit(lbl, (text_x, y))
    return lbl.get_height() + 4

def _draw_bar(surf, x, y, w, h, value, max_val, fg_color, bg_color=C_BAR_BG, border_radius=3):
    """Draw a small progress bar."""
    pygame.draw.rect(surf, bg_color, (x, y, w, h), border_radius=border_radius)
    fill = int((value / max_val) * w) if max_val > 0 else 0
    if fill > 0:
        pygame.draw.rect(surf, fg_color, (x, y, min(fill, w), h), border_radius=border_radius)

def draw_panel(surf, world, selected, font, sfont, tiny_font, panel_x, sim_time, time_scale, temperature, command_input):
    h = surf.get_height()
    pw = PANEL_W

    # Panel background with subtle gradient
    for gy in range(h):
        t = gy / max(1, h)
        r = int(18 + t * 6)
        g = int(22 + t * 8)
        b = int(14 + t * 4)
        pygame.draw.line(surf, (r, g, b), (panel_x, gy), (panel_x + pw, gy))
    # Left border accent
    pygame.draw.line(surf, (60, 100, 45), (panel_x, 0), (panel_x, h), 2)

    y = 8
    # ── Title ──
    title = font.render('Ecosystem Sim', True, (110, 220, 85))
    surf.blit(title, (panel_x + 12, y))
    # Version badge
    ver = tiny_font.render('v2.0', True, (80, 130, 65))
    surf.blit(ver, (panel_x + pw - 36, y + 4))
    y += 28

    # ── Status bar: time, temp, weather ──
    pygame.draw.rect(surf, (28, 35, 22), (panel_x + 6, y, pw - 12, 52), border_radius=5)
    # Time
    t_lbl = tiny_font.render(f'Time: {sim_time:.0f}s', True, (160, 180, 150))
    surf.blit(t_lbl, (panel_x + 12, y + 4))
    # Temperature with color coding
    if temperature > 45:
        temp_col = (255, 100, 80)
    elif temperature > 35:
        temp_col = (255, 200, 100)
    elif temperature < 15:
        temp_col = (100, 160, 255)
    else:
        temp_col = (150, 220, 150)
    temp_lbl = tiny_font.render(f'Temp: {temperature:.1f}C', True, temp_col)
    surf.blit(temp_lbl, (panel_x + pw // 2 + 5, y + 4))
    # Weather indicator
    weather_icons = {'clear': 'Clear', 'rain': 'Rain', 'storm': 'Storm'}
    weather_colors = {'clear': (200, 220, 140), 'rain': (100, 150, 220), 'storm': (180, 120, 220)}
    w_name = weather_icons.get(world.weather, 'Clear')
    w_col = weather_colors.get(world.weather, (200, 200, 200))
    w_lbl = sfont.render(f'Weather: {w_name}', True, w_col)
    surf.blit(w_lbl, (panel_x + 12, y + 20))
    # Rain intensity bar
    if world.weather != 'clear':
        _draw_bar(surf, panel_x + pw // 2 + 5, y + 25, pw // 2 - 18, 6, world.rain_intensity, 1.0, w_col)
        ri_lbl = tiny_font.render(f'{world.rain_intensity*100:.0f}%', True, w_col)
        surf.blit(ri_lbl, (panel_x + pw - 38, y + 20))
    y += 58

    # ── Selected entity details ──
    if selected and selected.alive:
        y += _draw_section_header(surf, sfont, 'Selected', panel_x, y, pw, (200, 200, 120))
        pygame.draw.rect(surf, (30, 38, 24), (panel_x + 6, y, pw - 12, 105), border_radius=5)
        name_col = ANIMAL_COLORS.get(selected.kind, (200, 200, 200)) if hasattr(selected, 'kind') else (148, 195, 132)
        name_text = selected.kind.capitalize() if hasattr(selected, 'kind') else type(selected).__name__
        n_lbl = sfont.render(name_text, True, name_col)
        surf.blit(n_lbl, (panel_x + 14, y + 4))

        if isinstance(selected, Animal):
            # State badge
            state_text = selected.state.name.replace('_', ' ').title()
            st_lbl = tiny_font.render(state_text, True, (180, 180, 130))
            surf.blit(st_lbl, (panel_x + pw - st_lbl.get_width() - 14, y + 6))
            # Stat bars
            bar_x = panel_x + 14
            bar_w = pw - 36
            bar_h = 6
            stats_info = [
                ('HP', selected.health, 100, (220, 60, 60)),
                ('Food', selected.hunger, 100, (220, 180, 60)),
                ('Water', selected.thirst, 100, (60, 140, 220)),
                ('Sleep', selected.sleep_v, 100, (140, 100, 200)),
                ('Stamina', selected.stamina, 100, (60, 200, 120)),
            ]
            by = y + 22
            for label, val, mx, col in stats_info:
                l = tiny_font.render(f'{label}', True, (140, 150, 130))
                surf.blit(l, (bar_x, by))
                _draw_bar(surf, bar_x + 48, by + 2, bar_w - 78, bar_h, val, mx, col)
                v = tiny_font.render(f'{val:.0f}', True, (140, 150, 130))
                surf.blit(v, (bar_x + bar_w - 24, by))
                by += 15
            # Age
            age_lbl = tiny_font.render(f'Age: {selected.age:.0f}s', True, (140, 150, 130))
            surf.blit(age_lbl, (bar_x, by + 2))
            # Pollen indicator for bees
            if isinstance(selected, Bee):
                pollen_txt = 'Has Pollen' if selected.has_pollen else 'No Pollen'
                pollen_col = (255, 220, 50) if selected.has_pollen else (100, 100, 80)
                pl = tiny_font.render(pollen_txt, True, pollen_col)
                surf.blit(pl, (bar_x + 60, by + 2))
        y += 112
    else:
        y += 4

    # ── Food Chain ──
    y += _draw_section_header(surf, sfont, 'Food Chain', panel_x, y, pw, (200, 160, 100))
    pygame.draw.rect(surf, (28, 35, 22), (panel_x + 6, y, pw - 12, 36), border_radius=4)
    chain_items = [
        ('Rabbit', (180, 160, 120)),
        ('Fox', (200, 130, 60)),
        ('Wolf', (140, 140, 150)),
        ('Bear', (140, 90, 50)),
    ]
    cx = panel_x + 12
    for i, (name, col) in enumerate(chain_items):
        lbl = tiny_font.render(name, True, col)
        surf.blit(lbl, (cx, y + 5))
        cx += lbl.get_width() + 2
        if i < len(chain_items) - 1:
            arrow = tiny_font.render('>', True, (100, 120, 80))
            surf.blit(arrow, (cx, y + 5))
            cx += arrow.get_width() + 2
    # Second row
    chain2 = [('Deer', (160, 140, 90)), ('Pig', (200, 150, 150)), ('Bird', (100, 180, 220))]
    cx = panel_x + 12
    for i, (name, col) in enumerate(chain2):
        lbl = tiny_font.render(name, True, col)
        surf.blit(lbl, (cx, y + 19))
        cx += lbl.get_width() + 6
    prey_lbl = tiny_font.render('(prey)', True, (80, 100, 70))
    surf.blit(prey_lbl, (cx, y + 19))
    y += 42

    # ── Populations ──
    y += _draw_section_header(surf, sfont, 'Populations', panel_x, y, pw)
    counts = world.counts()
    # Group: Flora
    flora_order = ['Grass', 'Flower', 'Tree', 'BerryBush', 'Mushroom']
    fauna_prey = ['Rabbit', 'Deer', 'Pig', 'Bird']
    fauna_pred = ['Fox', 'Wolf', 'Bear', 'Tiger', 'Alligator']
    fauna_other = ['Bee']

    total_entities = sum(counts.values())

    def draw_pop_row(name, count, col, x, y_pos):
        dot_r = 3
        pygame.draw.circle(surf, col, (x + dot_r, y_pos + 7), dot_r)
        lbl = tiny_font.render(f'{name}', True, col)
        surf.blit(lbl, (x + 10, y_pos))
        num = tiny_font.render(f'{count}', True, (160, 170, 150))
        surf.blit(num, (panel_x + pw - num.get_width() - 12, y_pos))
        return 14

    # Flora
    fl_lbl = tiny_font.render('Flora:', True, (100, 160, 80))
    surf.blit(fl_lbl, (panel_x + 10, y)); y += 14
    for name in flora_order:
        n = counts.get(name, 0)
        if n == 0: continue
        col = ANIMAL_COLORS.get(name.lower(), (148, 195, 132))
        y += draw_pop_row(name, n, col, panel_x + 14, y)

    # Prey
    fp_lbl = tiny_font.render('Prey:', True, (180, 160, 100))
    surf.blit(fp_lbl, (panel_x + 10, y)); y += 14
    for name in fauna_prey:
        n = counts.get(name, 0)
        if n == 0: continue
        col = ANIMAL_COLORS.get(name.lower(), (180, 180, 180))
        y += draw_pop_row(name, n, col, panel_x + 14, y)

    # Predators
    pr_lbl = tiny_font.render('Predators:', True, (200, 100, 80))
    surf.blit(pr_lbl, (panel_x + 10, y)); y += 14
    for name in fauna_pred:
        n = counts.get(name, 0)
        if n == 0: continue
        col = ANIMAL_COLORS.get(name.lower(), (180, 180, 180))
        y += draw_pop_row(name, n, col, panel_x + 14, y)

    # Other (bees)
    for name in fauna_other:
        n = counts.get(name, 0)
        if n == 0: continue
        col = ANIMAL_COLORS.get(name.lower(), (180, 180, 180))
        y += draw_pop_row(name, n, col, panel_x + 14, y)

    # Total
    tot_lbl = tiny_font.render(f'Total: {total_entities}', True, (130, 140, 120))
    surf.blit(tot_lbl, (panel_x + 10, y)); y += 18

    # ── Speed slider ──
    slider_y = h - 150
    slider_x = panel_x + 20
    slider_w = pw - 40
    slider_h = 8
    y += _draw_section_header(surf, sfont, 'Speed', panel_x, min(y, slider_y - 22), pw, (150, 180, 200))
    pygame.draw.rect(surf, C_BAR_BG, (slider_x, slider_y, slider_w, slider_h), border_radius=4)
    log_min = math.log(0.01)
    log_max = math.log(100.0)
    log_val = math.log(max(0.01, time_scale))
    t = (log_val - log_min) / (log_max - log_min)
    fill_w = int(t * slider_w)
    if fill_w > 0:
        pygame.draw.rect(surf, (100, 200, 255), (slider_x, slider_y, fill_w, slider_h), border_radius=4)
    knob_x = slider_x + fill_w
    pygame.draw.circle(surf, WHITE, (knob_x, slider_y + slider_h // 2), 6)
    pygame.draw.circle(surf, (100, 200, 255), (knob_x, slider_y + slider_h // 2), 4)
    lbl = sfont.render(f'{time_scale:.2f}x', True, WHITE)
    surf.blit(lbl, (panel_x + pw - lbl.get_width() - 14, slider_y - 18))
    surf.blit(tiny_font.render('0.01x', True, GREY), (slider_x, slider_y + 12))
    surf.blit(tiny_font.render('100x', True, GREY), (slider_x + slider_w - 25, slider_y + 12))

    # ── Command input ──
    cmd_y = h - 80
    pygame.draw.line(surf, (55, 75, 45), (panel_x + 8, cmd_y - 6), (panel_x + pw - 8, cmd_y - 6), 1)
    cmd_label = tiny_font.render('Commands: /fire /summon /kill /spawnrate /temperature', True, (100, 110, 90))
    surf.blit(cmd_label, (panel_x + 10, cmd_y - 4))
    command_input.rect.x = panel_x + 10
    command_input.rect.y = cmd_y + 12
    command_input.draw(surf)

    # ── Controls footer ──
    pygame.draw.line(surf, (55, 75, 45), (panel_x + 8, h - 28), (panel_x + pw - 8, h - 28), 1)
    ctrl = tiny_font.render('WASD: pan | Scroll: zoom | /: cmd | Q: quit', True, (70, 90, 60))
    surf.blit(ctrl, (panel_x + 10, h - 22))

# ────────────────────────────────────────────────────────────────────────────────
#  MAIN
# ────────────────────────────────────────────────────────────────────────────────
def main():
    pygame.init()
    screen = pygame.display.set_mode((DEFAULT_W, DEFAULT_H), pygame.RESIZABLE)
    pygame.display.set_caption("Eco Simulator – Huge World")
    pygame.key.set_repeat(0)  # Disable key repeat for smooth WASD
    clock = pygame.time.Clock()

    font = pygame.font.SysFont('segoeui', 18, bold=True)
    sfont = pygame.font.SysFont('segoeui', 14)
    tiny_font = pygame.font.SysFont('segoeui', 11)

    win_w, win_h = screen.get_size()
    sim_w = max(100, win_w - PANEL_W)
    sim_h = max(100, win_h)
    world = World(WORLD_W, WORLD_H)
    camera = Camera(WORLD_W, WORLD_H, sim_w, sim_h)

    time_scale = 1.0
    dragging_slider = False
    selected = None
    command_input = TextInput(0, 0, PANEL_W-20, 24, sfont, prompt='Type /command...')

    running = True
    while running:
        win_w, win_h = screen.get_size()
        panel_w = PANEL_W
        sim_w = max(100, win_w - panel_w)
        sim_h = max(100, win_h)
        camera.update_view_size(sim_w, sim_h)

        dt = clock.tick(FPS) / 1000.0 * time_scale
        dt = min(dt, 0.1)

        sim_surf = pygame.Surface((sim_w, sim_h))

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q and not command_input.active:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    if selected:
                        selected.selected = False
                        selected = None
                elif event.key == pygame.K_SLASH and not command_input.active:
                    command_input.active = True
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    slider_x = sim_w + 20
                    slider_w = panel_w - 40
                    slider_y = win_h - 150
                    if slider_x <= mx <= slider_x + slider_w and slider_y-5 <= my <= slider_y+15:
                        dragging_slider = True
                        rel = (mx - slider_x) / slider_w
                        rel = clamp(rel, 0.0, 1.0)
                        log_min = math.log(0.01)
                        log_max = math.log(100.0)
                        log_val = log_min + rel * (log_max - log_min)
                        time_scale = math.exp(log_val)
                    elif mx < sim_w:
                        wx, wy = camera.screen_to_world(mx, my)
                        clicked = None
                        for e in world.entities:
                            if isinstance(e, (Animal, Plant)) and e.alive:
                                if dist([wx, wy], e.pos) < (e.size if hasattr(e,'size') else 30) + 10:
                                    clicked = e
                                    break
                        if selected:
                            selected.selected = False
                        selected = clicked
                        if selected:
                            selected.selected = True
                elif event.button == 2:
                    camera.dragging = True
                    camera.drag_start = event.pos
                    camera.drag_cam_start = (camera.x, camera.y)
                elif event.button == 4:
                    camera.zoom = min(ZOOM_MAX, camera.zoom * 1.1)
                elif event.button == 5:
                    camera.zoom = max(ZOOM_MIN, camera.zoom / 1.1)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging_slider = False
                elif event.button == 2:
                    camera.dragging = False
            elif event.type == pygame.MOUSEMOTION:
                if dragging_slider:
                    mx, my = event.pos
                    slider_x = sim_w + 20
                    slider_w = panel_w - 40
                    rel = (mx - slider_x) / slider_w
                    rel = clamp(rel, 0.0, 1.0)
                    log_min = math.log(0.01)
                    log_max = math.log(100.0)
                    log_val = log_min + rel * (log_max - log_min)
                    time_scale = math.exp(log_val)
                elif camera.dragging:
                    dx = event.pos[0] - camera.drag_start[0]
                    dy = event.pos[1] - camera.drag_start[1]
                    camera.x = camera.drag_cam_start[0] - dx / camera.zoom
                    camera.y = camera.drag_cam_start[1] - dy / camera.zoom
                    camera.x = clamp(camera.x, 0, WORLD_W)
                    camera.y = clamp(camera.y, 0, WORLD_H)

            cmd = command_input.handle_event(event)
            if cmd:
                cmd = cmd.lower().strip()
                if cmd == '/fire':
                    x = random.uniform(50, WORLD_W-50)
                    y = random.uniform(50, WORLD_H-50)
                    if not in_water([x,y], world.water_zones):
                        world.to_add.append(Fire(x, y))
                elif cmd.startswith('/summon '):
                    entity = cmd[8:].strip()
                    world.spawn_entity(entity)
                elif cmd == '/kill':
                    if selected and selected.alive:
                        selected.alive = False
                elif cmd.startswith('/temperature '):
                    try:
                        temp = float(cmd[13:].strip())
                        world.temperature = clamp(temp, 5, 55)
                    except ValueError:
                        pass
                elif cmd.startswith('/spawnrate '):
                    try:
                        rate = float(cmd[11:].strip())
                        world.spawn_rate = clamp(rate, 0.1, 10.0)
                    except ValueError:
                        pass

        # WASD camera movement (use raw dt, not time_scale affected)
        raw_dt = clock.get_rawtime() / 1000.0
        keys = pygame.key.get_pressed()
        camera.update_keys(raw_dt, keys, command_input.active)

        command_input.update(dt)
        if selected and not selected.alive:
            selected = None

        world.update(dt)

        animals = world.draw(sim_surf, camera)
        for a in animals:
            if camera.is_visible((a.pos[0]-a.size, a.pos[1]-a.size, a.size*2, a.size*2)):
                a.draw(sim_surf, camera, tiny_font)

        screen.fill((0,0,0))
        screen.blit(sim_surf, (0,0))

        panel_x = sim_w
        draw_panel(screen, world, selected, font, sfont, tiny_font, panel_x, world.time, time_scale, world.temperature, command_input)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
