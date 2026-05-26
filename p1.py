import pygame
import pymunk
import pymunk.pygame_util
import math

# --- CONFIGURACIÓN DE PYGAME ---
pygame.init()
WIDTH, HEIGHT = 1200, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Simulador Orbital: Atmósfera Realista")
clock = pygame.time.Clock()
draw_options = pymunk.pygame_util.DrawOptions(screen)

# --- CONFIGURACIÓN DE PYMUNK ---
space = pymunk.Space() 
space.iterations = 30  

# Constantes del Planeta
G = 150000  
PLANET_MASS = 100
PLANET_RADIUS = 120
PLANET_POS = (WIDTH // 2, HEIGHT // 2)
PLANET_W = 0.5  # Velocidad angular (rotación del planeta)

# Constantes de la Atmósfera
ATMOSPHERE_RADIUS = 250
DRAG_COEFFICIENT = 0.5  # Cuánta resistencia opone el aire

# --- CREAR EL PLANETA ---
planet_body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
planet_body.position = PLANET_POS
planet_body.angular_velocity = PLANET_W
planet_shape = pymunk.Circle(planet_body, PLANET_RADIUS)
planet_shape.color = pygame.Color("blue")
planet_shape.friction = 0.1 # Fricción mínima, ya no dependemos de ella
space.add(planet_body, planet_shape)

# --- CREAR EL COHETE ---
rocket_mass = 1
rocket_radius = 12 
moment = pymunk.moment_for_circle(rocket_mass, 0, rocket_radius)
rocket_body = pymunk.Body(rocket_mass, moment)
rocket_body.position = (PLANET_POS[0], PLANET_POS[1] - PLANET_RADIUS - rocket_radius - 1)

# ¡MAGIA AQUÍ! Le damos al cohete la velocidad inicial de la rotación de la Tierra
# Calculamos la distancia relativa al centro
rx = rocket_body.position.x - PLANET_POS[0]
ry = rocket_body.position.y - PLANET_POS[1]
# v = w * r (Vector perpendicular)
rocket_body.velocity = (-ry * PLANET_W, rx * PLANET_W)

rocket_shape = pymunk.Circle(rocket_body, rocket_radius)
rocket_shape.color = pygame.Color("red")
rocket_shape.friction = 0.1
space.add(rocket_body, rocket_shape)

# --- FUNCIÓN DE FÍSICAS (Gravedad + Atmósfera) ---
def apply_forces(rocket, planet_pos, g_const, planet_mass, w, atm_radius, drag_c):
    # Vector desde el cohete hacia el centro del planeta
    dx_center = planet_pos[0] - rocket.position.x
    dy_center = planet_pos[1] - rocket.position.y
    distance_sq = dx_center**2 + dy_center**2
    
    if distance_sq == 0: 
        return
        
    distance = math.sqrt(distance_sq)
    
    # 1. APLICAR GRAVEDAD
    force_mag = g_const * (rocket.mass * planet_mass) / distance_sq
    angle = math.atan2(dy_center, dx_center)
    gx = math.cos(angle) * force_mag
    gy = math.sin(angle) * force_mag
    rocket.apply_force_at_world_point((gx, gy), (0, 0))

    # 2. APLICAR ARRASTRE ATMOSFÉRICO (Viento Rotacional)
    if distance < atm_radius:
        # Vector desde el centro del planeta hacia el cohete
        rx = rocket.position.x - planet_pos[0]
        ry = rocket.position.y - planet_pos[1]
        
        # Velocidad de la atmósfera en el punto exacto del cohete
        wind_vx = -ry * w
        wind_vy = rx * w
        
        # Velocidad relativa (Cohete vs Viento)
        rel_vx = rocket.velocity.x - wind_vx
        rel_vy = rocket.velocity.y - wind_vy
        
        # Fricción aerodinámica: Se opone a la velocidad relativa
        drag_fx = -drag_c * rel_vx
        drag_fy = -drag_c * rel_vy
        rocket.apply_force_at_world_point((drag_fx, drag_fy), (0, 0))

# --- BUCLE PRINCIPAL ---
running = True
thrust_power = 2000  # Necesitarás más empuje para vencer el aire!
fps = 60
physics_steps = 5  

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    
    # --- EMPUJE DEL COHETE ---
    if keys[pygame.K_UP]:
        dx = rocket_body.position.x - PLANET_POS[0]
        dy = rocket_body.position.y - PLANET_POS[1]
        angle = math.atan2(dy, dx)
        
        thrust_x = math.cos(angle) * thrust_power
        thrust_y = math.sin(angle) * thrust_power
        rocket_body.apply_force_at_world_point((thrust_x, thrust_y), (0, 0))

    # AplicarGravedad y Atmósfera
    apply_forces(rocket_body, PLANET_POS, G, PLANET_MASS, PLANET_W, ATMOSPHERE_RADIUS, DRAG_COEFFICIENT)

    # Actualizar física
    for _ in range(physics_steps):
        space.step((1 / fps) / physics_steps)

    # Renderizar
    screen.fill(pygame.Color("black"))
    
    # Dibujar límite de la atmósfera para que puedas verla
    pygame.draw.circle(screen, (30, 30, 50), PLANET_POS, ATMOSPHERE_RADIUS, 2)
    
    space.debug_draw(draw_options)
    pygame.display.flip()
    
    clock.tick(fps)

pygame.quit()