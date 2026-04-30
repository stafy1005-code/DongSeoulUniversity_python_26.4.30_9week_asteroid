
"""
3인칭 후방 원근 시점 소행성 부수기 v6

주요 반영 사항
- 레벨 상승 기준: 보스 처치
- 등급(RANK): 기존 파괴 목표 진행 기능을 담당
- 등급 조건 달성 시 우주선 주변에 아이템 여러 개 생성
- 일반 별: 아주 작은 점/반짝임, 멀리 생성
- 최종 보스 별: 큰 발광 구체, 코로나 효과, 가까워지면 보스로 변환
- 외계인: UFO 형태, 초록/파랑 계열, 이동 및 공격 가능
- 아이템: 소행성처럼 가까이 오면 바로 습득, 랭크업 후 10초 자석 흡수
- 오브젝트 접근 속도 상향
- 조작: W/S 전후, A/D 좌우, Space 상승, Ctrl 하강, 마우스 발사
- 같은 폴더의 ship.png / rock.png 자동 사용

실행:
    pip install pygame
    python asteroid_pseudo3d_3rd_person.py

파일 배치:
    asteroid_pseudo3d_3rd_person.py
    ship.png
    rock.png
"""

import os
import sys
import math
import random
import pygame


# ============================================================
# 1. 기본 설정
# ============================================================
WIDTH = 1000
HEIGHT = 720
FPS = 60

CENTER_X = WIDTH // 2
CENTER_Y = HEIGHT // 2
HORIZON_Y = 245
PLAYER_SCREEN_Y = HEIGHT - 105

NEAR_Z = 34
OBJECT_FAR_Z = 1250
STAR_NEAR_Z = 900
STAR_FAR_Z = 5600
BOSS_STAR_START_Z = 3300
BOSS_STAR_TRIGGER_Z = 760
BOSS_HOLD_Z = 650
PROJECTION = 660

MAGNET_DURATION = FPS * 10
ENEMY_BULLET_SHOT_HIT_BONUS = 30
BOSS_BULLET_SHOT_HIT_BONUS = 26

WHITE = (245, 245, 245)
BLACK = (0, 0, 0)
DARK = (5, 8, 18)
PANEL = (24, 28, 45)
PANEL_2 = (38, 43, 67)
GRAY = (150, 150, 160)
RED = (235, 80, 90)
ORANGE = (255, 165, 70)
YELLOW = (255, 220, 90)
GREEN = (90, 230, 130)
CYAN = (80, 220, 255)
BLUE = (80, 130, 255)
PURPLE = (190, 110, 255)
PINK = (255, 120, 210)

DIFFICULTIES = {
    "쉬움": 0.8,
    "보통": 1.0,
    "어려움": 1.3,
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHIP_PATH = os.path.join(BASE_DIR, "ship.png")
ROCK_PATH = os.path.join(BASE_DIR, "rock.png")


# ============================================================
# 2. 유틸 함수
# ============================================================
def clamp(value, min_value, max_value):
    return max(min_value, min(max_value, value))


def safe_load_image(path):
    if os.path.exists(path):
        try:
            return pygame.image.load(path).convert_alpha()
        except pygame.error:
            return None
    return None


def get_font(size, bold=False):
    return pygame.font.SysFont(["malgungothic", "맑은 고딕", "arial"], size, bold=bold)


def draw_text(surface, text, size, x, y, color=WHITE, center=False, bold=False):
    font = get_font(size, bold)
    image = font.render(str(text), True, color)
    rect = image.get_rect()
    if center:
        rect.center = (int(x), int(y))
    else:
        rect.topleft = (int(x), int(y))
    surface.blit(image, rect)
    return rect


def wrap_text(text, font, max_width):
    lines = []
    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
            continue

        current = ""
        for ch in paragraph:
            test = current + ch
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def project_point(x, y, z, player, far_z=OBJECT_FAR_Z):
    """
    pseudo-3D 좌표를 2D 화면 좌표로 변환한다.
    player.world_x / world_y가 바뀌면 실제 3D 공간 속 사물이 옆으로 밀려 보인다.
    """
    z = max(NEAR_Z, z)
    perspective = PROJECTION / z
    depth_t = clamp((far_z - z) / (far_z - NEAR_Z), 0.0, 1.0)

    rel_x = x - player.world_x
    rel_y = y - player.world_y

    sx = CENTER_X + rel_x * perspective * 0.72
    base_y = HORIZON_Y + depth_t * (PLAYER_SCREEN_Y - HORIZON_Y)
    sy = base_y - rel_y * perspective * 0.45
    return sx, sy, depth_t, perspective


def circle_rect_hit(cx, cy, radius, rect):
    closest_x = clamp(cx, rect.left, rect.right)
    closest_y = clamp(cy, rect.top, rect.bottom)
    return math.hypot(cx - closest_x, cy - closest_y) <= radius


def draw_heart(surface, x, y, size, color):
    """목숨 UI용 하트 도형을 직접 그린다."""
    x = int(x)
    y = int(y)
    r = max(4, int(size * 0.28))
    pygame.draw.circle(surface, color, (x - r, y - r // 2), r)
    pygame.draw.circle(surface, color, (x + r, y - r // 2), r)
    points = [
        (x - r * 2, y - r // 2),
        (x + r * 2, y - r // 2),
        (x, y + int(size * 0.58)),
    ]
    pygame.draw.polygon(surface, color, points)
    pygame.draw.circle(surface, WHITE, (x - r, y - r // 2), r, 1)
    pygame.draw.circle(surface, WHITE, (x + r, y - r // 2), r, 1)


# ============================================================
# 3. UI 버튼 / 스크롤 팝업
# ============================================================
class Button:
    def __init__(self, text, rect, action):
        self.text = text
        self.rect = pygame.Rect(rect)
        self.action = action

    def draw(self, surface, mouse_pos):
        hovered = self.rect.collidepoint(mouse_pos)
        color = PANEL_2 if hovered else PANEL
        border = CYAN if hovered else GRAY
        pygame.draw.rect(surface, color, self.rect, border_radius=12)
        pygame.draw.rect(surface, border, self.rect, 2, border_radius=12)
        draw_text(surface, self.text, 24, self.rect.centerx, self.rect.centery, WHITE, center=True, bold=True)

    def is_clicked(self, event):
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )


class ScrollPopup:
    def __init__(self, title, text):
        self.title = title
        self.text = text
        self.scroll = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEWHEEL:
            self.scroll -= event.y * 38
            self.scroll = max(0, self.scroll)

    def draw(self, surface):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        surface.blit(overlay, (0, 0))

        panel_rect = pygame.Rect(120, 70, WIDTH - 240, HEIGHT - 140)
        pygame.draw.rect(surface, PANEL, panel_rect, border_radius=18)
        pygame.draw.rect(surface, CYAN, panel_rect, 2, border_radius=18)

        draw_text(surface, self.title, 34, panel_rect.centerx, panel_rect.y + 35, CYAN, center=True, bold=True)
        draw_text(surface, "마우스 휠: 스크롤 / ESC: 뒤로", 18, panel_rect.centerx, panel_rect.y + 75, GRAY, center=True)

        content_rect = pygame.Rect(panel_rect.x + 30, panel_rect.y + 110, panel_rect.width - 60, panel_rect.height - 140)
        pygame.draw.rect(surface, (16, 19, 32), content_rect, border_radius=12)

        font = get_font(20)
        lines = wrap_text(self.text, font, content_rect.width - 28)
        line_h = 30
        content_h = len(lines) * line_h
        max_scroll = max(0, content_h - content_rect.height + 20)
        self.scroll = clamp(self.scroll, 0, max_scroll)

        old_clip = surface.get_clip()
        surface.set_clip(content_rect)
        y = content_rect.y + 14 - self.scroll
        for line in lines:
            if content_rect.y - line_h <= y <= content_rect.bottom + line_h:
                img = font.render(line, True, WHITE)
                surface.blit(img, (content_rect.x + 14, y))
            y += line_h
        surface.set_clip(old_clip)

        if content_h > content_rect.height:
            bar_h = max(40, int(content_rect.height * content_rect.height / content_h))
            bar_y = content_rect.y + int((content_rect.height - bar_h) * self.scroll / max_scroll)
            pygame.draw.rect(surface, (70, 75, 100), (content_rect.right - 10, content_rect.y, 6, content_rect.height), border_radius=3)
            pygame.draw.rect(surface, CYAN, (content_rect.right - 10, bar_y, 6, bar_h), border_radius=3)


# ============================================================
# 4. 배경 일반 별
# ============================================================
class BackgroundStar:
    COLORS = [
        (255, 255, 255),
        (220, 235, 255),
        (185, 215, 255),
        (255, 245, 210),
    ]

    def __init__(self):
        self.reset(random_z=True)

    def reset(self, random_z=False):
        self.x = random.uniform(-2800, 2800)
        self.y = random.uniform(-1600, 1600)
        self.z = random.uniform(STAR_NEAR_Z, STAR_FAR_Z) if random_z else STAR_FAR_Z
        self.radius = random.choice([1, 1, 1, 1, 2])
        self.color = random.choice(self.COLORS)
        self.alpha = random.randint(120, 255)
        self.twinkle_speed = random.uniform(0.015, 0.06)
        self.offset = random.uniform(0, math.tau)

    def update(self, player):
        # 별은 매우 멀리 있으므로 천천히만 흐른다.
        self.z -= max(0.0, player.velocity_z) * 0.18 + 0.18
        if self.z < STAR_NEAR_Z:
            self.reset(random_z=False)

    def draw(self, surface, player, offset=(0, 0)):
        # 배경 별은 멀리 있으므로 player 이동 반영을 약하게 적용한다.
        rel_x = self.x - player.world_x * 0.38
        rel_y = self.y - player.world_y * 0.38
        perspective = PROJECTION / max(STAR_NEAR_Z, self.z)
        sx = CENTER_X + rel_x * perspective
        sy = HORIZON_Y - 30 - rel_y * perspective * 0.6

        if sx < -20 or sx > WIDTH + 20 or sy < -20 or sy > HEIGHT + 20:
            return

        time_value = pygame.time.get_ticks() * 0.01
        twinkle = math.sin(time_value * self.twinkle_speed + self.offset)
        alpha = clamp(self.alpha + int(twinkle * 45), 70, 255)
        radius = self.radius
        color = self.color

        star_surf = pygame.Surface((radius * 8, radius * 8), pygame.SRCALPHA)
        center = (star_surf.get_width() // 2, star_surf.get_height() // 2)
        pygame.draw.circle(star_surf, (color[0], color[1], color[2], int(alpha * 0.16)), center, radius * 3)
        pygame.draw.circle(star_surf, (color[0], color[1], color[2], alpha), center, radius)
        surface.blit(star_surf, (int(sx - star_surf.get_width() // 2 + offset[0]), int(sy - star_surf.get_height() // 2 + offset[1])))


# ============================================================
# 5. 파티클
# ============================================================
class Particle:
    def __init__(self, x, y, color, mode="hit"):
        self.x = x
        self.y = y
        angle = random.uniform(0, math.tau)
        speed = random.uniform(2.0, 8.0) if mode == "hit" else random.uniform(1.2, 5.5)
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life = random.randint(18, 44)
        self.max_life = self.life
        self.color = color
        self.radius = random.randint(2, 5)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.92
        self.vy *= 0.92
        self.life -= 1

    def draw(self, surface, offset=(0, 0)):
        if self.life <= 0:
            return
        t = self.life / self.max_life
        r = max(1, int(self.radius * t))
        pygame.draw.circle(surface, self.color, (int(self.x + offset[0]), int(self.y + offset[1])), r)


# ============================================================
# 6. 플레이어
# ============================================================
class Player:
    def __init__(self, ship_image):
        self.ship_image = ship_image
        self.reset()

    def reset(self):
        self.world_x = 0.0
        self.world_y = 0.0
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_z = 0.0

        self.max_side_speed = 13.0
        self.max_vertical_speed = 9.0
        self.max_forward_speed = 12.5
        self.max_backward_speed = -4.5

        self.lives = 3
        self.shield = 0
        self.attack_count = 1
        self.attack_speed_level = 0
        self.missiles = 0
        self.invincible = 0
        self.shield_burst = 0
        self.hit_blink = 0

    @property
    def screen_pos(self):
        # 우주선은 기본적으로 화면 아래쪽에 보이고, 이동값에 따라 조금 움직인다.
        sx = CENTER_X + self.world_x * 0.11
        sy = PLAYER_SCREEN_Y - self.world_y * 0.10
        return sx, sy

    def get_rect(self):
        sx, sy = self.screen_pos
        return pygame.Rect(int(sx - 36), int(sy - 28), 72, 56)

    def update(self, keys):
        ax = 0.0
        ay = 0.0
        az = 0.0

        if keys[pygame.K_a]:
            ax -= 0.85
        if keys[pygame.K_d]:
            ax += 0.85
        if keys[pygame.K_SPACE]:
            ay += 0.72
        if keys[pygame.K_LCTRL] or keys[pygame.K_RCTRL]:
            ay -= 0.72
        if keys[pygame.K_w]:
            az += 0.72
        if keys[pygame.K_s]:
            az -= 0.48

        self.velocity_x += ax
        self.velocity_y += ay
        self.velocity_z += az

        self.velocity_x *= 0.935
        self.velocity_y *= 0.935
        self.velocity_z *= 0.94

        self.velocity_x = clamp(self.velocity_x, -self.max_side_speed, self.max_side_speed)
        self.velocity_y = clamp(self.velocity_y, -self.max_vertical_speed, self.max_vertical_speed)
        self.velocity_z = clamp(self.velocity_z, self.max_backward_speed, self.max_forward_speed)

        self.world_x += self.velocity_x
        self.world_y += self.velocity_y

        # 좌우/상하 이동 범위는 넓게 허용한다.
        self.world_x = clamp(self.world_x, -760, 760)
        self.world_y = clamp(self.world_y, -420, 420)

        if self.invincible > 0:
            self.invincible -= 1
        if self.shield_burst > 0:
            self.shield_burst -= 1
        if self.hit_blink > 0:
            self.hit_blink -= 1

    def damage(self, game):
        if self.invincible > 0:
            return

        self.invincible = 75
        self.hit_blink = 24
        game.shake_frames = 22
        game.flash_frames = 18

        px, py = self.screen_pos
        for _ in range(35):
            game.particles.append(Particle(px, py, RED, "hit"))

        if self.shield > 0:
            self.shield -= 1
            self.shield_burst = 35
            for _ in range(45):
                game.particles.append(Particle(px, py, CYAN, "shield"))
            return

        self.lives -= 1
        if self.lives <= 0:
            game.state = "GAME_OVER"

    def apply_item(self, item_type):
        if item_type == "shield":
            self.shield = clamp(self.shield + 1, 0, 5)
            self.shield_burst = 35
        elif item_type == "attack":
            self.attack_count = clamp(self.attack_count + 1, 1, 5)
        elif item_type == "life":
            # 최대 목숨 제한 없이 하트가 늘어난다.
            self.lives += 1
        elif item_type == "speed":
            # 공격 속도 증가. 숫자가 커질수록 발사 쿨타임이 짧아진다.
            self.attack_speed_level = clamp(self.attack_speed_level + 1, 0, 7)
        elif item_type == "missile":
            # 파란색 미사일 아이템. 한 번 먹으면 미사일 3발 충전.
            self.missiles += 3

    def draw(self, surface, mouse_pos, offset=(0, 0)):
        sx, sy = self.screen_pos
        sx += offset[0]
        sy += offset[1]

        if self.invincible > 0 and (self.invincible // 5) % 2 == 0:
            return

        angle = math.degrees(math.atan2(mouse_pos[1] - sy, mouse_pos[0] - sx))

        if self.ship_image is not None:
            base = pygame.transform.smoothscale(self.ship_image, (84, 84))
            rotated = pygame.transform.rotate(base, -angle - 90)
            rect = rotated.get_rect(center=(sx, sy))
            surface.blit(rotated, rect)
        else:
            rad = math.radians(angle)
            front = (sx + math.cos(rad) * 40, sy + math.sin(rad) * 40)
            left = (sx + math.cos(rad + 2.45) * 34, sy + math.sin(rad + 2.45) * 34)
            right = (sx + math.cos(rad - 2.45) * 34, sy + math.sin(rad - 2.45) * 34)
            pygame.draw.polygon(surface, CYAN, [front, left, right])
            pygame.draw.polygon(surface, WHITE, [front, left, right], 2)

        if self.shield > 0:
            radius = 50 + int(math.sin(pygame.time.get_ticks() * 0.012) * 3)
            pygame.draw.circle(surface, CYAN, (int(sx), int(sy)), radius, 2)

        if self.shield_burst > 0:
            radius = 52 + (35 - self.shield_burst) * 3
            pygame.draw.circle(surface, CYAN, (int(sx), int(sy)), radius, 3)

        if self.hit_blink > 0:
            pygame.draw.circle(surface, RED, (int(sx), int(sy)), 56, 3)


# ============================================================
# 7. 총알
# ============================================================
class Shot:
    def __init__(self, start_pos, target_pos, offset_index=0, total=1, boss_snipe=False):
        self.x, self.y = start_pos
        tx, ty = target_pos
        dx = tx - self.x
        dy = ty - self.y
        length = math.hypot(dx, dy)
        if length == 0:
            dx, dy, length = 0, -1, 1

        nx = dx / length
        ny = dy / length
        px = -ny
        py = nx

        spread = 13
        center_offset = offset_index - (total - 1) / 2
        self.x += px * center_offset * spread
        self.y += py * center_offset * spread

        self.vx = nx * 20.5 + px * center_offset * 0.9
        self.vy = ny * 20.5 + py * center_offset * 0.9
        self.life = 60
        self.radius = 5
        self.alive = True
        self.boss_snipe = boss_snipe

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0 or self.x < -100 or self.x > WIDTH + 100 or self.y < -100 or self.y > HEIGHT + 100:
            self.alive = False

    def get_rect(self):
        return pygame.Rect(int(self.x - self.radius), int(self.y - self.radius), self.radius * 2, self.radius * 2)

    def draw(self, surface, offset=(0, 0)):
        x = int(self.x + offset[0])
        y = int(self.y + offset[1])
        color = PINK if self.boss_snipe else YELLOW
        pygame.draw.circle(surface, color, (x, y), self.radius)
        pygame.draw.circle(surface, WHITE, (x, y), self.radius + 2, 1)
        if self.boss_snipe:
            pygame.draw.circle(surface, PINK, (x, y), self.radius + 6, 1)




class Missile:
    def __init__(self, start_pos):
        self.x, self.y = start_pos
        self.vx = 0.0
        self.vy = -10.0
        self.speed = 12.0
        self.turn_rate = 0.13
        self.radius = 9
        self.life = 150
        self.alive = True
        self.trail = []

    def find_target(self, game):
        candidates = []
        # v6: 보스는 우클릭을 누른 상태에서 좌클릭 저격탄으로만 피해를 받는다.
        # 미사일은 일반 운석, 외계인, 붉은 공 정리에 사용한다.
        for obj in game.objects:
            if not obj.alive or obj.kind not in ("rock", "alien"):
                continue
            rect = obj.get_screen_rect(game.player)
            candidates.append((rect.centerx, rect.centery, 1.0))
        for bullet in game.enemy_bullets:
            if bullet.alive:
                candidates.append((bullet.x, bullet.y, 0.75))
        if not candidates:
            return None
        return min(candidates, key=lambda c: math.hypot(c[0] - self.x, c[1] - self.y) * c[2])

    def update(self, game):
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return
        target = self.find_target(game)
        if target is not None:
            tx, ty, _ = target
            dx = tx - self.x
            dy = ty - self.y
            dist = math.hypot(dx, dy) or 1
            desired_vx = dx / dist * self.speed
            desired_vy = dy / dist * self.speed
            self.vx += (desired_vx - self.vx) * self.turn_rate
            self.vy += (desired_vy - self.vy) * self.turn_rate
        self.x += self.vx
        self.y += self.vy
        self.trail.append((self.x, self.y))
        if len(self.trail) > 12:
            self.trail.pop(0)
        if self.x < -160 or self.x > WIDTH + 160 or self.y < -160 or self.y > HEIGHT + 160:
            self.alive = False

    def get_rect(self):
        return pygame.Rect(int(self.x - self.radius), int(self.y - self.radius), self.radius * 2, self.radius * 2)

    def draw(self, surface, offset=(0, 0)):
        for i, pos in enumerate(self.trail):
            alpha_size = max(2, int(self.radius * (i + 1) / max(1, len(self.trail))))
            pygame.draw.circle(surface, BLUE, (int(pos[0] + offset[0]), int(pos[1] + offset[1])), alpha_size)
        x = int(self.x + offset[0])
        y = int(self.y + offset[1])
        pygame.draw.circle(surface, BLUE, (x, y), self.radius + 3)
        pygame.draw.circle(surface, CYAN, (x, y), self.radius)
        pygame.draw.circle(surface, WHITE, (x, y), self.radius + 4, 1)

# ============================================================
# 8. 운석 / 아이템 / 외계인 UFO
# ============================================================
class SpaceObject:
    def __init__(self, kind, rank, difficulty_mul, rock_image=None, forced_pos=None, size=None):
        self.kind = kind
        self.rank = rank
        self.difficulty_mul = difficulty_mul
        self.rock_image = rock_image
        self.alive = True
        self.rotation = random.randint(0, 359)
        self.rot_speed = random.uniform(-4, 4)
        self.phase = random.uniform(0, math.tau)
        self.shoot_timer = random.randint(90, 160)

        if forced_pos:
            self.x, self.y, self.z = forced_pos
        else:
            self.x = random.uniform(-690, 690)
            self.y = random.uniform(-360, 300)
            self.z = random.uniform(OBJECT_FAR_Z * 0.72, OBJECT_FAR_Z)

        if self.kind == "rock":
            self.base_size = size if size is not None else random.randint(45, 82)
            self.speed = random.uniform(4.8, 8.2) * difficulty_mul + rank * 0.22
            self.hp = 1
        elif self.kind == "alien":
            self.base_size = size if size is not None else random.randint(82, 112)
            self.speed = random.uniform(3.8, 6.2) * difficulty_mul + rank * 0.18
            self.hp = 3 + rank // 2
            self.max_hp = self.hp
        elif self.kind in ("shield", "attack", "life", "speed", "missile"):
            self.base_size = 48 if self.kind != "missile" else 52
            self.speed = 5.3 * difficulty_mul
            self.hp = 1
        else:
            self.base_size = 42
            self.speed = 5.0 * difficulty_mul
            self.hp = 1

    def update(self, game):
        player_forward = max(0.0, game.player.velocity_z)
        player_backward = min(0.0, game.player.velocity_z)
        self.z -= self.speed + player_forward * 0.75 + player_backward * 0.25
        self.rotation += self.rot_speed

        if self.kind == "alien":
            self.phase += 0.055
            self.x += math.sin(self.phase) * 2.2
            self.y += math.cos(self.phase * 1.4) * 0.7
            self.shoot_timer -= 1
            if self.shoot_timer <= 0 and self.z < 900:
                self.shoot_timer = max(48, 130 - game.rank * 4) + random.randint(0, 35)
                sx, sy, size, _ = self.projection(game.player)
                px, py = game.player.screen_pos
                game.enemy_bullets.append(EnemyBullet((sx, sy), (px, py), speed=5.8 + game.rank * 0.12))

        if self.z <= NEAR_Z - 10:
            self.alive = False

    def projection(self, player):
        sx, sy, depth_t, _ = project_point(self.x, self.y, self.z, player)
        scale = 0.38 + depth_t * 2.15
        size = max(10, int(self.base_size * scale))
        return sx, sy, size, depth_t

    def get_screen_rect(self, player):
        sx, sy, size, _ = self.projection(player)
        return pygame.Rect(int(sx - size / 2), int(sy - size / 2), size, size)

    def hit(self, damage=1):
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def draw(self, surface, player, offset=(0, 0)):
        sx, sy, size, depth_t = self.projection(player)
        sx += offset[0]
        sy += offset[1]

        if sx < -190 or sx > WIDTH + 190 or sy < -190 or sy > HEIGHT + 190:
            return

        aligned_with_player_y = (
            self.kind == "rock" or self.kind in ("shield", "attack", "life", "speed", "missile")
        ) and abs(self.y - player.world_y) <= 62

        if aligned_with_player_y:
            self.draw_same_height_glow(surface, sx, sy, size)

        if self.kind in ("rock", "alien"):
            shadow_w = int(size * 1.05)
            shadow_h = max(4, int(size * 0.18))
            pygame.draw.ellipse(surface, (0, 0, 0), (sx - shadow_w / 2, sy + size * 0.36, shadow_w, shadow_h))

        if self.kind == "rock":
            if self.rock_image is not None:
                img = pygame.transform.smoothscale(self.rock_image, (size, size))
                img = pygame.transform.rotate(img, self.rotation)
                rect = img.get_rect(center=(sx, sy))
                surface.blit(img, rect)
            else:
                pygame.draw.circle(surface, (105, 105, 118), (int(sx), int(sy)), size // 2)
                pygame.draw.circle(surface, (180, 180, 195), (int(sx - size * 0.12), int(sy - size * 0.14)), max(2, size // 9))
                pygame.draw.circle(surface, (65, 65, 76), (int(sx + size * 0.15), int(sy + size * 0.08)), max(2, size // 8))
                pygame.draw.circle(surface, WHITE, (int(sx), int(sy)), size // 2, 1)

        elif self.kind == "alien":
            self.draw_alien(surface, sx, sy, size)

        elif self.kind == "shield":
            pulse = int(math.sin(pygame.time.get_ticks() * 0.012) * 4)
            pygame.draw.circle(surface, CYAN, (int(sx), int(sy)), size // 2 + pulse, 4)
            pygame.draw.circle(surface, BLUE, (int(sx), int(sy)), size // 3, 2)
            draw_text(surface, "S", max(18, size // 2), sx, sy - size * 0.05, CYAN, center=True, bold=True)

        elif self.kind == "attack":
            pulse = int(math.sin(pygame.time.get_ticks() * 0.014) * 4)
            pygame.draw.circle(surface, YELLOW, (int(sx), int(sy)), size // 2 + pulse, 4)
            draw_text(surface, "+", max(24, size // 2), sx, sy - size * 0.1, YELLOW, center=True, bold=True)

        elif self.kind == "life":
            pulse = int(math.sin(pygame.time.get_ticks() * 0.013) * 4)
            pygame.draw.circle(surface, PINK, (int(sx), int(sy)), size // 2 + pulse, 4)
            draw_heart(surface, sx, sy - size * 0.04, max(20, size // 2), RED)

        elif self.kind == "speed":
            pulse = int(math.sin(pygame.time.get_ticks() * 0.017) * 4)
            pygame.draw.circle(surface, GREEN, (int(sx), int(sy)), size // 2 + pulse, 4)
            draw_text(surface, "F", max(20, size // 2), sx, sy - size * 0.1, GREEN, center=True, bold=True)

        elif self.kind == "missile":
            pulse = int(math.sin(pygame.time.get_ticks() * 0.016) * 4)
            pygame.draw.circle(surface, BLUE, (int(sx), int(sy)), size // 2 + pulse, 4)
            pygame.draw.polygon(surface, CYAN, [
                (sx, sy - size * 0.32),
                (sx + size * 0.22, sy + size * 0.25),
                (sx, sy + size * 0.12),
                (sx - size * 0.22, sy + size * 0.25),
            ])
            draw_text(surface, "M", max(16, size // 3), sx, sy + size * 0.34, WHITE, center=True, bold=True)

    def draw_same_height_glow(self, surface, sx, sy, size):
        # 플레이어와 상하 위치가 거의 같은 아이템/소행성은 노란 테두리로 표시한다.
        # 3D 원근에서 높이가 헷갈리는 문제를 줄이기 위한 보조 표시다.
        pulse = 4 + int(math.sin(pygame.time.get_ticks() * 0.018) * 3)
        glow_size = int(size * 1.18 + pulse)
        glow = pygame.Surface((glow_size * 2 + 24, glow_size * 2 + 24), pygame.SRCALPHA)
        gx = glow.get_width() // 2
        gy = glow.get_height() // 2
        pygame.draw.circle(glow, (255, 225, 80, 42), (gx, gy), glow_size)
        pygame.draw.circle(glow, (255, 230, 95, 190), (gx, gy), max(8, int(size * 0.62)), max(2, size // 28))
        surface.blit(glow, (int(sx - gx), int(sy - gy)))

    def draw_alien(self, surface, sx, sy, size):
        # 크고 눈에 띄는 UFO: 초록/파랑 계열, 돔과 빔을 가진 형태
        body_rect = pygame.Rect(0, 0, int(size * 1.1), int(size * 0.34))
        body_rect.center = (int(sx), int(sy + size * 0.08))
        pygame.draw.ellipse(surface, (95, 210, 170), body_rect)
        pygame.draw.ellipse(surface, WHITE, body_rect, 2)

        dome_rect = pygame.Rect(0, 0, int(size * 0.58), int(size * 0.42))
        dome_rect.center = (int(sx), int(sy - size * 0.10))
        pygame.draw.ellipse(surface, (85, 175, 255), dome_rect)
        pygame.draw.ellipse(surface, WHITE, dome_rect, 2)

        light_count = 5
        for i in range(light_count):
            lx = sx - size * 0.35 + i * (size * 0.7 / (light_count - 1))
            ly = sy + size * 0.13
            pygame.draw.circle(surface, random.choice([CYAN, GREEN, YELLOW]), (int(lx), int(ly)), max(2, size // 22))

        beam_h = size * 0.28 + math.sin(self.phase * 2.2) * size * 0.04
        beam_points = [
            (sx - size * 0.22, sy + size * 0.22),
            (sx + size * 0.22, sy + size * 0.22),
            (sx + size * 0.10, sy + size * 0.22 + beam_h),
            (sx - size * 0.10, sy + size * 0.22 + beam_h),
        ]
        beam_surf = pygame.Surface((int(size), int(size)), pygame.SRCALPHA)
        shifted = [(int(x - sx + size / 2), int(y - sy + size / 2)) for x, y in beam_points]
        pygame.draw.polygon(beam_surf, (90, 255, 180, 85), shifted)
        surface.blit(beam_surf, (int(sx - size / 2), int(sy - size / 2)))

        if self.hp > 1:
            bar_w = int(size * 0.85)
            bar_x = int(sx - bar_w / 2)
            bar_y = int(sy - size * 0.55)
            pygame.draw.rect(surface, (80, 20, 30), (bar_x, bar_y, bar_w, 6))
            pygame.draw.rect(surface, GREEN, (bar_x, bar_y, int(bar_w * self.hp / self.max_hp), 6))


# ============================================================
# 9. 보스 별 / 보스 탄환
# ============================================================
class BossStar:
    def __init__(self, level, difficulty_mul):
        self.level = level
        self.difficulty_mul = difficulty_mul
        self.x = 0.0
        self.y = 12.0
        self.z = BOSS_STAR_START_Z
        self.radius_world = 720
        self.phase = random.uniform(0, math.tau)
        self.mode = "approach"  # approach -> boss
        self.max_hp = 70 + level * 22
        self.hp = self.max_hp
        self.shoot_timer = 100
        self.transform_timer = 0
        self.big_attack_toggle = False
        self.alive = True

    def update(self, game):
        self.phase += 0.035

        if self.mode == "approach":
            # 플레이어가 W로 전진하면 더 빠르게 가까워진다.
            self.z -= 0.75 + max(0.0, game.player.velocity_z) * 0.82
            self.z = max(self.z, BOSS_STAR_TRIGGER_Z)
            if self.z <= BOSS_STAR_TRIGGER_Z + 2:
                self.mode = "boss"
                self.transform_timer = 120
                game.shake_frames = 44
                game.flash_frames = 26
                sx, sy, radius = self.projection(game.player)
                for _ in range(130):
                    game.particles.append(Particle(sx, sy, RED if random.random() < 0.55 else ORANGE, "hit"))
        else:
            # 보스는 플레이어에게 계속 다가오지 않고 앞쪽 한계 위치에 고정된다.
            self.z = BOSS_HOLD_Z
            self.x = math.sin(self.phase) * 230
            self.y = 25 + math.sin(self.phase * 1.7) * 95

            if self.transform_timer > 0:
                self.transform_timer -= 1

            self.shoot_timer -= 1
            if self.shoot_timer <= 0:
                self.shoot_timer = max(34, 84 - self.level * 4)
                sx, sy, radius = self.projection(game.player)
                px, py = game.player.screen_pos

                for spread in (-0.18, 0.0, 0.18):
                    target = (px + math.cos(self.phase + spread) * 70, py + math.sin(self.phase + spread) * 45)
                    game.enemy_bullets.append(EnemyBullet((sx, sy), target, speed=6.1 + self.level * 0.17, radius=13, source="boss"))

                self.big_attack_toggle = not self.big_attack_toggle
                if self.big_attack_toggle:
                    game.enemy_bullets.append(EnemyBullet((sx, sy), (px, py), speed=4.9 + self.level * 0.12, radius=28, hp=2, source="boss_big"))

    def projection(self, player):
        sx, sy, depth_t, perspective = project_point(self.x, self.y, self.z, player, far_z=BOSS_STAR_START_Z)
        radius = max(60, int(self.radius_world * perspective * (0.74 + depth_t * 0.35)))
        return sx, sy, radius

    def get_screen_rect(self, player):
        sx, sy, radius = self.projection(player)
        return pygame.Rect(int(sx - radius * 0.65), int(sy - radius * 0.65), int(radius * 1.3), int(radius * 1.3))

    def get_snipe_rect(self, player):
        # v6: 일반 탄이 보스의 넓은 피격 범위에 빨려 들어가지 않게,
        # 우클릭+좌클릭 저격탄만 이 작은 중심 약점 판정으로 보스를 때린다.
        sx, sy, radius = self.projection(player)
        weak_w = max(42, int(radius * 0.42))
        weak_h = max(34, int(radius * 0.32))
        return pygame.Rect(int(sx - weak_w / 2), int(sy - radius * 0.24 - weak_h / 2), weak_w, weak_h)

    def hit(self, damage, game):
        if self.mode != "boss":
            return False

        self.hp -= damage
        sx, sy, radius = self.projection(game.player)
        for _ in range(18):
            game.particles.append(Particle(sx + random.uniform(-radius * 0.3, radius * 0.3), sy + random.uniform(-radius * 0.3, radius * 0.3), YELLOW, "hit"))

        if self.hp <= 0:
            self.alive = False
            game.score += 1500 + self.level * 350
            for _ in range(160):
                game.particles.append(Particle(sx, sy, ORANGE, "hit"))
            return True
        return False

    def draw(self, surface, player, offset=(0, 0)):
        sx, sy, radius = self.projection(player)
        sx += offset[0]
        sy += offset[1]

        if self.mode == "boss":
            self.draw_boss_alien(surface, sx, sy, radius)
            self.draw_hp_bar(surface)
            return

        self.draw_star_form(surface, sx, sy, radius)

    def draw_star_form(self, surface, sx, sy, radius):
        r = int(radius)
        pulse = math.sin(self.phase * 2.0) * max(5, r * 0.045)
        outer_r = int(r + r * 0.38 + pulse)
        mid_r = int(r + r * 0.18 + pulse * 0.45)
        core_r = r
        glow = pygame.Surface((outer_r * 2 + 40, outer_r * 2 + 40), pygame.SRCALPHA)
        gcx = glow.get_width() // 2
        gcy = glow.get_height() // 2
        pygame.draw.circle(glow, (255, 210, 100, 28), (gcx, gcy), outer_r)
        pygame.draw.circle(glow, (255, 190, 75, 70), (gcx, gcy), mid_r)
        pygame.draw.circle(glow, (255, 165, 60, 245), (gcx, gcy), core_r)
        pygame.draw.circle(glow, (255, 245, 190, 255), (gcx - int(r * 0.18), gcy - int(r * 0.18)), max(6, int(core_r * 0.42)))
        surface.blit(glow, (int(sx - gcx), int(sy - gcy)))
        for i in range(18):
            angle = math.radians(i * 20 + pygame.time.get_ticks() * 0.025)
            x1 = sx + math.cos(angle) * (r * 0.86)
            y1 = sy + math.sin(angle) * (r * 0.86)
            x2 = sx + math.cos(angle) * (r * 1.15 + pulse)
            y2 = sy + math.sin(angle) * (r * 1.15 + pulse)
            pygame.draw.line(surface, (255, 220, 125), (x1, y1), (x2, y2), max(1, r // 80))

    def draw_boss_alien(self, surface, sx, sy, radius):
        r = int(radius)
        transform_t = self.transform_timer / 120 if self.transform_timer > 0 else 0
        pulse = math.sin(self.phase * 2.7) * max(4, r * 0.035)
        glow_r = int(r * (1.22 + transform_t * 0.36) + pulse)
        glow = pygame.Surface((glow_r * 2 + 60, glow_r * 2 + 60), pygame.SRCALPHA)
        gcx = glow.get_width() // 2
        gcy = glow.get_height() // 2
        pygame.draw.circle(glow, (255, 45, 45, 42 + int(transform_t * 48)), (gcx, gcy), glow_r)
        pygame.draw.circle(glow, (255, 90, 70, 78), (gcx, gcy), int(glow_r * 0.72))
        surface.blit(glow, (int(sx - gcx), int(sy - gcy)))

        body_rect = pygame.Rect(0, 0, int(r * 1.75), int(r * 0.62))
        body_rect.center = (int(sx), int(sy + r * 0.14))
        pygame.draw.ellipse(surface, (165, 45, 65), body_rect)
        pygame.draw.ellipse(surface, (255, 185, 165), body_rect, max(2, r // 70))

        head_rect = pygame.Rect(0, 0, int(r * 1.08), int(r * 0.88))
        head_rect.center = (int(sx), int(sy - r * 0.18))
        pygame.draw.ellipse(surface, (190, 58, 72), head_rect)
        pygame.draw.ellipse(surface, WHITE, head_rect, max(2, r // 80))

        eye_w = max(10, int(r * 0.18))
        eye_h = max(7, int(r * 0.09))
        for side in (-1, 1):
            eye = pygame.Rect(0, 0, eye_w, eye_h)
            eye.center = (int(sx + side * r * 0.23), int(sy - r * 0.23))
            pygame.draw.ellipse(surface, (255, 235, 170), eye)
            pygame.draw.ellipse(surface, RED, eye, 2)

        beam_h = r * 0.42 + math.sin(self.phase * 2.0) * r * 0.08
        beam_points = [
            (sx - r * 0.30, sy + r * 0.42),
            (sx + r * 0.30, sy + r * 0.42),
            (sx + r * 0.13, sy + r * 0.42 + beam_h),
            (sx - r * 0.13, sy + r * 0.42 + beam_h),
        ]
        beam_surf = pygame.Surface((int(r * 1.2), int(r * 1.0)), pygame.SRCALPHA)
        shifted = [(int(x - sx + r * 0.6), int(y - sy + r * 0.5)) for x, y in beam_points]
        pygame.draw.polygon(beam_surf, (255, 60, 65, 95), shifted)
        surface.blit(beam_surf, (int(sx - r * 0.6), int(sy - r * 0.5)))

        for i in range(14):
            angle = math.radians(i * 360 / 14 + pygame.time.get_ticks() * 0.035)
            x1 = sx + math.cos(angle) * (r * 0.62)
            y1 = sy + math.sin(angle) * (r * 0.36)
            x2 = sx + math.cos(angle) * (r * (0.86 + transform_t * 0.28))
            y2 = sy + math.sin(angle) * (r * (0.52 + transform_t * 0.18))
            pygame.draw.line(surface, (255, 95, 80), (x1, y1), (x2, y2), max(1, r // 90))

    def draw_hp_bar(self, surface):
        bar_w = 430
        bar_x = CENTER_X - bar_w // 2
        bar_y = 28
        pygame.draw.rect(surface, (70, 20, 25), (bar_x, bar_y, bar_w, 20), border_radius=8)
        pygame.draw.rect(surface, RED, (bar_x, bar_y, int(bar_w * self.hp / self.max_hp), 20), border_radius=8)
        pygame.draw.rect(surface, WHITE, (bar_x, bar_y, bar_w, 20), 2, border_radius=8)
        draw_text(surface, f"BOSS ALIEN HP {self.hp}/{self.max_hp}", 18, CENTER_X, bar_y - 2, WHITE, center=True, bold=True)


class EnemyBullet:
    def __init__(self, start_pos, target_pos, speed=6.0, radius=9, hp=1, source="alien"):
        self.x, self.y = start_pos
        tx, ty = target_pos
        dx = tx - self.x
        dy = ty - self.y
        length = math.hypot(dx, dy)
        if length == 0:
            length = 1
        self.vx = dx / length * speed
        self.vy = dy / length * speed
        self.radius = radius
        self.hp = hp
        self.source = source
        self.life = 155
        self.alive = True

    @property
    def shot_hit_radius(self):
        bonus = BOSS_BULLET_SHOT_HIT_BONUS if self.source.startswith("boss") else ENEMY_BULLET_SHOT_HIT_BONUS
        return self.radius + bonus

    def hit(self, damage=1):
        self.hp -= damage
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def update(self, game):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        if self.life <= 0:
            self.alive = False
            return
        if circle_rect_hit(self.x, self.y, self.radius, game.player.get_rect()):
            self.alive = False
            game.player.damage(game)

    def draw(self, surface, offset=(0, 0)):
        x = int(self.x + offset[0])
        y = int(self.y + offset[1])
        if self.source == "boss_big":
            pygame.draw.circle(surface, (120, 15, 25), (x, y), self.radius + 10)
            pygame.draw.circle(surface, RED, (x, y), self.radius)
            pygame.draw.circle(surface, ORANGE, (x - self.radius // 3, y - self.radius // 3), max(4, self.radius // 3))
            pygame.draw.circle(surface, WHITE, (x, y), self.shot_hit_radius, 1)
        else:
            pygame.draw.circle(surface, RED, (x, y), self.radius)
            pygame.draw.circle(surface, ORANGE, (x, y), self.radius + 4, 2)
            pygame.draw.circle(surface, (255, 130, 120), (x, y), self.shot_hit_radius, 1)


# ============================================================
# 10. 게임 본체
# ============================================================
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("3인칭 원근 시점 소행성 부수기 v6")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()

        self.ship_image = safe_load_image(SHIP_PATH)
        self.rock_image = safe_load_image(ROCK_PATH)

        self.settings = {
            "difficulty": "보통",
            "start_level": 1,
            "r_restart": True,
        }

        self.state = "PLAYING"
        self.player = Player(self.ship_image)

        self.stars = [BackgroundStar() for _ in range(260)]
        self.objects = []
        self.shots = []
        self.missiles = []
        self.enemy_bullets = []
        self.particles = []
        self.boss_star = None

        self.score = 0
        self.level = 1
        self.rank = 1
        self.rank_progress = 0
        self.rank_goal = 10

        self.shot_cooldown = 0
        self.missile_cooldown = 0
        self.magnet_timer = 0

        self.shake_frames = 0
        self.flash_frames = 0

        self.help_popup = ScrollPopup("도움말", self.help_text())
        self.menu_buttons = []
        self.settings_buttons = []
        self.build_menu_buttons()
        self.build_settings_buttons()

        self.reset_game()

    def difficulty_mul(self):
        return DIFFICULTIES[self.settings["difficulty"]]

    def reset_game(self):
        self.state = "PLAYING"
        self.player.reset()
        self.objects.clear()
        self.shots.clear()
        self.missiles.clear()
        self.enemy_bullets.clear()
        self.particles.clear()
        self.score = 0
        self.level = self.settings["start_level"]
        self.rank = 1
        self.rank_progress = 0
        self.rank_goal = self.calc_rank_goal()
        self.shot_cooldown = 0
        self.missile_cooldown = 0
        self.magnet_timer = 0
        self.shake_frames = 0
        self.flash_frames = 0
        self.start_level(self.level)

    def calc_rank_goal(self):
        return 10 + (self.rank - 1) * 3

    def start_level(self, level):
        self.level = level
        self.objects.clear()
        self.shots.clear()
        self.enemy_bullets.clear()
        self.boss_star = BossStar(level, self.difficulty_mul())

        rock_count = 10 + min(10, self.rank)
        alien_count = max(1, self.rank // 2)

        for _ in range(rock_count):
            self.objects.append(SpaceObject("rock", self.rank, self.difficulty_mul(), self.rock_image))

        for _ in range(alien_count):
            self.objects.append(SpaceObject("alien", self.rank, self.difficulty_mul()))

    def build_menu_buttons(self):
        cx = WIDTH // 2
        y = 215
        w = 260
        h = 58
        gap = 16
        self.menu_buttons = [
            Button("도움말", (cx - w // 2, y, w, h), "HELP"),
            Button("다시시작", (cx - w // 2, y + (h + gap), w, h), "RESTART"),
            Button("환경설정", (cx - w // 2, y + (h + gap) * 2, w, h), "SETTINGS"),
            Button("게임종료", (cx - w // 2, y + (h + gap) * 3, w, h), "QUIT"),
        ]

    def build_settings_buttons(self):
        self.settings_buttons = [
            Button("쉬움", (280, 235, 130, 50), "DIFF_쉬움"),
            Button("보통", (435, 235, 130, 50), "DIFF_보통"),
            Button("어려움", (590, 235, 130, 50), "DIFF_어려움"),
            Button("-", (370, 340, 60, 50), "LEVEL_DOWN"),
            Button("+", (570, 340, 60, 50), "LEVEL_UP"),
            Button("R 재시작 ON/OFF", (350, 435, 300, 54), "TOGGLE_R"),
            Button("적용하고 시작", (350, 520, 300, 58), "APPLY"),
        ]

    def help_text(self):
        return (
            "[게임 목표]\n"
            "전방에 있는 거대한 보스 별을 향해 이동하고, 가까워지면 보스로 변한 별을 처치하는 게임입니다. "
            "레벨은 보스를 처치했을 때만 올라갑니다.\n\n"
            "[조작]\n"
            "W: 전진 가속\n"
            "S: 후진/감속\n"
            "A/D: 좌우 이동\n"
            "SPACE: 위로 상승\n"
            "CTRL: 아래로 하강\n"
            "마우스 왼쪽 클릭 유지: 조준 방향으로 일반 연사\n"
            "마우스 우클릭 유지 + 왼쪽 클릭: 보스 약점 저격탄 발사\n"
            "E: 미사일 발사\n"
            "ESC: 메뉴 열기 / 자동 일시정지\n"
            "R: 다시시작 옵션이 ON일 때 즉시 다시시작\n\n"
            "[이동감]\n"
            "키를 떼도 바로 멈추지 않고 속도가 남아 미끄러지듯 움직입니다. "
            "화면 왼쪽 아래에서 좌우/상하/전후 속도를 확인할 수 있습니다.\n\n"
            "[일반 별]\n"
            "일반 별은 아주 작은 점으로 표시됩니다. 흰색, 푸른색, 노란빛으로 약하게 반짝이며 배경 장식입니다. "
            "소행성과 헷갈리지 않도록 다각형이나 큰 물체로 그리지 않습니다.\n\n"
            "[최종 보스 별]\n"
            "큰 발광 구체로 보이며, 일반 별보다 압도적으로 큽니다. 빛 번짐과 코로나 효과를 가지고 있습니다. "
            "가까워지면 색이 붉어지면서 거대 외계인으로 변신합니다. 변신 후에는 작은 붉은 공 여러 발과 더 큰 붉은 공을 발사합니다. "
            "보스는 계속 플레이어에게 돌진하지 않고, 전방 한계 위치에 고정됩니다.\n\n"
            "[등급]\n"
            "기존 레벨의 파괴 목표 기능은 등급으로 분리했습니다. 운석과 UFO를 파괴해서 등급 조건을 채우면 "
            "등급이 오르고 우주선 주변에 실드/공격 아이템이 여러 개 생성됩니다.\n\n"
            "[아이템]\n"
            "S 아이템: 실드 1개 획득\n"
            "+ 아이템: 공격 횟수 증가\n"
            "하트 아이템: 목숨 1개 증가. 최대 목숨 제한 없이 하트가 늘어납니다.\n"
            "F 아이템: 공격 속도 증가. 마우스를 누르고 있을 때 더 빠르게 연사합니다.\n"
            "파란 M 아이템: 미사일 3발 충전. E 키로 유도 미사일을 발사합니다.\n"
            "랭크업 직후 10초 동안 자석 효과가 생겨 주변 아이템을 자동으로 흡수합니다.\n"
            "아이템은 소행성처럼 가까이 오면 바로 습득됩니다.\n"
            "플레이어와 상하 위치가 거의 같은 아이템/소행성은 노란 테두리로 표시됩니다.\n\n"
            "[외계인]\n"
            "외계인은 초록/파랑 계열의 UFO입니다. 좌우로 움직이고 플레이어 방향으로 붉은 공을 발사합니다. "
            "붉은 공은 플레이어 탄환이 주변에 닿아도 부서질 수 있도록 판정 범위를 넓게 잡았습니다.\n\n"
            "[피격 효과]\n"
            "피격되면 화면 흔들림과 붉은 플래시가 발생합니다. 실드가 있으면 실드가 먼저 소모되고 파란 이펙트가 나타납니다."
        )

    # --------------------------------------------------------
    # 이벤트 처리
    # --------------------------------------------------------
    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if self.state == "HELP":
                self.help_popup.handle_event(event)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.state == "PLAYING":
                        self.state = "MENU"
                    elif self.state in ("MENU", "HELP", "SETTINGS"):
                        self.state = "PLAYING"
                    elif self.state == "GAME_OVER":
                        self.state = "MENU"

                if event.key == pygame.K_r and self.settings["r_restart"]:
                    self.reset_game()

            if self.state == "PLAYING":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    right_held = pygame.mouse.get_pressed(num_buttons=3)[2]
                    self.fire_shots(event.pos, boss_snipe=right_held)
                if event.type == pygame.KEYDOWN and event.key == pygame.K_e:
                    self.fire_missile()
            elif self.state == "MENU":
                for button in self.menu_buttons:
                    if button.is_clicked(event):
                        self.handle_menu_action(button.action)
            elif self.state == "SETTINGS":
                for button in self.settings_buttons:
                    if button.is_clicked(event):
                        self.handle_settings_action(button.action)
            elif self.state == "GAME_OVER":
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.state = "MENU"

    def handle_menu_action(self, action):
        if action == "HELP":
            self.state = "HELP"
            self.help_popup.scroll = 0
        elif action == "RESTART":
            self.reset_game()
        elif action == "SETTINGS":
            self.state = "SETTINGS"
        elif action == "QUIT":
            pygame.quit()
            sys.exit()

    def handle_settings_action(self, action):
        if action.startswith("DIFF_"):
            self.settings["difficulty"] = action.replace("DIFF_", "")
        elif action == "LEVEL_DOWN":
            self.settings["start_level"] = clamp(self.settings["start_level"] - 1, 1, 30)
        elif action == "LEVEL_UP":
            self.settings["start_level"] = clamp(self.settings["start_level"] + 1, 1, 30)
        elif action == "TOGGLE_R":
            self.settings["r_restart"] = not self.settings["r_restart"]
        elif action == "APPLY":
            self.reset_game()

    def get_fire_cooldown_frames(self):
        return max(4, 16 - self.player.attack_speed_level * 2)

    def fire_shots(self, mouse_pos, boss_snipe=False):
        if self.shot_cooldown > 0:
            return
        start = self.player.screen_pos
        total = self.player.attack_count
        for i in range(total):
            self.shots.append(Shot(start, mouse_pos, i, total, boss_snipe=boss_snipe))
        self.shot_cooldown = self.get_fire_cooldown_frames()

    def fire_missile(self):
        if self.player.missiles <= 0 or self.missile_cooldown > 0:
            return
        self.player.missiles -= 1
        self.missile_cooldown = 18
        self.missiles.append(Missile(self.player.screen_pos))

    # --------------------------------------------------------
    # 업데이트
    # --------------------------------------------------------
    def update(self):
        if self.state != "PLAYING":
            return

        keys = pygame.key.get_pressed()
        self.player.update(keys)

        if self.shot_cooldown > 0:
            self.shot_cooldown -= 1
        if self.missile_cooldown > 0:
            self.missile_cooldown -= 1
        if self.magnet_timer > 0:
            self.magnet_timer -= 1

        mouse_buttons = pygame.mouse.get_pressed(num_buttons=3)
        if mouse_buttons[0]:
            self.fire_shots(pygame.mouse.get_pos(), boss_snipe=mouse_buttons[2])

        for star in self.stars:
            star.update(self.player)

        if self.boss_star is not None and self.boss_star.alive:
            self.boss_star.update(self)

        for obj in self.objects:
            obj.update(self)

        for shot in self.shots:
            shot.update()

        for missile in self.missiles:
            missile.update(self)

        self.update_magnet_items()

        for bullet in self.enemy_bullets:
            bullet.update(self)

        for particle in self.particles:
            particle.update()

        self.check_collisions()
        self.cleanup_objects()
        self.spawn_runtime_objects()

        if self.boss_star is not None and not self.boss_star.alive:
            self.on_boss_defeated()

        if self.shake_frames > 0:
            self.shake_frames -= 1
        if self.flash_frames > 0:
            self.flash_frames -= 1

    def item_kinds(self):
        return ("shield", "attack", "life", "speed", "missile")

    def collect_item(self, obj):
        obj.alive = False
        self.player.apply_item(obj.kind)
        px, py = self.player.screen_pos
        color_map = {"shield": CYAN, "attack": YELLOW, "life": PINK, "speed": GREEN, "missile": BLUE}
        color = color_map.get(obj.kind, WHITE)
        for _ in range(34):
            self.particles.append(Particle(px, py, color, "shield"))

    def update_magnet_items(self):
        if self.magnet_timer <= 0:
            return
        px, py = self.player.screen_pos
        for obj in self.objects:
            if not obj.alive or obj.kind not in self.item_kinds():
                continue
            sx, sy, _, _ = obj.projection(self.player)
            screen_dist = math.hypot(sx - px, sy - py)
            world_dist = math.hypot(obj.x - self.player.world_x, obj.y - self.player.world_y)
            if screen_dist < 560 or world_dist < 980 or obj.z < 420:
                obj.x += (self.player.world_x - obj.x) * 0.22
                obj.y += (self.player.world_y - obj.y) * 0.22
                obj.z += (115 - obj.z) * 0.20
                if screen_dist < 82 or obj.z < 145:
                    self.collect_item(obj)

    def check_collisions(self):
        player_rect = self.player.get_rect()

        # 플레이어와 접근한 오브젝트 충돌
        for obj in self.objects:
            if not obj.alive:
                continue

            rect = obj.get_screen_rect(self.player)

            # 아이템은 가까이 오면 바로 습득
            if obj.kind in self.item_kinds():
                if obj.z < 190 and rect.colliderect(player_rect):
                    self.collect_item(obj)
                continue

            if obj.z < 105 and rect.colliderect(player_rect):
                obj.alive = False
                self.player.damage(self)

        # 총알과 오브젝트/보스 충돌
        for shot in self.shots:
            if not shot.alive:
                continue

            shot_rect = shot.get_rect()

            for bullet in self.enemy_bullets:
                if not bullet.alive:
                    continue
                if math.hypot(shot.x - bullet.x, shot.y - bullet.y) <= shot.radius + bullet.shot_hit_radius:
                    shot.alive = False
                    destroyed = bullet.hit(1)
                    for _ in range(18):
                        self.particles.append(Particle(bullet.x, bullet.y, ORANGE if destroyed else RED, "hit"))
                    if destroyed:
                        self.score += 8 if not bullet.source.startswith("boss") else 18
                    break
            if not shot.alive:
                continue

            if (
                shot.boss_snipe
                and self.boss_star is not None
                and self.boss_star.alive
                and self.boss_star.mode == "boss"
            ):
                if shot_rect.colliderect(self.boss_star.get_snipe_rect(self.player)):
                    shot.alive = False
                    self.boss_star.hit(1, self)
                    continue

            for obj in self.objects:
                if not obj.alive:
                    continue
                if obj.kind not in ("rock", "alien"):
                    continue

                obj_rect = obj.get_screen_rect(self.player)
                if shot_rect.colliderect(obj_rect):
                    shot.alive = False
                    destroyed = obj.hit(1)
                    sx, sy, _, _ = obj.projection(self.player)
                    effect_color = ORANGE if obj.kind == "rock" else GREEN
                    for _ in range(14):
                        self.particles.append(Particle(sx, sy, effect_color, "hit"))

                    if destroyed:
                        self.destroy_object(obj)
                    break

        for missile in self.missiles:
            if not missile.alive:
                continue
            for bullet in self.enemy_bullets:
                if not bullet.alive:
                    continue
                if math.hypot(missile.x - bullet.x, missile.y - bullet.y) <= missile.radius + bullet.shot_hit_radius:
                    missile.alive = False
                    bullet.alive = False
                    for _ in range(24):
                        self.particles.append(Particle(bullet.x, bullet.y, BLUE, "hit"))
                    break
            if not missile.alive:
                continue
            for obj in self.objects:
                if not obj.alive or obj.kind not in ("rock", "alien"):
                    continue
                if missile.get_rect().colliderect(obj.get_screen_rect(self.player)):
                    missile.alive = False
                    destroyed = obj.hit(4)
                    sx, sy, _, _ = obj.projection(self.player)
                    for _ in range(32):
                        self.particles.append(Particle(sx, sy, BLUE, "hit"))
                    if destroyed:
                        self.destroy_object(obj)
                    break

    def destroy_object(self, obj):
        if obj.kind == "rock":
            self.score += int(obj.base_size * 3 + self.rank * 6)
            self.rank_progress += 1

            # 큰 운석은 낮은 확률로 분열
            if obj.base_size >= 60 and random.random() < 0.38:
                for _ in range(2):
                    nx = obj.x + random.uniform(-65, 65)
                    ny = obj.y + random.uniform(-45, 45)
                    nz = clamp(obj.z + random.uniform(50, 150), NEAR_Z + 110, OBJECT_FAR_Z)
                    child = SpaceObject(
                        "rock",
                        self.rank,
                        self.difficulty_mul(),
                        self.rock_image,
                        (nx, ny, nz),
                        size=max(30, int(obj.base_size * 0.56)),
                    )
                    child.speed *= 1.25
                    self.objects.append(child)

        elif obj.kind == "alien":
            self.score += 220 + self.rank * 35
            self.rank_progress += 2

        # 낮은 확률의 일반 드롭
        if random.random() < 0.13:
            item_kind = random.choices(["shield", "attack", "life", "speed", "missile"], weights=[30, 26, 14, 18, 12], k=1)[0]
            item = SpaceObject(
                item_kind,
                self.rank,
                self.difficulty_mul(),
                forced_pos=(obj.x, obj.y, clamp(obj.z + 120, NEAR_Z + 120, OBJECT_FAR_Z)),
            )
            self.objects.append(item)

        self.check_rank_progress()

    def check_rank_progress(self):
        while self.rank_progress >= self.rank_goal:
            self.rank_progress -= self.rank_goal
            self.rank += 1
            self.rank_goal = self.calc_rank_goal()
            self.spawn_rank_reward_items()
            self.magnet_timer = MAGNET_DURATION
            self.shake_frames = 15

    def spawn_rank_reward_items(self):
        # 우주선 주변에 아이템 여러 개 생성
        count = 5 + min(4, self.rank // 2)
        for i in range(count):
            angle = math.tau * i / count + random.uniform(-0.25, 0.25)
            radius = random.uniform(80, 180)
            item_x = self.player.world_x + math.cos(angle) * radius
            item_y = self.player.world_y + math.sin(angle) * radius
            item_z = random.uniform(155, 245)
            item_kind = random.choice(["shield", "attack", "life", "speed", "missile"])
            self.objects.append(
                SpaceObject(
                    item_kind,
                    self.rank,
                    self.difficulty_mul(),
                    forced_pos=(item_x, item_y, item_z),
                )
            )

    def on_boss_defeated(self):
        for obj in self.objects:
            if obj.alive and obj.kind in self.item_kinds():
                self.collect_item(obj)
        self.level += 1
        self.rank_progress = 0
        self.rank_goal = self.calc_rank_goal()
        self.player.shield = clamp(self.player.shield + 1, 0, 5)
        self.player.attack_count = clamp(self.player.attack_count, 1, 5)
        self.start_level(self.level)

    def cleanup_objects(self):
        self.objects = [obj for obj in self.objects if obj.alive]
        self.shots = [shot for shot in self.shots if shot.alive]
        self.missiles = [missile for missile in self.missiles if missile.alive]
        self.enemy_bullets = [bullet for bullet in self.enemy_bullets if bullet.alive]
        self.particles = [particle for particle in self.particles if particle.life > 0]

    def spawn_runtime_objects(self):
        # 보스전 중에도 기본 방해물이 너무 적으면 보충
        rocks = sum(1 for obj in self.objects if obj.kind == "rock")
        aliens = sum(1 for obj in self.objects if obj.kind == "alien")
        items = sum(1 for obj in self.objects if obj.kind in self.item_kinds())

        desired_rocks = 9 + min(10, self.rank)
        if rocks < desired_rocks and random.random() < 0.075:
            self.objects.append(SpaceObject("rock", self.rank, self.difficulty_mul(), self.rock_image))

        desired_aliens = max(1, self.rank // 2)
        if aliens < desired_aliens and random.random() < 0.026:
            self.objects.append(SpaceObject("alien", self.rank, self.difficulty_mul()))

        if items < 2 and random.random() < 0.006:
            item_kind = random.choices(["shield", "attack", "life", "speed", "missile"], weights=[30, 25, 15, 18, 12], k=1)[0]
            self.objects.append(SpaceObject(item_kind, self.rank, self.difficulty_mul()))

    # --------------------------------------------------------
    # 그리기
    # --------------------------------------------------------
    def draw(self):
        offset = self.get_screen_offset()
        mouse_pos = pygame.mouse.get_pos()

        self.screen.fill(DARK)
        self.draw_background(offset)

        if self.boss_star is not None and self.boss_star.alive:
            self.boss_star.draw(self.screen, self.player, offset)

        self.draw_objects(offset)
        self.player.draw(self.screen, mouse_pos, offset)
        self.draw_shots(offset)
        self.draw_missiles(offset)
        self.draw_particles(offset)
        self.draw_ui()
        self.draw_damage_flash()

        if self.state == "MENU":
            self.draw_menu()
        elif self.state == "HELP":
            self.help_popup.draw(self.screen)
        elif self.state == "SETTINGS":
            self.draw_settings()
        elif self.state == "GAME_OVER":
            self.draw_game_over()

        pygame.display.flip()

    def get_screen_offset(self):
        if self.shake_frames <= 0:
            return 0, 0
        power = min(12, self.shake_frames)
        return random.randint(-power, power), random.randint(-power, power)

    def draw_background(self, offset):
        self.screen.fill(DARK)

        # 일반 별: 작은 점으로만 표현
        for star in self.stars:
            star.draw(self.screen, self.player, offset)

        # 아주 약한 원근 방향감만 남기고, 줄 그리드 느낌은 제거
        glow = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(glow, (60, 80, 140, 18), (CENTER_X, HORIZON_Y), 280)
        self.screen.blit(glow, (0, 0))

    def draw_objects(self, offset):
        # 먼 것부터 그림
        for obj in sorted(self.objects, key=lambda o: o.z, reverse=True):
            obj.draw(self.screen, self.player, offset)

        for bullet in self.enemy_bullets:
            bullet.draw(self.screen, offset)

    def draw_shots(self, offset):
        for shot in self.shots:
            shot.draw(self.screen, offset)

    def draw_missiles(self, offset):
        for missile in self.missiles:
            missile.draw(self.screen, offset)

    def draw_particles(self, offset):
        for particle in self.particles:
            particle.draw(self.screen, offset)

    def draw_ui(self):
        draw_text(self.screen, f"SCORE {self.score}", 26, 20, 18, WHITE, bold=True)
        draw_text(self.screen, f"LEVEL {self.level}", 24, 20, 52, CYAN, bold=True)
        draw_text(self.screen, f"RANK {self.rank}", 23, 20, 84, YELLOW, bold=True)
        draw_text(self.screen, f"등급 조건 {self.rank_progress}/{self.rank_goal}", 20, 20, 114, WHITE)
        draw_text(self.screen, f"난이도 {self.settings['difficulty']} x{self.difficulty_mul():.1f}", 19, 20, 142, GRAY)

        if self.boss_star is not None and self.boss_star.mode == "approach":
            dist_t = clamp((self.boss_star.z - BOSS_STAR_TRIGGER_Z) / (BOSS_STAR_START_Z - BOSS_STAR_TRIGGER_Z), 0, 1)
            draw_text(self.screen, f"보스 별 접근률 {int((1 - dist_t) * 100)}%", 20, 20, 170, ORANGE)

        vx = self.player.velocity_x
        vy = self.player.velocity_y
        vz = self.player.velocity_z
        draw_text(self.screen, f"속도 X:{vx:5.1f}  Y:{vy:5.1f}  Z:{vz:5.1f}", 18, 20, HEIGHT - 34, (120, 135, 170))

        # 목숨: 하트로 표시. 하트가 많아지면 자동 줄바꿈.
        hearts_per_row = 8
        for i in range(self.player.lives):
            row = i // hearts_per_row
            col = i % hearts_per_row
            draw_heart(self.screen, WIDTH - 34 - col * 32, 32 + row * 31, 22, RED)

        ui_y = 72 + max(0, (self.player.lives - 1) // hearts_per_row) * 31
        draw_text(self.screen, f"실드 {self.player.shield}", 21, WIDTH - 178, ui_y, CYAN, bold=True)
        draw_text(self.screen, f"공격 {self.player.attack_count}", 21, WIDTH - 178, ui_y + 30, YELLOW, bold=True)
        draw_text(self.screen, f"연사 {self.player.attack_speed_level}", 21, WIDTH - 178, ui_y + 60, GREEN, bold=True)
        draw_text(self.screen, f"미사일 {self.player.missiles}", 21, WIDTH - 178, ui_y + 90, BLUE, bold=True)
        if self.magnet_timer > 0:
            draw_text(self.screen, f"자석 흡수 {self.magnet_timer / FPS:0.1f}s", 21, CENTER_X, 72, CYAN, center=True, bold=True)
        draw_text(self.screen, "ESC 메뉴", 19, WIDTH - 120, HEIGHT - 34, GRAY)

        # 조준점
        mx, my = pygame.mouse.get_pos()
        boss_snipe_mode = pygame.mouse.get_pressed(num_buttons=3)[2]
        aim_color = PINK if boss_snipe_mode else WHITE
        pygame.draw.circle(self.screen, aim_color, (mx, my), 12, 1)
        pygame.draw.line(self.screen, aim_color, (mx - 18, my), (mx - 6, my), 1)
        pygame.draw.line(self.screen, aim_color, (mx + 6, my), (mx + 18, my), 1)
        pygame.draw.line(self.screen, aim_color, (mx, my - 18), (mx, my - 6), 1)
        pygame.draw.line(self.screen, aim_color, (mx, my + 6), (mx, my + 18), 1)
        if boss_snipe_mode:
            draw_text(self.screen, "BOSS 저격 모드", 18, mx + 18, my + 18, PINK, bold=True)

    def draw_damage_flash(self):
        if self.flash_frames > 0:
            alpha = int(150 * self.flash_frames / 18)
            flash = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            flash.fill((255, 35, 45, alpha))
            self.screen.blit(flash, (0, 0))

    def draw_menu(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        self.screen.blit(overlay, (0, 0))

        panel_rect = pygame.Rect(WIDTH // 2 - 210, 120, 420, 440)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=20)
        pygame.draw.rect(self.screen, CYAN, panel_rect, 2, border_radius=20)
        draw_text(self.screen, "일시정지 메뉴", 36, panel_rect.centerx, 165, CYAN, center=True, bold=True)
        draw_text(self.screen, "ESC를 다시 누르면 게임으로 돌아감", 18, panel_rect.centerx, 198, GRAY, center=True)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            button.draw(self.screen, mouse_pos)

    def draw_settings(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        self.screen.blit(overlay, (0, 0))

        panel_rect = pygame.Rect(210, 115, 580, 505)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=20)
        pygame.draw.rect(self.screen, CYAN, panel_rect, 2, border_radius=20)
        draw_text(self.screen, "환경설정", 36, panel_rect.centerx, 158, CYAN, center=True, bold=True)
        draw_text(self.screen, "ESC: 돌아가기", 18, panel_rect.centerx, 195, GRAY, center=True)

        draw_text(self.screen, "난이도", 24, 250, 198, WHITE, bold=True)
        draw_text(self.screen, f"현재: {self.settings['difficulty']}  / 운석 속도 x{self.difficulty_mul():.1f}", 20, 250, 292, GRAY)

        draw_text(self.screen, "시작 레벨", 24, 250, 350, WHITE, bold=True)
        draw_text(self.screen, str(self.settings["start_level"]), 32, CENTER_X, 355, YELLOW, center=True, bold=True)

        draw_text(self.screen, "R 키 다시시작", 24, 250, 445, WHITE, bold=True)
        draw_text(self.screen, "ON" if self.settings["r_restart"] else "OFF", 26, 680, 447, GREEN if self.settings["r_restart"] else RED, center=True, bold=True)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.settings_buttons:
            button.draw(self.screen, mouse_pos)

        diff_to_rect = {
            "쉬움": pygame.Rect(280, 235, 130, 50),
            "보통": pygame.Rect(435, 235, 130, 50),
            "어려움": pygame.Rect(590, 235, 130, 50),
        }
        pygame.draw.rect(self.screen, YELLOW, diff_to_rect[self.settings["difficulty"]], 3, border_radius=12)

    def draw_game_over(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 205))
        self.screen.blit(overlay, (0, 0))

        panel_rect = pygame.Rect(WIDTH // 2 - 260, HEIGHT // 2 - 160, 520, 320)
        pygame.draw.rect(self.screen, PANEL, panel_rect, border_radius=22)
        pygame.draw.rect(self.screen, RED, panel_rect, 3, border_radius=22)

        draw_text(self.screen, "GAME OVER", 52, panel_rect.centerx, panel_rect.y + 70, RED, center=True, bold=True)
        draw_text(self.screen, f"최종 점수: {self.score}", 28, panel_rect.centerx, panel_rect.y + 140, WHITE, center=True)
        draw_text(self.screen, f"도달 레벨: {self.level}", 24, panel_rect.centerx, panel_rect.y + 178, CYAN, center=True)
        draw_text(self.screen, f"도달 등급: {self.rank}", 24, panel_rect.centerx, panel_rect.y + 210, YELLOW, center=True)

        restart_text = "R: 다시시작 / 클릭: 메뉴" if self.settings["r_restart"] else "클릭: 메뉴"
        draw_text(self.screen, restart_text, 22, panel_rect.centerx, panel_rect.y + 255, GRAY, center=True)

    # --------------------------------------------------------
    # 메인 루프
    # --------------------------------------------------------
    def run(self):
        while True:
            self.clock.tick(FPS)
            self.handle_events()
            self.update()
            self.draw()


if __name__ == "__main__":
    Game().run()
