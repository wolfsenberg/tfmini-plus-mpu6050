import serial
import pygame
import time
import math

# === SETTINGS ===
PORT = 'COM4'
BAUD = 9600
WIDTH, HEIGHT = 800, 600
CENTER_X, CENTER_Y = WIDTH // 2, HEIGHT // 2

# === SERIAL SETUP ===
ser = serial.Serial(PORT, BAUD, timeout=1)
time.sleep(2)

# === PYGAME INIT ===
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("TF Mini S with MPU6050 - Pen-like Drawing")
font = pygame.font.SysFont("Arial", 18)
clock = pygame.time.Clock()
draw_surface = pygame.Surface((WIDTH, HEIGHT))
draw_surface.fill((0, 0, 0))

# === RESET BUTTON ===
reset_button_rect = pygame.Rect(WIDTH - 110, 10, 100, 30)

# === CALIBRATION BUTTON ===
calibrate_button_rect = pygame.Rect(WIDTH - 110, 50, 100, 30)

# === STATE ===
distance_cm = 9999
yaw_angle = 0
yaw_offset = 0  # For calibration
current_pos_x = CENTER_X  # Current pen position
current_pos_y = CENTER_Y
last_pos_x = CENTER_X     # Last pen position
last_pos_y = CENTER_Y
calibrated = False
is_drawing = False
drawing_speed = 2  # How fast the "pen" moves (pixels per frame when drawing)

# Gyro movement detection
previous_yaw = 0
yaw_history = []  # Store recent yaw values
movement_threshold = 0.5  # Minimum degrees per frame to consider "moving"
history_length = 10  # Number of frames to check for movement
is_gyro_moving = False

# === FUNCTIONS ===
def calibrate_yaw():
    """Set current yaw as the reference (0 degrees)"""
    global yaw_offset, calibrated
    yaw_offset = yaw_angle
    calibrated = True
    print(f"Calibrated! Yaw offset set to: {yaw_offset}")

def get_calibrated_angle():
    """Get the calibrated yaw angle (relative to calibration point)"""
    if not calibrated:
        return yaw_angle
    calibrated_angle = yaw_angle - yaw_offset
    # Normalize to -180 to 180 range
    while calibrated_angle > 180:
        calibrated_angle -= 360
    while calibrated_angle < -180:
        calibrated_angle += 360
    return calibrated_angle

def detect_gyro_movement():
    """Detect if the gyro is currently moving"""
    global is_gyro_moving, yaw_history, previous_yaw
    
    if not calibrated:
        return False
    
    current_calibrated_yaw = get_calibrated_angle()
    
    # Add current yaw to history
    yaw_history.append(current_calibrated_yaw)
    
    # Keep history to specified length
    if len(yaw_history) > history_length:
        yaw_history.pop(0)
    
    # Need at least 3 readings to detect movement
    if len(yaw_history) < 3:
        is_gyro_moving = False
        return False
    
    # Calculate movement over recent frames
    recent_range = max(yaw_history[-5:]) - min(yaw_history[-5:]) if len(yaw_history) >= 5 else 0
    
    # Also check immediate change
    immediate_change = abs(current_calibrated_yaw - previous_yaw)
    
    # Consider moving if there's been recent range of movement or immediate change
    is_gyro_moving = (recent_range > movement_threshold) or (immediate_change > movement_threshold)
    
    previous_yaw = current_calibrated_yaw
    return is_gyro_moving

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
                # Reset pen position to center
                current_pos_x = CENTER_X
                current_pos_y = CENTER_Y
                last_pos_x = CENTER_X
                last_pos_y = CENTER_Y
                print("Drawing reset!")
            elif calibrate_button_rect.collidepoint(event.pos):
                calibrate_yaw()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_c:  # Press 'C' to calibrate
                calibrate_yaw()
            elif event.key == pygame.K_r:  # Press 'R' to reset
                draw_surface.fill((0, 0, 0))
                current_pos_x = CENTER_X
                current_pos_y = CENTER_Y
                last_pos_x = CENTER_X
                last_pos_y = CENTER_Y

    # === READ SERIAL DATA ===
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

    # === DETECT GYRO MOVEMENT ===
    detect_gyro_movement()

    # === DETERMINE IF DRAWING ===
    # Only draw when BOTH conditions are met:
    # 1. Object is detected within 10cm
    # 2. Gyro is actively moving
    if 0 < distance_cm <= 10 and is_gyro_moving:
        is_drawing = True
    else:
        is_drawing = False

    # === CALCULATE MOVEMENT DIRECTION ===
    if calibrated and is_drawing:
        # Get current physical direction
        current_angle = get_calibrated_angle()
        angle_rad = math.radians(current_angle)
        
        # Calculate movement direction
        dx = math.cos(angle_rad) * drawing_speed
        dy = math.sin(angle_rad) * drawing_speed
        
        # Update pen position
        last_pos_x = current_pos_x
        last_pos_y = current_pos_y
        current_pos_x += dx
        current_pos_y += dy
        
        # Keep pen within screen bounds
        current_pos_x = max(10, min(WIDTH - 10, current_pos_x))
        current_pos_y = max(10, min(HEIGHT - 10, current_pos_y))
        
        # Draw line from last position to current position
        pygame.draw.line(draw_surface, (0, 255, 0), 
                        (int(last_pos_x), int(last_pos_y)), 
                        (int(current_pos_x), int(current_pos_y)), 3)
        
        # Draw current pen position
        pygame.draw.circle(screen, (255, 255, 0), 
                          (int(current_pos_x), int(current_pos_y)), 5)
    
    # === DRAW DIRECTION INDICATOR ===
    if calibrated:
        # Current direction indicator (white line from center)
        current_angle = get_calibrated_angle()
        angle_rad = math.radians(current_angle)
        dx_indicator = math.cos(angle_rad)
        dy_indicator = math.sin(angle_rad)
        
        indicator_length = 60
        indicator_x = int(CENTER_X + dx_indicator * indicator_length)
        indicator_y = int(CENTER_Y + dy_indicator * indicator_length)
        
        # Draw direction line
        color = (255, 255, 255) if is_drawing else (100, 100, 100)
        pygame.draw.line(screen, color, (CENTER_X, CENTER_Y), 
                        (indicator_x, indicator_y), 2)
        
        # Draw center point
        pygame.draw.circle(screen, (255, 255, 255), (CENTER_X, CENTER_Y), 3)
        
        # Reference direction (calibration line in blue)
        ref_x = int(CENTER_X + 50)
        ref_y = int(CENTER_Y)
        pygame.draw.line(screen, (0, 0, 255), (CENTER_X, CENTER_Y), 
                        (ref_x, ref_y), 1)

    # === DRAW CURRENT PEN POSITION ===
    if is_drawing:
        # Green circle for active drawing (both conditions met)
        pygame.draw.circle(screen, (0, 255, 0), 
                          (int(current_pos_x), int(current_pos_y)), 6)
    elif 0 < distance_cm <= 10 and not is_gyro_moving:
        # Yellow circle for object detected but gyro not moving
        pygame.draw.circle(screen, (255, 255, 0), 
                          (int(current_pos_x), int(current_pos_y)), 5)
    else:
        # Red circle for not drawing (too far from object or other issues)
        pygame.draw.circle(screen, (255, 0, 0), 
                          (int(current_pos_x), int(current_pos_y)), 4)

    # === UI ELEMENTS ===
    # Reset button
    pygame.draw.rect(screen, (200, 0, 0), reset_button_rect)
    reset_text = font.render("RESET", True, (255, 255, 255))
    screen.blit(reset_text, (WIDTH - 85, 15))
    
    # Calibrate button
    color = (0, 200, 0) if calibrated else (100, 100, 100)
    pygame.draw.rect(screen, color, calibrate_button_rect)
    cal_text = font.render("CALIB", True, (255, 255, 255))
    screen.blit(cal_text, (WIDTH - 85, 55))

    # === STATUS TEXT ===
    distance_text = font.render(f"Distance: {distance_cm} cm", True, (255, 255, 255))
    screen.blit(distance_text, (10, 10))
    
    yaw_text = font.render(f"Raw Yaw: {yaw_angle:.1f}°", True, (255, 255, 255))
    screen.blit(yaw_text, (10, 35))
    
    if calibrated:
        current_angle = get_calibrated_angle()
        cal_yaw_text = font.render(f"Direction: {current_angle:.1f}°", True, (0, 255, 0))
        screen.blit(cal_yaw_text, (10, 60))
        
        # More detailed drawing status
        if is_drawing:
            drawing_status = "DRAWING"
            status_color = (0, 255, 0)
        elif 0 < distance_cm <= 10 and not is_gyro_moving:
            drawing_status = "OBJECT DETECTED - NOT MOVING"
            status_color = (255, 255, 0)
        elif distance_cm > 10 and is_gyro_moving:
            drawing_status = "MOVING - NO OBJECT"
            status_color = (255, 100, 100)
        else:
            drawing_status = "NOT DRAWING"
            status_color = (255, 0, 0)
            
        status_text = font.render(f"Status: {drawing_status}", True, status_color)
        screen.blit(status_text, (10, 85))
        
        # Movement indicator
        movement_status = "MOVING" if is_gyro_moving else "STATIONARY"
        movement_color = (0, 255, 0) if is_gyro_moving else (150, 150, 150)
        movement_text = font.render(f"Gyro: {movement_status}", True, movement_color)
        screen.blit(movement_text, (10, 110))
    else:
        status_text = font.render("Status: Press 'C' or CALIB to calibrate", True, (255, 255, 0))
        screen.blit(status_text, (10, 60))
    
    pen_pos_text = font.render(f"Pen: ({int(current_pos_x)}, {int(current_pos_y)})", True, (255, 255, 255))
    screen.blit(pen_pos_text, (10, 135))
    
    # Instructions
    inst_text = font.render("Green=Drawing, Yellow=Object but not moving, Red=Not drawing", True, (200, 200, 200))
    screen.blit(inst_text, (10, HEIGHT - 30))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()