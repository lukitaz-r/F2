import pygame
import pymunk
import pymunk.pygame_util
import math

# --- CONFIGURACIÓN DE PYGAME ---
pygame.init()
WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Simulador Orbital: Inyección Precisa")
clock = pygame.time.Clock()
draw_options = pymunk.pygame_util.DrawOptions(screen)

# --- CONFIGURACIÓN DE PYMUNK ---
space = pymunk.Space() 
space.iterations = 30  

G = 80000  
PLANET_MASS = 100
PLANET_RADIUS = 100
PLANET_POS = (WIDTH // 2, HEIGHT // 2)
PLANET_W = 0.5  

ATMOSPHERE_RADIUS = 180
TARGET_ORBIT = 280  
DRAG_COEFFICIENT = 0.5  

# --- CREAR EL PLANETA ---
planet_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
planet_body.position = PLANET_POS
planet_body.angular_velocity = PLANET_W
planet_shape = pymunk.Circle(planet_body, PLANET_RADIUS)
planet_shape.color = pygame.Color("blue")
planet_shape.friction = 0.1 
space.add(planet_body, planet_shape)

# --- CREAR EL COHETE ---
rocket_mass = 1
rocket_radius = 10 
moment = pymunk.moment_for_circle(rocket_mass, 0, rocket_radius)
rocket_body = pymunk.Body(rocket_mass, moment)
rocket_body.position = (PLANET_POS[0], PLANET_POS[1] - PLANET_RADIUS - rocket_radius - 1)

rx = rocket_body.position.x - PLANET_POS[0]
ry = rocket_body.position.y - PLANET_POS[1]
rocket_body.velocity = (-ry * PLANET_W, rx * PLANET_W)

rocket_shape = pymunk.Circle(rocket_body, rocket_radius)
rocket_shape.color = pygame.Color("red")
rocket_shape.friction = 0.1
space.add(rocket_body, rocket_shape)

# --- FUNCIÓN DE FÍSICAS ---
def apply_forces(rocket, planet_pos, g_const, planet_mass, w, atm_radius, drag_c):
    dx_center = planet_pos[0] - rocket.position.x
    dy_center = planet_pos[1] - rocket.position.y
    distance_sq = dx_center**2 + dy_center**2
    
    if distance_sq == 0: return
    distance = math.sqrt(distance_sq)
    
    force_mag = g_const * (rocket.mass * planet_mass) / distance_sq
    angle = math.atan2(dy_center, dx_center)
    gx = math.cos(angle) * force_mag
    gy = math.sin(angle) * force_mag
    rocket.apply_force_at_world_point((gx, gy), rocket.position)

    if distance < atm_radius:
        rx = rocket.position.x - planet_pos[0]
        ry = rocket.position.y - planet_pos[1]
        wind_vx = -ry * w
        wind_vy = rx * w
        rel_vx = rocket.velocity.x - wind_vx
        rel_vy = rocket.velocity.y - wind_vy
        drag_fx = -drag_c * rel_vx
        drag_fy = -drag_c * rel_vy
        rocket.apply_force_at_world_point((drag_fx, drag_fy), rocket.position)

# --- BUCLE PRINCIPAL ---
running = True
thrust_power = 2500  
fps = 60
physics_steps = 5  

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    thrust_x = 0
    thrust_y = 0

    # --- PILOTO AUTOMÁTICO INTELIGENTE (Controlador PD) ---
    dx = rocket_body.position.x - PLANET_POS[0]
    dy = rocket_body.position.y - PLANET_POS[1]
    dist = math.hypot(dx, dy)
    
    if dist > 0:
        # Vectores direccionales
        nx = dx / dist
        ny = dy / dist
        tx = -ny
        ty = nx
        
        # Descomponer la velocidad actual
        vx, vy = rocket_body.velocity
        v_radial = vx * nx + vy * ny      # Qué tan rápido sube/baja
        v_tangent = vx * tx + vy * ty     # Qué tan rápido va de lado
        
        v_required = math.sqrt(G * PLANET_MASS / dist)
        
        # 1. Eje Radial (Controlar altitud frenando si sube muy rápido)
        error_dist = TARGET_ORBIT - dist
        # Multiplicamos la distancia por 15, y le RESTAMOS la velocidad multiplicada por 40 para frenar
        fuerza_radial = (error_dist * 15) - (v_radial * 40)
        # Sujetamos la fuerza al límite del motor
        fuerza_radial = max(min(fuerza_radial, thrust_power), -thrust_power)
        
        # 2. Eje Tangencial (Controlar la inyección orbital)
        fuerza_tangencial = 0
        if dist > PLANET_RADIUS + 20: 
            error_vel = v_required - v_tangent
            fuerza_tangencial = error_vel * 40
            fuerza_tangencial = max(min(fuerza_tangencial, thrust_power), -thrust_power)
            
        # Recombinar fuerzas en X e Y
        thrust_x = (nx * fuerza_radial) + (tx * fuerza_tangencial)
        thrust_y = (ny * fuerza_radial) + (ty * fuerza_tangencial)
        
        # Solo aplicar empuje si es significativo (ahorro de cálculos)
        if abs(thrust_x) > 5 or abs(thrust_y) > 5:
            rocket_body.apply_force_at_world_point((thrust_x, thrust_y), rocket_body.position)

    apply_forces(rocket_body, PLANET_POS, G, PLANET_MASS, PLANET_W, ATMOSPHERE_RADIUS, DRAG_COEFFICIENT)

    for _ in range(physics_steps):
        space.step((1 / fps) / physics_steps)

    # --- RENDERIZADO VISUAL ---
    screen.fill(pygame.Color("black"))
    
    pygame.draw.circle(screen, (30, 30, 50), PLANET_POS, ATMOSPHERE_RADIUS, 1) 
    pygame.draw.circle(screen, (20, 50, 20), PLANET_POS, TARGET_ORBIT, 1)      
    
    space.debug_draw(draw_options)
    
    start_pos = (int(rocket_body.position.x), int(rocket_body.position.y))
    
    # Vector de Velocidad (Verde)
    vel_scale = 0.5
    end_vx = int(start_pos[0] + rocket_body.velocity.x * vel_scale)
    end_vy = int(start_pos[1] + rocket_body.velocity.y * vel_scale)
    pygame.draw.line(screen, (0, 255, 0), start_pos, (end_vx, end_vy), 3)
    pygame.draw.circle(screen, (0, 255, 0), (end_vx, end_vy), 4)

    # Vector de Empuje (Naranja)
    if abs(thrust_x) > 5 or abs(thrust_y) > 5:
        thrust_scale = 0.015 
        end_tx = int(start_pos[0] + thrust_x * thrust_scale)
        end_ty = int(start_pos[1] + thrust_y * thrust_scale)
        pygame.draw.line(screen, (255, 165, 0), start_pos, (end_tx, end_ty), 2)

    pygame.display.flip()
    clock.tick(fps)

pygame.quit()