import serial
import pygame
import time
import math

# === SETTINGS ===
PORT = 'COM4'
BAUD = 9600
WIDTH, HEIGHT = 800, 600
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2
DRAW_LIMIT_CM = 10         # LiDAR distance limit for drawing
DRAW_SPEED = 2             # Pixels per frame

# === SERIAL SETUP ===
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

# === PYGAME INIT ===
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("TF Mini S with MPU6050 - Continuous Drawing")
font = pygame.font.SysFont("Arial", 18)
clock = pygame.time.Clock()
draw_surface = pygame.Surface((WIDTH, HEIGHT))
draw_surface.fill((0, 0, 0))

# === BUTTONS ===
reset_button_rect = pygame.Rect(WIDTH - 110, 10, 100, 30)
calibrate_button_rect = pygame.Rect(WIDTH - 110, 50, 100, 30)

# === STATE ===
distance_cm = 9999
yaw_angle = 0
yaw_offset = 0
calibrated = False

# Pen position
current_pos_x = CENTER_X
current_pos_y = CENTER_Y
last_pos_x = CENTER_X
last_pos_y = CENTER_Y

# Direction handling
current_direction_angle = 0  # degrees, used for movement
previous_yaw = 0
yaw_history = []
movement_threshold = 0.5
history_length = 10

# === FUNCTIONS ===
def calibrate_yaw():
    """Set current yaw as the reference (0 degrees)"""
    global yaw_offset, calibrated, current_direction_angle
    yaw_offset = yaw_angle
    calibrated = True
    current_direction_angle = 0
    print(f"Calibrated! Yaw offset set to: {yaw_offset}")

def get_calibrated_angle():
    """Get the calibrated yaw angle"""
    if not calibrated:
        return yaw_angle
    calibrated_angle = yaw_angle - yaw_offset
    while calibrated_angle > 180:
        calibrated_angle -= 360
    while calibrated_angle < -180:
        calibrated_angle += 360
    return calibrated_angle

def detect_gyro_turn():
    """Return True if gyro has turned enough to change direction"""
    global yaw_history, previous_yaw
    if not calibrated:
        return False
    
    current_calibrated_yaw = get_calibrated_angle()
    yaw_history.append(current_calibrated_yaw)
    if len(yaw_history) > history_length:
        yaw_history.pop(0)
    
    immediate_change = abs(current_calibrated_yaw - previous_yaw)
    previous_yaw = current_calibrated_yaw
    return immediate_change > movement_threshold

# === MAIN LOOP ===
running = True
while running:
    screen.fill((0, 0, 0))
    screen.blit(draw_surface, (0, 0))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.MOUSEBUTTONDOWN:
            if reset_button_rect.collidepoint(event.pos):
                draw_surface.fill((0, 0, 0))
                current_pos_x = CENTER_X
                current_pos_y = CENTER_Y
                last_pos_x = CENTER_X
                last_pos_y = CENTER_Y
                print("Drawing reset!")
            elif calibrate_button_rect.collidepoint(event.pos):
                calibrate_yaw()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:
                calibrate_yaw()
            elif event.key == pygame.K_r:
                draw_surface.fill((0, 0, 0))
                current_pos_x = CENTER_X
                current_pos_y = CENTER_Y
                last_pos_x = CENTER_X
                last_pos_y = CENTER_Y

    # === READ SERIAL ===
    if ser.in_waiting:
        try:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            if line:
                parts = line.split(',')
                for part in parts:
                    if part.startswith("distance="):
                        distance_cm = int(part.split("=")[1])
                    elif part.startswith("yaw="):
                        yaw_angle = float(part.split("=")[1])
        except:
            pass

    # === TURN DETECTION ===
    if detect_gyro_turn():
        current_direction_angle = get_calibrated_angle()

    # === CONTINUOUS DRAWING ===
    if 0 < distance_cm <= DRAW_LIMIT_CM and calibrated:
        # Move pen in current direction
        angle_rad = math.radians(current_direction_angle)
        dx = math.cos(angle_rad) * DRAW_SPEED
        dy = math.sin(angle_rad) * DRAW_SPEED

        last_pos_x = current_pos_x
        last_pos_y = current_pos_y
        current_pos_x += dx
        current_pos_y += dy

        # Keep inside screen
        current_pos_x = max(10, min(WIDTH - 10, current_pos_x))
        current_pos_y = max(10, min(HEIGHT - 10, current_pos_y))

        # Draw line
        pygame.draw.line(draw_surface, (0, 255, 0),
                         (int(last_pos_x), int(last_pos_y)),
                         (int(current_pos_x), int(current_pos_y)), 3)

        pygame.draw.circle(screen, (0, 255, 0),
                          (int(current_pos_x), int(current_pos_y)), 6)
    else:
        # Red circle when out of range
        pygame.draw.circle(screen, (255, 0, 0),
                          (int(current_pos_x), int(current_pos_y)), 4)

    # === UI ===
    pygame.draw.rect(screen, (200, 0, 0), reset_button_rect)
    screen.blit(font.render("RESET", True, (255, 255, 255)), (WIDTH - 85, 15))
    
    pygame.draw.rect(screen, (0, 200, 0) if calibrated else (100, 100, 100), calibrate_button_rect)
    screen.blit(font.render("CALIB", True, (255, 255, 255)), (WIDTH - 85, 55))

    screen.blit(font.render(f"Distance: {distance_cm} cm", True, (255, 255, 255)), (10, 10))
    screen.blit(font.render(f"Raw Yaw: {yaw_angle:.1f}°", True, (255, 255, 255)), (10, 35))
    if calibrated:
        screen.blit(font.render(f"Direction: {current_direction_angle:.1f}°", True, (0, 255, 0)), (10, 60))
    else:
        screen.blit(font.render("Press 'C' to calibrate", True, (255, 255, 0)), (10, 60))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
