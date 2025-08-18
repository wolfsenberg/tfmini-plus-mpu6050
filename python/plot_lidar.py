import serial
import pygame
import time
import math
from collections import deque

# ===== SETTINGS =====
PORT = "COM4"     # change if needed
BAUD = 9600
WIDTH, HEIGHT = 1400, 900
CENTER_X, CENTER_Y = WIDTH // 2 - 100, int(HEIGHT // 1.4)
MAX_CM = 70
SCALE = 7                    # pixels per cm
MAP_SMOOTH_N = 8             # heavier smoothing for map points
BEAM_SMOOTH_N = 2            # minimal smoothing for beam

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREEN = (0, 255, 0)
LIGHT_GREEN = (100, 255, 100)
DARK_GREEN = (0, 180, 0)
RED = (255, 50, 50)
GRAY = (60, 60, 60)
LIGHT_GRAY = (120, 120, 120)
DARK_GRAY = (30, 30, 30)
BLUE = (100, 150, 255)

# ===== SERIAL =====
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

# ===== PYGAME =====
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Radar Display")
clock = pygame.time.Clock()
font_small = pygame.font.SysFont('Arial', 16)
font_medium = pygame.font.SysFont('Arial', 18, bold=True)
font_large = pygame.font.SysFont('Arial', 24, bold=True)

# Window state
minimized = False
MINI_WIDTH, MINI_HEIGHT = 400, 300

# ===== STATE =====
map_dist_hist = deque(maxlen=MAP_SMOOTH_N)
map_yaw_hist = deque(maxlen=MAP_SMOOTH_N)
beam_yaw_hist = deque(maxlen=BEAM_SMOOTH_N)

sensor = {
    "distance_raw": 0.0,
    "yaw_raw": 90.0,
    "yaw_instant": 90.0,
    "direction": "Stationary",
    "object": "None",
    "gyro": "Still",
}

distance_plot = 0.0
beam_distance = 0.0
calibrated = False
yaw_offset = 0.0
# Enhanced scan_points structure
scan_points = {}  # angle -> {'coord': (x,y), 'has_object': bool, 'distance': float}

# UI Layout
PANEL_WIDTH = 320
PANEL_X = WIDTH - PANEL_WIDTH - 20
PANEL_Y = 20
CARD_HEIGHT = 140
SPACING = 15

# ===== HELPERS =====
def clamp(v, lo, hi): return max(lo, min(hi, v))
def movavg(buf, val): buf.append(val); return sum(buf)/len(buf)
def wrap360(a):
    while a < 0: a += 360
    while a >= 360: a -= 360
    return a

def parse_line(line):
    out = {}
    for part in line.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.strip()
    return out

def get_beam_angle(yaw_raw):
    y = yaw_raw - yaw_offset if calibrated else yaw_raw
    y = wrap360(y)
    if 0.0 <= y <= 180.0:
        reversed_y = 180 - y
        return movavg(beam_yaw_hist, reversed_y)
    return None

def get_map_angle(yaw_raw):
    y = yaw_raw - yaw_offset if calibrated else yaw_raw
    y = wrap360(y)
    if 0.0 <= y <= 180.0:
        reversed_y = 180 - y
        return movavg(map_yaw_hist, reversed_y)
    return None

def polar_to_xy(angle_deg, dist_cm):
    r = dist_cm * SCALE
    a = math.radians(angle_deg)
    x = CENTER_X + r * math.cos(a)
    y = CENTER_Y - r * math.sin(a)
    return (int(x), int(y))

def draw_card(surface, x, y, w, h, title, content, title_color=WHITE, bg_color=(25, 25, 25)):
    # Card background
    card_rect = pygame.Rect(x, y, w, h)
    pygame.draw.rect(surface, bg_color, card_rect, border_radius=12)
    pygame.draw.rect(surface, (70, 70, 70), card_rect, 2, border_radius=12)
    
    # Title
    title_surf = font_medium.render(title, True, title_color)
    surface.blit(title_surf, (x + 15, y + 12))
    
    # Content
    content_y = y + 40
    for line in content:
        text_surf = font_small.render(line, True, WHITE)
        surface.blit(text_surf, (x + 15, content_y))
        content_y += 22

def draw_radar_display():
    # Arc background (outer boundary)
    pygame.draw.arc(
        screen,
        (15, 15, 15),
        pygame.Rect(
            CENTER_X - (MAX_CM * SCALE + 10),
            CENTER_Y - (MAX_CM * SCALE + 10),
            2 * (MAX_CM * SCALE + 10),
            2 * (MAX_CM * SCALE + 10)
        ),
        math.radians(0),
        math.radians(180),
        10
    )

    # Outer arc border
    pygame.draw.arc(
        screen,
        GRAY,
        pygame.Rect(
            CENTER_X - MAX_CM * SCALE,
            CENTER_Y - MAX_CM * SCALE,
            2 * MAX_CM * SCALE,
            2 * MAX_CM * SCALE
        ),
        math.radians(0),
        math.radians(180),
        2
    )

    # Range rings (half-circles)
    for r in [10, 20, 30, 40, 50, 60]:
        pygame.draw.arc(
            screen,
            DARK_GRAY,
            pygame.Rect(CENTER_X - r * SCALE, CENTER_Y - r * SCALE, r * SCALE * 2, r * SCALE * 2),
            math.radians(0),
            math.radians(180),
            1
        )

    # Angle lines (radiating from center, only in top half)
    for angle in range(0, 181, 30):
        end_pos = polar_to_xy(angle, MAX_CM)
        color = LIGHT_GRAY if angle == 90 else DARK_GRAY
        width = 2 if angle == 90 else 1
        pygame.draw.line(screen, color, (CENTER_X, CENTER_Y), end_pos, width)

    # Range labels (on the middle vertical line)
    for r in [10, 20, 30, 40, 50, 60, 70]:
        label_pos = polar_to_xy(90, r)
        label = font_small.render(f"{r}cm", True, LIGHT_GRAY)
        screen.blit(label, (label_pos[0] - 15, label_pos[1] - 10))

    # Angle labels (top arc only)
    for angle in [0, 30, 60, 90, 120, 150, 180]:
        label_pos = polar_to_xy(angle, MAX_CM + 15)
        label = font_small.render(f"{angle}°", True, LIGHT_GRAY)
        label_rect = label.get_rect(center=label_pos)
        screen.blit(label, label_rect)

def draw_scan_data():
    if not scan_points:
        return
    
    # Draw continuous dotted line connecting all scan points
    all_angles = sorted(scan_points.keys())
    if len(all_angles) > 1:
        # Create a smooth dotted line across all scanned angles
        for i in range(len(all_angles) - 1):
            angle1 = all_angles[i]
            angle2 = all_angles[i + 1]
            
            # Get coordinates for both points
            data1 = scan_points[angle1]
            data2 = scan_points[angle2]
            
            # Use detection coordinates if available, otherwise use max range
            coord1 = data1['coord'] if data1['has_object'] else polar_to_xy(angle1, MAX_CM)
            coord2 = data2['coord'] if data2['has_object'] else polar_to_xy(angle2, MAX_CM)
            
            # Draw fine dotted line between consecutive points with no gaps
            draw_dotted_line(coord1, coord2, GREEN, dot_size=1, spacing=2)

def draw_dotted_line(start_pos, end_pos, color, dot_size=1, spacing=2):
    """Draw a fine dotted line with no gaps between two points"""
    start_x, start_y = start_pos
    end_x, end_y = end_pos
    
    # Calculate distance and direction
    dx = end_x - start_x
    dy = end_y - start_y
    distance = math.sqrt(dx*dx + dy*dy)
    
    if distance == 0:
        return
    
    # Draw very fine dots with minimal spacing for continuous appearance
    num_dots = int(distance / spacing) + 1
    for i in range(num_dots + 1):
        progress = i / max(num_dots, 1) if num_dots > 0 else 0
        dot_x = start_x + progress * dx
        dot_y = start_y + progress * dy
        pygame.draw.circle(screen, color, (int(dot_x), int(dot_y)), dot_size)

def draw_beam(angle_deg, dist_cm):
    if angle_deg is None:
        return
    
    end_point = polar_to_xy(angle_deg, dist_cm)
    
    # Beam line with gradient effect
    pygame.draw.line(screen, LIGHT_GREEN, (CENTER_X, CENTER_Y), end_point, 4)
    pygame.draw.line(screen, GREEN, (CENTER_X, CENTER_Y), end_point, 2)
    
    # Target indicator
    if sensor["object"].lower() != "none" and dist_cm < MAX_CM:
        pygame.draw.circle(screen, RED, end_point, 12)
        pygame.draw.circle(screen, WHITE, end_point, 12, 3)
        pygame.draw.circle(screen, RED, end_point, 6)
    
    # Center sensor
    pygame.draw.circle(screen, WHITE, (CENTER_X, CENTER_Y), 8)
    pygame.draw.circle(screen, BLUE, (CENTER_X, CENTER_Y), 6)

def draw_ui():
    if minimized:
        # Minimized UI - compact display
        # Mini title bar
        pygame.draw.rect(screen, (40, 40, 40), (0, 0, MINI_WIDTH, 30), border_radius=8)
        title = font_medium.render("Radar (Minimized)", True, WHITE)
        screen.blit(title, (10, 6))
        
        # Minimize button (expand)
        expand_btn = pygame.Rect(MINI_WIDTH - 35, 5, 25, 20)
        pygame.draw.rect(screen, (80, 80, 80), expand_btn, border_radius=4)
        pygame.draw.rect(screen, WHITE, (expand_btn.x + 8, expand_btn.y + 8, 9, 4))
        
        # Compact data display
        y_pos = 45
        compact_data = [
            f"Distance: {beam_distance:.0f}cm",
            f"Angle: {get_beam_angle(sensor['yaw_instant']):.0f}°" if get_beam_angle(sensor['yaw_instant']) else "Angle: —",
            f"Object: {sensor['object']}",
            f"Status: {'CAL' if calibrated else 'UNCAL'}",
            "",
            "M - Maximize | R - Reset | C - Cal | Q - Quit"
        ]
        
        for line in compact_data:
            color = RED if "object" in line.lower() and sensor["object"].lower() != "none" else WHITE
            color = GREEN if "CAL" in line and calibrated else color
            color = RED if "UNCAL" in line else color
            
            text = font_small.render(line, True, color)
            screen.blit(text, (15, y_pos))
            y_pos += 20
            
        return expand_btn
    else:
        # Full UI
        # Minimize button
        minimize_btn = pygame.Rect(WIDTH - 60, 10, 50, 25)
        pygame.draw.rect(screen, (60, 60, 60), minimize_btn, border_radius=6)
        pygame.draw.rect(screen, (100, 100, 100), minimize_btn, 2, border_radius=6)
        min_text = font_small.render("MIN", True, WHITE)
        screen.blit(min_text, (minimize_btn.x + 12, minimize_btn.y + 4))
        
        # Status panel
        status_content = [
            f"Distance: {beam_distance:.1f} cm",
            f"Angle: {get_beam_angle(sensor['yaw_instant']):.1f}°" if get_beam_angle(sensor['yaw_instant']) else "Angle: —",
            f"Object: {sensor['object']}"
        ]
        object_color = RED if sensor["object"].lower() != "none" else WHITE
        draw_card(screen, PANEL_X, PANEL_Y, PANEL_WIDTH, CARD_HEIGHT, 
                  "SENSOR STATUS", status_content, object_color)
        
        # System info
        system_content = [
            f"Calibrated: {'YES' if calibrated else 'NO'}",
            f"Direction: {sensor['direction']}",
            f"Gyro: {sensor['gyro']}",
            f"Points: {len(scan_points)}"
        ]
        calib_color = GREEN if calibrated else RED
        draw_card(screen, PANEL_X, PANEL_Y + CARD_HEIGHT + SPACING, PANEL_WIDTH, CARD_HEIGHT,
                  "SYSTEM", system_content, calib_color)
        
        # Controls
        controls_content = [
            "R - Reset scan data",
            "C - Calibrate sensor",
            "M - Minimize window", 
            "Q - Quit application"
        ]
        draw_card(screen, PANEL_X, PANEL_Y + 2*(CARD_HEIGHT + SPACING), PANEL_WIDTH, CARD_HEIGHT,
                  "CONTROLS", controls_content, BLUE)
        
        # Title
        title = font_large.render("OBJECT SCANNER XD", True, WHITE)
        screen.blit(title, (30, 30))
        
        # Range indicator
        range_text = font_medium.render(f"MAX RANGE: {MAX_CM}cm", True, LIGHT_GRAY)
        screen.blit(range_text, (30, 70))
        
        return minimize_btn

# ===== MAIN LOOP =====
running = True
while running:
    # Events
    for e in pygame.event.get():
        if e.type == pygame.QUIT:
            running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_r:
                scan_points.clear()
            elif e.key == pygame.K_c:
                yaw_offset = sensor["yaw_instant"] - 90.0
                calibrated = True
                try:
                    ser.write(b"CALIB\n")
                except: pass
            elif e.key == pygame.K_q:
                running = False
            elif e.key == pygame.K_m:
                minimized = not minimized
                if minimized:
                    screen = pygame.display.set_mode((MINI_WIDTH, MINI_HEIGHT))
                else:
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
        elif e.type == pygame.MOUSEBUTTONDOWN:
            # Handle minimize/maximize button clicks
            if minimized:
                expand_btn = pygame.Rect(MINI_WIDTH - 35, 5, 25, 20)
                if expand_btn.collidepoint(e.pos):
                    minimized = False
                    screen = pygame.display.set_mode((WIDTH, HEIGHT))
            else:
                minimize_btn = pygame.Rect(WIDTH - 60, 10, 50, 25)
                if minimize_btn.collidepoint(e.pos):
                    minimized = True
                    screen = pygame.display.set_mode((MINI_WIDTH, MINI_HEIGHT))

    # Serial read
    if ser.in_waiting:
        try:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                parsed = parse_line(line)
                
                if "distance" in parsed:
                    raw_dist = float(parsed["distance"])
                    sensor["distance_raw"] = movavg(map_dist_hist, raw_dist)
                    beam_distance = raw_dist
                
                if "yaw" in parsed:
                    raw_yaw = wrap360(float(parsed["yaw"]))
                    sensor["yaw_instant"] = raw_yaw
                    sensor["yaw_raw"] = raw_yaw
                
                if "direction" in parsed: sensor["direction"] = parsed["direction"]
                if "object" in parsed: sensor["object"] = parsed["object"]
                if "gyro" in parsed: sensor["gyro"] = parsed["gyro"]
        except: pass

    # Calculate angles
    beam_angle = get_beam_angle(sensor["yaw_instant"])
    map_angle = get_map_angle(sensor["yaw_raw"])
    
    # Calculate distances
    beam_plot_distance = clamp(beam_distance, 0.0, MAX_CM) if sensor["object"].lower() != "none" and beam_distance < MAX_CM else MAX_CM
    distance_plot = clamp(sensor["distance_raw"], 0.0, MAX_CM) if sensor["object"].lower() != "none" and sensor["distance_raw"] < MAX_CM else MAX_CM

    # Update map (Enhanced version)
    if map_angle is not None and 0 <= map_angle <= 180:
        angle_key = int(round(map_angle))
        has_object = sensor["object"].lower() != "none" and sensor["distance_raw"] < MAX_CM
        actual_distance = sensor["distance_raw"] if has_object else MAX_CM
        
        scan_points[angle_key] = {
            'coord': polar_to_xy(angle_key, distance_plot),
            'has_object': has_object,
            'distance': actual_distance
        }

    # Draw everything
    screen.fill(BLACK)
    
    if not minimized:
        draw_radar_display()
        draw_scan_data()
        if beam_angle is not None:
            draw_beam(beam_angle, beam_plot_distance)
    
    draw_ui()

    pygame.display.flip()
    clock.tick(60)

ser.close()
pygame.quit()