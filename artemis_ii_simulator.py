"""
============================================================================
SIMULADOR DE LANZAMIENTO ARTEMIS II — FASE 1
Preparación → Lanzamiento → Órbita Terrestre
============================================================================
Motor de Física: Pymunk | Renderizado: Pygame | UI: pygame_gui
Datos técnicos basados en documentación oficial de NASA.
============================================================================
"""

import pygame
import pymunk
import pygame_gui
import math
import random
import sys
import os
import json
import tempfile
import atexit

# ============================================================================
# SECCIÓN 1: CONSTANTES Y DATOS TÉCNICOS
# ============================================================================

# Colores (Tema NASA Oscuro)
C_BG        = (5, 5, 15)
C_PANEL     = (10, 16, 32)
C_BORDER    = (0, 120, 180)
C_CYAN      = (0, 200, 255)
C_ORANGE    = (255, 140, 0)
C_WHITE     = (220, 220, 230)
C_RED       = (255, 60, 60)
C_GREEN     = (60, 255, 100)
C_YELLOW    = (255, 255, 80)
C_GRAY      = (140, 140, 150)
C_DGRAY     = (55, 55, 65)
C_EARTH     = (25, 70, 160)
C_EARTH_HI  = (35, 90, 190)
C_EARTH_DK  = (12, 35, 80)
C_SKY       = (15, 30, 80)

# Ventana
INIT_W, INIT_H = 1280, 720
FPS = 60
PANEL_W = 290  # Ancho panel telemetría

# Datos reales Artemis II / SLS Block 1 (NASA)
ARTEMIS = {
    "liftoff_mass_kg": 2_608_000,
    "total_thrust_N":  39_100_000,
    "srb_mass_each_kg": 725_748,   "srb_fuel_each_kg": 500_000,
    "srb_thrust_each_N": 16_013_000, "srb_burn_time_s": 126,
    "core_dry_mass_kg": 85_000,    "core_fuel_mass_kg": 907_184,
    "core_thrust_N": 8_900_000,    "core_burn_time_s": 480,
    "icps_fuel_mass_kg": 27_200,   "icps_thrust_N": 110_100,
    "orion_mass_kg": 35_000,       "crew_volume_m3": 9.0,
    "nominal_crew": 4,             "crew_mass_kg": 80,
}

# Física Pymunk  (calibrado a partir de p1.py / p2.py que funcionan)
G_CONST    = 1500
P_MASS     = 100
DEF_PR     = 200       # Radio planeta por defecto (px)
ATM_MULT   = 1.8       # Radio atmósfera = PR * ATM_MULT
ORB_MULT   = 2.5       # Órbita objetivo = PR * ORB_MULT
ROCKET_R   = 6         # Radio colisión cohete

# Masa normalizada del cohete (unidades Pymunk)
NORM_TOTAL = 3.0
_T = ARTEMIS["liftoff_mass_kg"]
SRB_FUEL_N   = 2 * ARTEMIS["srb_fuel_each_kg"]       / _T * NORM_TOTAL
SRB_STRUCT_N = 2 * (ARTEMIS["srb_mass_each_kg"] - ARTEMIS["srb_fuel_each_kg"]) / _T * NORM_TOTAL
CORE_FUEL_N  = ARTEMIS["core_fuel_mass_kg"]           / _T * NORM_TOTAL
CORE_STRUCT_N= ARTEMIS["core_dry_mass_kg"]            / _T * NORM_TOTAL
ICPS_FUEL_N  = ARTEMIS["icps_fuel_mass_kg"]           / _T * NORM_TOTAL
ICPS_STRUCT_N= 5000                                   / _T * NORM_TOTAL
ORION_N      = ARTEMIS["orion_mass_kg"]               / _T * NORM_TOTAL

# Tiempos de quemado en segundos de pared (wall-clock) a 1x
SRB_BURN_T  = 9.0    # SRBs arden 9 s
CORE_BURN_T = 28.0   # Core stage arde 28 s
ICPS_BURN_T = 24.0   # ICPS arde hasta 24 s

# Factor para mostrar "tiempo de misión" realista
MISSION_TIME_MULT = 15.0  # Solo para display, no afecta física

MAX_CREW = int(ARTEMIS["crew_volume_m3"] / 0.5)  # ~18

# ============================================================================
# SECCIÓN 2: TEMA pygame_gui (mínimo — solo colores)
# ============================================================================
_THEME = {
    "defaults": {
        "colours": {
            "dark_bg": "#060C1A", "normal_bg": "#0E1628",
            "hovered_bg": "#162040", "disabled_bg": "#080C14",
            "selected_bg": "#1A2E50", "active_bg": "#122038",
            "normal_text": "#D0D4DE", "hovered_text": "#FFFFFF",
            "disabled_text": "#445060",
            "normal_border": "#007898", "hovered_border": "#00B8E8",
            "disabled_border": "#223040",
            "filled_bar": "#E07800", "unfilled_bar": "#162040"
        }
    },
    "button": {
        "colours": {
            "normal_bg": "#082040", "hovered_bg": "#0E3058",
            "normal_border": "#0090B0", "hovered_border": "#00C8FF"
        },
        "misc": {"border_width": "2", "shape_corner_radius": "5"}
    }
}

def _make_theme_file():
    f = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8')
    json.dump(_THEME, f); f.close()
    atexit.register(lambda p=f.name: os.path.exists(p) and os.unlink(p))
    return f.name

# ============================================================================
# SECCIÓN 3: PARTÍCULAS Y ESTRELLAS
# ============================================================================
class Particle:
    __slots__ = ['x','y','vx','vy','life','ml','r','g','b','sz']
    def __init__(s,x,y,vx,vy,life,col,sz):
        s.x=x; s.y=y; s.vx=vx; s.vy=vy; s.life=s.ml=life
        s.r,s.g,s.b=col; s.sz=sz
    def update(s,dt):
        s.x+=s.vx*dt; s.y+=s.vy*dt; s.life-=dt
    def alive(s): return s.life>0

class Particles:
    def __init__(s): s.p=[]
    def fire(s,x,y,dx,dy,n=3):
        for _ in range(n):
            sp=random.uniform(50,160)
            c=random.choice([(255,255,100),(255,190,40),(255,130,0),(255,70,15)])
            s.p.append(Particle(x,y, dx*sp+random.uniform(-20,20), dy*sp+random.uniform(-20,20),
                                random.uniform(.15,.45), c, random.uniform(2,5)))
    def smoke(s,x,y,dx,dy):
        for _ in range(2):
            g=random.randint(90,170); sp=random.uniform(12,40)
            s.p.append(Particle(x+random.uniform(-4,4),y, dx*sp+random.uniform(-15,15),
                                dy*sp+random.uniform(-15,15), random.uniform(.5,1.2),(g,g,g), random.uniform(3,8)))
    def explosion(s,x,y,n=55):
        for _ in range(n):
            a=random.uniform(0,6.28); sp=random.uniform(35,250)
            c=random.choice([(255,255,100),(255,170,30),(255,90,15),(255,255,255)])
            s.p.append(Particle(x,y,math.cos(a)*sp,math.sin(a)*sp, random.uniform(.3,1.2),c, random.uniform(2,6)))
    def sep(s,x,y,n=22):
        for _ in range(n):
            a=random.uniform(0,6.28); sp=random.uniform(12,80)
            c=random.choice([(210,210,210),(255,200,100),(255,255,190)])
            s.p.append(Particle(x,y,math.cos(a)*sp,math.sin(a)*sp, random.uniform(.2,.7),c, random.uniform(1,3)))
    def update(s,dt):
        for pp in s.p: pp.update(dt)
        s.p=[pp for pp in s.p if pp.alive()]
    def draw(s,surf,cam,sw,sh):
        for pp in s.p:
            f=max(0,pp.life/pp.ml); sx,sy=cam.w2s(pp.x,pp.y,sw,sh)
            sz=max(1,int(pp.sz*cam.zoom*f))
            if -sz<sx<sw+sz and -sz<sy<sh+sz:
                pygame.draw.circle(surf,(int(pp.r*f),int(pp.g*f),int(pp.b*f)),(sx,sy),sz)

class Stars:
    def __init__(s,n=160,span=5000):
        s.s=[(random.uniform(-span,span),random.uniform(-span,span),
              random.randint(110,255),random.choice([1,1,1,2]),
              random.uniform(1,3.5),random.uniform(0,6.28)) for _ in range(n)]
        s.t=0
    def update(s,dt): s.t+=dt
    def draw(s,surf,cam,sw,sh):
        for wx,wy,bri,sz,ts,to in s.s:
            sx=int((wx-cam.x*.03)*.1*cam.zoom+sw/2)%sw
            sy=int((wy-cam.y*.03)*.1*cam.zoom+sh/2)%sh
            b=int(bri*(.6+.4*math.sin(s.t*ts+to)))
            pygame.draw.circle(surf,(b,b,min(255,b+12)),(sx,sy),sz)

# ============================================================================
# SECCIÓN 4: CÁMARA
# ============================================================================
class Camera:
    def __init__(s):
        s.x=s.y=0.; s.zoom=2.0; s.tx=s.ty=0.; s.tz=2.0; s.spd=3.0
    def w2s(s,wx,wy,sw,sh):
        return(int((wx-s.x)*s.zoom+sw/2), int((wy-s.y)*s.zoom+sh/2))
    def snap(s,x,y,z): s.x=s.tx=x; s.y=s.ty=y; s.zoom=s.tz=z
    def target(s,x,y,z): s.tx=x; s.ty=y; s.tz=z
    def update(s,dt):
        t=min(1.,s.spd*dt)
        s.x+=(s.tx-s.x)*t; s.y+=(s.ty-s.y)*t; s.zoom+=(s.tz-s.zoom)*t

# ============================================================================
# SECCIÓN 5: DIBUJO PROGRAMÁTICO DEL COHETE
# ============================================================================
def _rot(pts, a, cx=0, cy=0):
    c,s=math.cos(a),math.sin(a)
    return [(cx+(px-cx)*c-(py-cy)*s, cy+(px-cx)*s+(py-cy)*c) for px,py in pts]

def draw_rocket(surf, sx, sy, angle, zoom, stg, flames):
    """Dibuja el cohete con etapas separables. stg=dict(srb,core,icps,orion)."""
    sc = max(0.2, zoom * 0.4)
    parts = []

    if stg.get('orion'):
        parts.append(([( 0,-38*sc),(-2*sc,-30*sc),(2*sc,-30*sc)], (200,200,200)))
        parts.append(([(-6*sc,-30*sc),(6*sc,-30*sc),(8*sc,-22*sc),(-8*sc,-22*sc)], (235,235,240)))
    if stg.get('icps'):
        parts.append(([(-5*sc,-22*sc),(5*sc,-22*sc),(5*sc,-13*sc),(-5*sc,-13*sc)], (155,160,170)))
    if stg.get('core'):
        parts.append(([(-6*sc,-13*sc),(6*sc,-13*sc),(6*sc,20*sc),(-6*sc,20*sc)], (95,100,112)))
        parts.append(([(-6*sc,-5*sc),(6*sc,-5*sc),(6*sc,-3*sc),(-6*sc,-3*sc)], (195,95,25)))
        for nx in [-4,-1.5,1.5,4]:
            parts.append(([(nx*sc-1.5*sc,20*sc),(nx*sc+1.5*sc,20*sc),
                           (nx*sc+2*sc,24*sc),(nx*sc-2*sc,24*sc)], (65,65,75)))
    if stg.get('srb'):
        for side in [-1,1]:
            bx=side*10*sc
            parts.append(([(bx-3*sc,-8*sc),(bx+3*sc,-8*sc),(bx+3*sc,22*sc),(bx-3*sc,22*sc)], (215,215,220)))
            parts.append(([(bx-3*sc,0),(bx+3*sc,0),(bx+3*sc,2*sc),(bx-3*sc,2*sc)], (175,35,35)))
            parts.append(([(bx-2.5*sc,22*sc),(bx+2.5*sc,22*sc),(bx+3.5*sc,26*sc),(bx-3.5*sc,26*sc)],(65,65,75)))

    for pts,col in parts:
        rp = _rot(pts, angle)
        sp = [(int(px+sx),int(py+sy)) for px,py in rp]
        if len(sp)>=3:
            pygame.draw.polygon(surf, col, sp)
            pygame.draw.polygon(surf, tuple(min(255,c+25) for c in col), sp, 1)

    if flames:
        t = pygame.time.get_ticks()/100.
        positions = []
        if stg.get('core') and stg.get('srb'):
            for nx in [-2,0,2]: positions.append((nx*sc, 1.0))
            for side in [-1,1]:  positions.append((side*10*sc, 1.4))
        elif stg.get('core'):
            for nx in [-2,0,2]: positions.append((nx*sc, 0.9))
        elif stg.get('icps'):
            positions.append((0, 0.5))

        for fx, fmul in positions:
            flk = .65 + .35*math.sin(t*7+fx*2)
            fh = sc*12*flk*fmul;  fw = sc*3*flk*fmul
            fp = [(fx-fw,24*sc),(fx+fw,24*sc),(fx+fw*.3,24*sc+fh*.7),(fx,24*sc+fh),(fx-fw*.3,24*sc+fh*.7)]
            rp = _rot(fp, angle); sp=[(int(px+sx),int(py+sy)) for px,py in rp]
            if len(sp)>=3: pygame.draw.polygon(surf,(255,int(110*flk),8),sp)
            fi = [(fx-fw*.4,24*sc),(fx+fw*.4,24*sc),(fx,24*sc+fh*.55)]
            ri = _rot(fi, angle); si=[(int(px+sx),int(py+sy)) for px,py in ri]
            if len(si)>=3: pygame.draw.polygon(surf,(255,255,int(130*flk)),si)

def draw_rocket_small(surf, sx, sy, angle, zoom):
    sz=max(3,int(5*zoom))
    pts=_rot([(0,-sz),(- sz*.5,sz*.5),(sz*.5,sz*.5)], angle)
    sp=[(int(px+sx),int(py+sy)) for px,py in pts]
    if len(sp)>=3:
        pygame.draw.polygon(surf,C_WHITE,sp); pygame.draw.polygon(surf,C_CYAN,sp,1)

# ============================================================================
# SECCIÓN 6: SIMULADOR PRINCIPAL
# ============================================================================
class Sim:
    def __init__(self):
        pygame.init()
        self.scr = pygame.display.set_mode((INIT_W, INIT_H), pygame.RESIZABLE)
        pygame.display.set_caption("ARTEMIS II — Simulador de Lanzamiento | Fase 1")
        self.clock = pygame.time.Clock()
        self.sw, self.sh = INIT_W, INIT_H

        self.theme_path = _make_theme_file()
        self.mgr = pygame_gui.UIManager((self.sw, self.sh), self.theme_path)

        self.parts = Particles(); self.stars = Stars(); self.cam = Camera()

        self.state = "MENU"  # MENU | SIM | END
        self.phase = "PREFLIGHT"
        self.running = True

        # Config (sliders)
        self.cfg = dict(fuel_srb=100., fuel_core=100., fuel_icps=100.,
                        crew=4, efficiency=100., throttle=100., extra_mass=0.,
                        planet_r=float(DEF_PR), gravity=9.81, wind=0.,
                        drag_cd=0.5, atm_density=1.0, time_scale=1.)

        # Pymunk
        self.space = None; self.planet_body=None; self.rbody=None; self.rshape=None
        self.debris = []

        # Sim state
        self.sim_t = 0.; self.fuel={}; self.fuelmax={}
        self.stg = dict(srb=True,core=True,icps=True,orion=True)
        self.orbit_tmr=0.; self.cd_tmr=5.; self.sep_tmr=0.
        self.fail_msg=""; self.trail=[]; self.trail_t=0.
        self.view="LATERAL"; self.eng_on=False
        self.thrust_total=0.; self.thrust_core=0.; self.thrust_icps=0.

        # Fonts
        self.f_title = pygame.font.SysFont("Consolas",40,bold=True)
        self.f_big   = pygame.font.SysFont("Consolas",26,bold=True)
        self.f_med   = pygame.font.SysFont("Consolas",17)
        self.f_sm    = pygame.font.SysFont("Consolas",13)
        self.f_cd    = pygame.font.SysFont("Consolas",68,bold=True)

        # UI
        self.ui_els=[]; self.sliders={}; self.sl_labels={}; self.buttons={}
        self._build_menu()

    # ── UI helpers ──────────────────────────────────────────────────────
    def _clear_ui(self):
        for e in self.ui_els: e.kill()
        self.ui_els.clear(); self.sliders.clear(); self.sl_labels.clear(); self.buttons.clear()

    def _slider(self, x, y, w, h, key, val, lo, hi, txt):
        lbl = pygame_gui.elements.UILabel(
            relative_rect=pygame.Rect((x,y-20),(w,20)),
            text=f"{txt}: {val:.1f}" if isinstance(val,float) else f"{txt}: {val}",
            manager=self.mgr)
        sl = pygame_gui.elements.UIHorizontalSlider(
            relative_rect=pygame.Rect((x,y),(w,h)),
            start_value=val, value_range=(lo,hi), manager=self.mgr)
        self.ui_els+=[lbl,sl]; self.sliders[key]=sl; self.sl_labels[key]=(lbl,txt)

    def _read_sliders(self):
        for k,sl in self.sliders.items():
            v = sl.get_current_value()
            if k in ("crew","extra_mass"): v=int(round(v))
            elif k=="time_scale": v=round(v,1)
            self.cfg[k]=v
            if k in self.sl_labels:
                lb,tx=self.sl_labels[k]
                lb.set_text(f"{tx}: {v}" if isinstance(v,int) else f"{tx}: {v:.2f}")

    # ── Pantallas UI ────────────────────────────────────────────────────
    def _build_menu(self):
        self._clear_ui()
        sw,sh=self.sw,self.sh
        cw=int(sw*0.38); gap=50; slh=20
        c1=int(sw*0.04); c2=int(sw*0.50)
        y0=120

        y=y0
        self._slider(c1,y,cw,slh,"fuel_srb",self.cfg["fuel_srb"],10,150,"Combustible SRBs (%)"); y+=gap
        self._slider(c1,y,cw,slh,"fuel_core",self.cfg["fuel_core"],10,150,"Combustible Core (%)"); y+=gap
        self._slider(c1,y,cw,slh,"fuel_icps",self.cfg["fuel_icps"],10,150,"Combustible ICPS (%)"); y+=gap
        self._slider(c1,y,cw,slh,"crew",self.cfg["crew"],1,MAX_CREW,"Tripulantes"); y+=gap
        self._slider(c1,y,cw,slh,"efficiency",self.cfg["efficiency"],50,120,"Eficiencia (%)"); y+=gap
        self._slider(c1,y,cw,slh,"throttle",self.cfg["throttle"],65,109,"Potencia Motores (%)"); y+=gap
        self._slider(c1,y,cw,slh,"extra_mass",self.cfg["extra_mass"],0,10000,"Carga Extra (kg)")

        y=y0
        self._slider(c2,y,cw,slh,"planet_r",self.cfg["planet_r"],80,350,"Radio Planeta (px)"); y+=gap
        self._slider(c2,y,cw,slh,"gravity",self.cfg["gravity"],1.,30.,"Gravedad (m/s²)"); y+=gap
        self._slider(c2,y,cw,slh,"wind",self.cfg["wind"],0.,50.,"Viento (m/s)"); y+=gap
        self._slider(c2,y,cw,slh,"drag_cd",self.cfg["drag_cd"],0.05,2.,"Coef. Drag (Cd)"); y+=gap
        self._slider(c2,y,cw,slh,"atm_density",self.cfg["atm_density"],0.1,3.,"Densidad Atm. (×ρ₀)")

        bw,bh=300,50
        btn = pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect(((sw-bw)//2, sh-90),(bw,bh)),
            text="INICIAR LANZAMIENTO", manager=self.mgr)
        self.ui_els.append(btn); self.buttons["start"]=btn

    def _build_sim(self):
        self._clear_ui()
        sw,sh=self.sw,self.sh
        px=sw-PANEL_W+12; slw=PANEL_W-35; slh=16; gap=36
        y=346
        self._slider(px,y,slw,slh,"planet_r",self.cfg["planet_r"],80,350,"Radio Planeta"); y+=gap
        self._slider(px,y,slw,slh,"gravity",self.cfg["gravity"],1.,30.,"Gravedad"); y+=gap
        self._slider(px,y,slw,slh,"wind",self.cfg["wind"],0.,50.,"Viento"); y+=gap
        self._slider(px,y,slw,slh,"drag_cd",self.cfg["drag_cd"],0.05,2.,"Drag Cd"); y+=gap
        self._slider(px,y,slw,slh,"atm_density",self.cfg["atm_density"],0.1,3.,"Densidad Atm."); y+=gap
        self._slider(px,y,slw,slh,"time_scale",self.cfg["time_scale"],1.,10.,"Velocidad")

    def _build_end(self):
        self._clear_ui()
        sw,sh=self.sw,self.sh; bw,bh=200,48; cx=sw//2
        b1=pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx-bw-15,sh//2+70),(bw,bh)),
            text="REINICIAR", manager=self.mgr)
        b2=pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((cx+15,sh//2+70),(bw,bh)),
            text="SALIR", manager=self.mgr)
        self.ui_els+=[b1,b2]; self.buttons["restart"]=b1; self.buttons["quit"]=b2

    # ── Física ──────────────────────────────────────────────────────────
    def _init_physics(self):
        self.space = pymunk.Space(); self.space.iterations=20
        pr = int(self.cfg["planet_r"])

        # Planeta
        self.planet_body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.planet_body.position = (0,0)
        ps = pymunk.Circle(self.planet_body, pr)
        ps.friction=.5; ps.collision_type=1
        self.space.add(self.planet_body, ps)
        self._planet_shape = ps

        # Masa extra de tripulación y carga
        crew_extra = max(0,(self.cfg["crew"]-ARTEMIS["nominal_crew"]))*ARTEMIS["crew_mass_kg"]
        extra_n = (crew_extra + self.cfg["extra_mass"]) / _T * NORM_TOTAL

        # Combustible
        self.fuel = dict(srb=SRB_FUEL_N*(self.cfg["fuel_srb"]/100),
                         core=CORE_FUEL_N*(self.cfg["fuel_core"]/100),
                         icps=ICPS_FUEL_N*(self.cfg["fuel_icps"]/100))
        self.fuelmax = dict(self.fuel)

        tot_mass = (SRB_STRUCT_N + self.fuel["srb"] + CORE_STRUCT_N + self.fuel["core"]
                    + ICPS_STRUCT_N + self.fuel["icps"] + ORION_N + extra_n + 0.05)

        # Cohete
        mom = pymunk.moment_for_circle(tot_mass, 0, ROCKET_R)
        self.rbody = pymunk.Body(tot_mass, mom)
        self.rbody.position = (0, -(pr + ROCKET_R + 3))
        # Inicia estrictamente estático en la plataforma para evitar el gancho inicial
        self.rbody.velocity = (0.0, 0.0)
        self.rshape = pymunk.Circle(self.rbody, ROCKET_R)
        self.rshape.sensor = True  # sin colisión directa
        self.space.add(self.rbody, self.rshape)

        # Empuje calibrado para TWR ≈ 1.22
        g_surf = G_CONST * P_MASS / (pr*pr)
        self.thrust_total = 1.22 * tot_mass * g_surf   # SRB+Core
        self.thrust_core  = self.thrust_total * 0.55    # Solo Core
        self.thrust_icps  = self.thrust_total * 0.15    # ICPS (bajo)

        # Reset
        self.debris=[]; self.trail=[]; self.trail_t=0
        self.stg=dict(srb=True,core=True,icps=True,orion=True)
        self.sim_t=0.; self.orbit_tmr=0.; self.sep_tmr=0.; self.eng_on=False
        self.view="LATERAL"; self.fail_msg=""
        self.parts.p.clear()

        # Cámara inicial: mostrar cohete sobre el planeta
        self.cam.snap(0, -(pr+50), 1.8)

    def _grav(self, body):
        dx,dy = -body.position.x, -body.position.y
        d2=dx*dx+dy*dy
        if d2<1: return
        d=math.sqrt(d2); gs=self.cfg["gravity"]/9.81
        fm = G_CONST*gs*(body.mass*P_MASS)/d2
        a=math.atan2(dy,dx)
        body.apply_force_at_world_point((math.cos(a)*fm, math.sin(a)*fm), body.position)

    def _drag(self, body):
        pr=self.cfg["planet_r"]; atm_r=pr*ATM_MULT*self.cfg["atm_density"]
        d=math.hypot(*body.position)
        if d<atm_r and d>pr:
            af=max(0, 1-(d-pr)/(atm_r-pr))*self.cfg["atm_density"]
            vx,vy=body.velocity; sp=math.hypot(vx,vy)
            if sp>.1:
                dm=.5*self.cfg["drag_cd"]*af*sp
                body.apply_force_at_world_point((-dm*vx,-dm*vy), body.position)

    def _wind(self, body):
        pr=self.cfg["planet_r"]; atm_r=pr*ATM_MULT*self.cfg["atm_density"]
        d=math.hypot(*body.position)
        if d<atm_r and d>pr and self.cfg["wind"]>.01:
            af=max(0,1-(d-pr)/(atm_r-pr))
            nx,ny=body.position.x/d, body.position.y/d
            tx,ty=-ny,nx
            wf=self.cfg["wind"]*af*body.mass*.4
            body.apply_force_at_world_point((tx*wf,ty*wf), body.position)

    def _thrust(self):
        if not self.eng_on: return
        rx,ry=self.rbody.position; d=math.hypot(rx,ry)
        if d<1: return
        nx,ny=rx/d,ry/d; tx,ty=-ny,nx
        thr=self.cfg["throttle"]/100.

        if self.phase=="ASCENT_SRB":
            mag=self.thrust_total*thr
            pr=self.cfg["planet_r"]
            vx,vy=self.rbody.velocity
            vt=vx*tx+vy*ty
            alt=max(0, d-pr-ROCKET_R-3)
            
            # Calculamos minidesviaciones por rotación en cada fotograma
            # La velocidad tangencial objetivo aumenta suavemente con la altitud
            vt_target = 14.0 * min(1.0, alt/300.0)
            
            # Fuerza tangencial para generar la parábola inicial
            ft=(vt_target-vt)*16.0*self.rbody.mass
            ft=max(-mag*0.5, min(mag*0.5, ft))
            
            # La fuerza restante se destina al empuje radial (vertical)
            fr=math.sqrt(max(0, mag**2 - ft**2))
            
            self.rbody.apply_force_at_world_point((nx*fr+tx*ft, ny*fr+ty*ft), self.rbody.position)
        elif self.phase=="ASCENT_CORE":
            # Autopilot vertical durante la etapa Core: mantiene trayectoria vertical y sube a la órbita
            pr=self.cfg["planet_r"]; target=pr*ORB_MULT
            vx,vy=self.rbody.velocity
            vr=vx*nx+vy*ny; vt=vx*tx+vy*ty
            ed=target-d
            alt=max(0, d-pr-ROCKET_R-3)
            
            mag = self.thrust_core * thr
            
            # Guiado vertical más rápido para alcanzar la órbita (menor amortiguación)
            fr=(ed*3.0-vr*10.0)*self.rbody.mass
            fr=max(-mag,min(mag,fr))
            # Velocidad tangencial objetivo aumenta con la altitud para una parábola de Coriolis perfecta
            vt_target = 14.0 * min(1.0, alt/300.0)
            ft=(vt_target-vt)*16.0*self.rbody.mass
            ft=max(-mag,min(mag,ft))
            self.rbody.apply_force_at_world_point((nx*fr+tx*ft, ny*fr+ty*ft), self.rbody.position)
        elif self.phase=="CIRC_ICPS":
            # Circularización en órbita con ICPS: mantiene altitud de órbita y acelera tangencialmente
            pr=self.cfg["planet_r"]; target=pr*ORB_MULT
            gs=self.cfg["gravity"]/9.81
            vo=math.sqrt(G_CONST*gs*P_MASS/d) if d>1 else 0
            vx,vy=self.rbody.velocity
            vr=vx*nx+vy*ny; vt=vx*tx+vy*ty
            ed=target-d; ev=vo-vt
            
            mag = self.thrust_icps * thr
            
            fr=(ed*2.0-vr*25.0)*self.rbody.mass
            fr=max(-mag,min(mag,fr))
            ft=ev*16.0*self.rbody.mass
            ft=max(-mag,min(mag,ft))
            self.rbody.apply_force_at_world_point((nx*fr+tx*ft, ny*fr+ty*ft), self.rbody.position)

    def _burn_fuel(self, dt):
        if not self.eng_on: return
        thr=self.cfg["throttle"]/100.; eff=max(.01,self.cfg["efficiency"]/100.)
        used=0
        if self.phase=="ASCENT_SRB":
            sr=SRB_FUEL_N/SRB_BURN_T*thr/eff; cr=CORE_FUEL_N/CORE_BURN_T*thr/eff
            su=min(self.fuel["srb"],sr*dt); cu=min(self.fuel["core"],cr*dt)
            self.fuel["srb"]-=su; self.fuel["core"]-=cu; used=su+cu
        elif self.phase=="ASCENT_CORE":
            cr=CORE_FUEL_N/CORE_BURN_T*thr/eff
            cu=min(self.fuel["core"],cr*dt); self.fuel["core"]-=cu; used=cu
        elif self.phase=="CIRC_ICPS":
            ir=ICPS_FUEL_N/ICPS_BURN_T*thr/eff
            iu=min(self.fuel["icps"],ir*dt); self.fuel["icps"]-=iu; used=iu
        if used>0:
            nm=max(.05, self.rbody.mass-used)
            self.rbody.mass=nm; self.rbody.moment=pymunk.moment_for_circle(nm,0,ROCKET_R)

    def _check_phases(self, dt):
        pr=self.cfg["planet_r"]; d=math.hypot(*self.rbody.position)
        alt=d-pr

        if self.phase=="COUNTDOWN":
            self.cd_tmr-=dt
            if self.cd_tmr<=0: self.phase="ASCENT_SRB"; self.eng_on=True
        elif self.phase=="ASCENT_SRB":
            if self.fuel["srb"]<=.001:
                self.phase="SEP_SRB"; self.sep_tmr=1.2; self.eng_on=False
                self.parts.sep(*self.rbody.position,30); self._mk_srb_debris()
        elif self.phase=="SEP_SRB":
            self.sep_tmr-=dt
            if self.sep_tmr<=0: self.phase="ASCENT_CORE"; self.stg["srb"]=False; self.eng_on=True
        elif self.phase=="ASCENT_CORE":
            if self.fuel["core"]<=.001:
                self.phase="SEP_CORE"; self.sep_tmr=1.2; self.eng_on=False
                self.parts.sep(*self.rbody.position,30); self._mk_core_debris()
        elif self.phase=="SEP_CORE":
            self.sep_tmr-=dt
            if self.sep_tmr<=0: self.phase="CIRC_ICPS"; self.stg["core"]=False; self.eng_on=True
        elif self.phase=="CIRC_ICPS":
            if self._is_orbit(d):
                self.orbit_tmr+=dt
                if self.orbit_tmr>2.5: self.phase="ORBIT"; self.eng_on=False
            else: self.orbit_tmr=0
            if self.fuel["icps"]<=.001 and self.orbit_tmr<1:
                self._fail("Combustible ICPS agotado sin alcanzar orbita")

        # Crash
        if self.phase in ("ASCENT_SRB","ASCENT_CORE","CIRC_ICPS") and d<=pr+1:
            self._fail("El cohete impacto la superficie")

        # Transición de vista
        atm_h=pr*ATM_MULT*self.cfg["atm_density"]
        if alt>atm_h*.7 and self.view=="LATERAL": self.view="ORBITAL"

    def _is_orbit(self, d):
        pr=self.cfg["planet_r"]; target=pr*ORB_MULT
        atm_r=pr*ATM_MULT*self.cfg["atm_density"]
        if d<=atm_r: return False
        # Validar que estamos cerca de la órbita objetivo (máximo 3% de error de altitud)
        if abs(d-target) > target*0.03: return False
        
        rx,ry=self.rbody.position; nx,ny=rx/d,ry/d; tx,ty=-ny,nx
        vx,vy=self.rbody.velocity; vr=vx*nx+vy*ny; vt=vx*tx+vy*ty
        gs=self.cfg["gravity"]/9.81
        vo=math.sqrt(G_CONST*gs*P_MASS/d) if d>1 else 0
        # Criterio estricto de órbita circular centrada (tolerancia de error de velocidad 4%)
        return abs(vt-vo)<vo*.04 and abs(vr)<vo*.04

    def _mk_srb_debris(self):
        rx,ry=self.rbody.position; vx,vy=self.rbody.velocity
        d=math.hypot(rx,ry)
        if d<1: return
        nx,ny=rx/d,ry/d; tx,ty=-ny,nx
        for side in [-1,1]:
            m=SRB_STRUCT_N*.3
            b=pymunk.Body(m,pymunk.moment_for_circle(m,0,4))
            b.position=(rx+tx*side*12, ry+ty*side*12)
            b.velocity=(vx+tx*side*35-nx*8, vy+ty*side*35-ny*8)
            s=pymunk.Circle(b,4); s.sensor=True
            self.space.add(b,s); self.debris.append((b,s,"SRB"))

    def _mk_core_debris(self):
        rx,ry=self.rbody.position; vx,vy=self.rbody.velocity
        d=math.hypot(rx,ry)
        if d<1: return
        nx,ny=rx/d,ry/d
        m=CORE_STRUCT_N*.4
        b=pymunk.Body(m,pymunk.moment_for_circle(m,0,5))
        b.position=(rx-nx*12,ry-ny*12)
        b.velocity=(vx-nx*15,vy-ny*15)
        s=pymunk.Circle(b,5); s.sensor=True
        self.space.add(b,s); self.debris.append((b,s,"CORE"))
        nm=max(.05,self.rbody.mass-CORE_STRUCT_N)
        self.rbody.mass=nm; self.rbody.moment=pymunk.moment_for_circle(nm,0,ROCKET_R)

    def _fail(self, msg):
        self.phase="FAILED"; self.fail_msg=msg; self.eng_on=False
        self.parts.explosion(*self.rbody.position, 70)

    # ── Actualización principal ─────────────────────────────────────────
    def _update(self, wdt):
        if self.phase=="PREFLIGHT": return

        ts = self.cfg["time_scale"]
        sdt = wdt * ts      # Tiempo de simulación este frame

        if self.phase in ("ORBIT","FAILED"):
            if self.phase=="ORBIT":
                # Stepping estable aplicando gravedad en cada sub-paso para órbita infinita
                n=max(8,int(sdt/.003)+1); step=sdt/n
                for _ in range(n):
                    self._grav(self.rbody)
                    self.space.step(step)
                self.sim_t += sdt
                self.trail_t+=wdt
                if self.trail_t>.06:
                    self.trail_t=0; self.trail.append(tuple(self.rbody.position))
                    if len(self.trail)>600: self.trail.pop(0)
            self._update_cam()
            return

        self.sim_t += sdt

        if self.phase=="COUNTDOWN":
            self._check_phases(sdt); self._update_cam(); return

        self._burn_fuel(sdt)

        # Step Pymunk aplicando fuerzas en cada sub-paso para persistencia y estabilidad
        n=max(8,int(sdt/.003)+1); step=sdt/n
        for _ in range(n):
            self._grav(self.rbody); self._drag(self.rbody); self._wind(self.rbody)
            self._thrust()
            for b,s,t in self.debris:
                self._grav(b); self._drag(b)
            self.space.step(step)

        # Limpiar debris
        pr=self.cfg["planet_r"]
        self.debris=[(b,s,t) for b,s,t in self.debris if math.hypot(*b.position)>pr-3]

        # Partículas de propulsión
        if self.eng_on and self.phase not in ("SEP_SRB","SEP_CORE"):
            rx,ry=self.rbody.position
            vx,vy=self.rbody.velocity; sp=math.hypot(vx,vy)
            if sp>1:
                hx,hy=vx/sp,vy/sp
            else:
                d=math.hypot(rx,ry)
                hx,hy=(rx/d,ry/d) if d>1 else (0,-1)
            intensity = 2.0 if self.stg["srb"] else (1.0 if self.stg["core"] else .4)
            # Emitir desde la base trasera del cohete (12 px detrás del centro en dirección opuesta)
            self.parts.fire(rx-hx*12, ry-hy*12, -hx,-hy, int(3*intensity))
            if self.stg["srb"] and math.hypot(rx,ry)<self.cfg["planet_r"]*ATM_MULT:
                self.parts.smoke(rx-hx*15, ry-hy*15, -hx,-hy)

        # Trail
        self.trail_t+=wdt
        if self.trail_t>.1:
            self.trail_t=0; self.trail.append(tuple(self.rbody.position))
            if len(self.trail)>600: self.trail.pop(0)

        self._check_phases(sdt)
        self._update_cam()

        # Actualizar radio de planeta en Pymunk si cambió
        cur_r = self._planet_shape.radius
        new_r = self.cfg["planet_r"]
        if abs(cur_r - new_r) > 1:
            self._planet_shape.unsafe_set_radius(new_r)

    def _update_cam(self):
        rx,ry=self.rbody.position; pr=self.cfg["planet_r"]
        if self.view=="LATERAL":
            alt = math.hypot(rx,ry) - pr
            # Empieza con mucho zoom de despegue y se aleja suavemente hasta llegar a órbita
            z = max(1.2, 6.0 - alt * 0.015)
            off_y = 30/z
            self.cam.target(rx, ry+off_y, z)
        else:
            target_r=pr*ORB_MULT
            z=min(1.0, self.sh*.35/max(1,target_r))
            self.cam.target(0, 0, z)

    # ── Renderizado ─────────────────────────────────────────────────────
    def _draw_all(self):
        self.scr.fill(C_BG)
        if self.state=="MENU":   self._draw_menu()
        elif self.state=="SIM":  self._draw_sim()
        elif self.state=="END":  self._draw_end()
        self.mgr.draw_ui(self.scr)
        pygame.display.flip()

    def _draw_menu(self):
        sw,sh=self.sw,self.sh
        self.stars.draw(self.scr, self.cam, sw, sh)

        # Título
        t1=self.f_title.render("ARTEMIS II",True,C_CYAN)
        t2=self.f_med.render("SIMULADOR DE LANZAMIENTO  —  FASE 1",True,C_ORANGE)
        self.scr.blit(t1,(sw//2-t1.get_width()//2, 16))
        self.scr.blit(t2,(sw//2-t2.get_width()//2, 58))
        pygame.draw.line(self.scr,C_BORDER,(sw*.04,82),(sw*.96,82),1)

        h1=self.f_med.render("VEHICULO",True,C_CYAN)
        h2=self.f_med.render("ENTORNO",True,C_CYAN)
        self.scr.blit(h1,(int(sw*.04),90)); self.scr.blit(h2,(int(sw*.50),90))

        # Preview del cohete sobre el planeta (esquina inferior derecha)
        prev_x = int(sw*0.82); prev_planet_y = sh - 30
        prev_pr = min(80, int(self.cfg["planet_r"]*0.35))
        pygame.draw.circle(self.scr, C_EARTH, (prev_x, prev_planet_y), prev_pr)
        pygame.draw.circle(self.scr, C_EARTH_DK, (prev_x, prev_planet_y), prev_pr, 2)
        # Atmósfera
        atm_pr = int(prev_pr * ATM_MULT * self.cfg["atm_density"])
        atm_s = pygame.Surface((atm_pr*2+4, atm_pr*2+4), pygame.SRCALPHA)
        pygame.draw.circle(atm_s,(80,140,255,20),(atm_pr+2,atm_pr+2),atm_pr)
        self.scr.blit(atm_s,(prev_x-atm_pr-2, prev_planet_y-atm_pr-2))
        # Cohete sobre planeta
        draw_rocket(self.scr, prev_x, prev_planet_y-prev_pr-28, 0, .8,
                    dict(srb=True,core=True,icps=True,orion=True), False)

        # Info
        info=f"SLS Block 1 | Masa: {ARTEMIS['liftoff_mass_kg']:,} kg | Empuje: {ARTEMIS['total_thrust_N']/1e6:.1f} MN | Max tripulantes: {MAX_CREW}"
        self.scr.blit(self.f_sm.render(info,True,C_GRAY),(sw//2-len(info)*3.5, sh-40))

    def _draw_sim(self):
        sw,sh=self.sw,self.sh; sim_w=sw-PANEL_W
        pr=self.cfg["planet_r"]; rx,ry=self.rbody.position
        d=math.hypot(rx,ry); alt=max(0,d-pr)
        atm_h=pr*ATM_MULT*self.cfg["atm_density"]

        # ── Área de simulación (clipped) ──
        self.scr.set_clip(pygame.Rect(0,0,sim_w,sh))

        # Fondo (gradiente cielo → espacio)
        if alt<atm_h:
            f=alt/atm_h
            bg=(int(C_SKY[0]*(1-f)), int(C_SKY[1]*(1-f)), int(C_SKY[2]*(1-f)))
        else: bg=C_BG
        self.scr.fill(bg, (0,0,sim_w,sh))

        if alt>atm_h*.25: self.stars.draw(self.scr, self.cam, sim_w, sh)

        # Planeta
        psx,psy=self.cam.w2s(0,0,sim_w,sh); prpx=int(pr*self.cam.zoom)
        # Atmósfera
        atm_px=int(atm_h*self.cam.zoom)
        if atm_px>3:
            asf=pygame.Surface((atm_px*2+4,atm_px*2+4),pygame.SRCALPHA)
            pygame.draw.circle(asf,(80,140,255,22),(atm_px+2,atm_px+2),atm_px)
            self.scr.blit(asf,(psx-atm_px-2,psy-atm_px-2))
        if prpx>1:
            pygame.draw.circle(self.scr, C_EARTH, (psx,psy), prpx)
            if prpx>8:
                pygame.draw.circle(self.scr, C_EARTH_HI, (psx-prpx//5,psy-prpx//5), int(prpx*.65))
                pygame.draw.circle(self.scr, C_EARTH_DK, (psx,psy), prpx, max(1,prpx//30))

        # Órbita objetivo (siempre visible para depuración y referencia gráfica)
        orpx=int(pr*ORB_MULT*self.cam.zoom)
        if orpx>8:
            pygame.draw.circle(self.scr, (0, 150, 100), (psx, psy), orpx, 1)

        # Trail
        if len(self.trail)>1:
            for i in range(1,len(self.trail)):
                p1=self.cam.w2s(*self.trail[i-1],sim_w,sh)
                p2=self.cam.w2s(*self.trail[i],sim_w,sh)
                f=i/len(self.trail)
                pygame.draw.line(self.scr,(0,int(160*f),int(255*f)),p1,p2,1)

        # Debris
        for b,s,t in self.debris:
            ds=self.cam.w2s(b.position.x,b.position.y,sim_w,sh)
            dsz=max(2,int(3*self.cam.zoom))
            pygame.draw.circle(self.scr,(170,170,175) if t=="SRB" else (100,105,115),ds,dsz)

        # Cohete
        rsx,rsy=self.cam.w2s(rx,ry,sim_w,sh)
        vx,vy=self.rbody.velocity; sp=math.hypot(vx,vy)
        if self.phase == "COUNTDOWN" or sp <= 1:
            # En plataforma, apunta radialmente
            d=math.hypot(rx,ry)
            hx,hy=(rx/d,ry/d) if d>1 else (0,-1)
        else:
            # Durante el vuelo, el cohete apunta en la dirección de su velocidad
            hx,hy=vx/sp,vy/sp
        ra=math.atan2(hy,hx)+math.pi/2

        if self.cam.zoom > 0.8:
            draw_rocket(self.scr,rsx,rsy,ra,self.cam.zoom,self.stg,
                        self.eng_on and self.phase not in ("SEP_SRB","SEP_CORE"))
        else:
            draw_rocket_small(self.scr,rsx,rsy,ra,self.cam.zoom)

        # Partículas
        self.parts.draw(self.scr, self.cam, sim_w, sh)

        # Countdown
        if self.phase=="COUNTDOWN":
            cv=max(0,int(math.ceil(self.cd_tmr)))
            txt = str(cv) if cv>0 else "LANZAMIENTO!"
            col = C_ORANGE if cv>0 else C_GREEN
            cs=self.f_cd.render(txt,True,col)
            self.scr.blit(cs,(sim_w//2-cs.get_width()//2, sh//2-cs.get_height()//2))

        self.scr.set_clip(None)

        # ── HUD ──
        phase_names={"COUNTDOWN":"CUENTA REGRESIVA","ASCENT_SRB":"ASCENSO  SRBs+Core",
            "SEP_SRB":"SEPARACION SRBs","ASCENT_CORE":"ASCENSO  Core Stage",
            "SEP_CORE":"SEPARACION Core","CIRC_ICPS":"CIRCULARIZACION  ICPS",
            "ORBIT":"ORBITA ESTABLE","FAILED":"MISION FALLIDA"}
        pn=phase_names.get(self.phase,self.phase)
        pc=C_GREEN if self.phase=="ORBIT" else (C_RED if self.phase=="FAILED" else C_CYAN)
        self.scr.blit(self.f_med.render(f"FASE: {pn}",True,pc),(8,8))
        ms=self.sim_t*MISSION_TIME_MULT
        self.scr.blit(self.f_med.render(f"T+ {int(ms//60):02d}:{int(ms%60):02d}",True,C_WHITE),(8,30))
        self.scr.blit(self.f_sm.render(f"x{self.cfg['time_scale']:.1f}",True,C_ORANGE),(sim_w-50,8))

        # ── Panel telemetría ──
        self._draw_panel()

    def _draw_panel(self):
        sw,sh=self.sw,self.sh; px=sw-PANEL_W
        pygame.draw.rect(self.scr,C_PANEL,(px,0,PANEL_W,sh))
        pygame.draw.line(self.scr,C_BORDER,(px,0),(px,sh),2)

        t=self.f_med.render("TELEMETRIA",True,C_CYAN)
        self.scr.blit(t,(px+PANEL_W//2-t.get_width()//2,8))
        pygame.draw.line(self.scr,C_BORDER,(px+8,30),(px+PANEL_W-8,30),1)

        rx,ry=self.rbody.position; vx,vy=self.rbody.velocity
        d=math.hypot(rx,ry); pr=self.cfg["planet_r"]
        # Descontar el radio del cohete y la plataforma de lanzamiento para que inicie en 0 km
        alt=max(0,d-pr-ROCKET_R-3)
        sp=math.hypot(vx,vy)

        gs=self.cfg["gravity"]/9.81
        gf=G_CONST*gs*P_MASS/(d*d) if d>1 else 0
        twr=0
        if self.eng_on and self.rbody.mass>0:
            th=0
            if self.phase=="ASCENT_SRB": th=self.thrust_total
            elif self.phase=="ASCENT_CORE": th=self.thrust_core
            elif self.phase=="CIRC_ICPS": th=self.thrust_icps
            th*=self.cfg["throttle"]/100.
            w=self.rbody.mass*gf; twr=th/w if w>0 else 0

        # Formato compacto de telemetría
        y=32
        for lab,val in [("Altitud",f"{alt*50:.0f} km"),("Velocidad",f"{sp*50:.0f} m/s"),
                        ("TWR",f"{twr:.2f}"),("Masa",f"{self.rbody.mass:.3f} u"),
                        ("Gravedad",f"{self.cfg['gravity']:.1f} m/s²")]:
            y+=16
            self.scr.blit(self.f_sm.render(lab,True,C_GRAY),(px+10,y))
            vs=self.f_sm.render(val,True,C_WHITE)
            self.scr.blit(vs,(px+PANEL_W-vs.get_width()-10,y))

        # Sección de Combustible compacta
        y+=22
        pygame.draw.line(self.scr,C_BORDER,(px+8,y),(px+PANEL_W-8,y),1)
        y+=4
        self.scr.blit(self.f_sm.render("COMBUSTIBLE",True,C_CYAN),(px+10,y))
        y+=16
        bw=PANEL_W-36; bh=10
        for k,nm in [("srb","SRB"),("core","Core"),("icps","ICPS")]:
            fr=max(0,min(1,self.fuel[k]/self.fuelmax[k])) if self.fuelmax[k]>0 else 0
            bc=(int(255*(1-fr)*2),255,50) if fr>.5 else (255,int(255*fr*2),50)
            self.scr.blit(self.f_sm.render(f"{nm}:",True,C_GRAY),(px+10,y))
            ps=self.f_sm.render(f"{fr*100:.0f}%",True,C_WHITE)
            self.scr.blit(ps,(px+PANEL_W-ps.get_width()-10,y))
            y+=14
            pygame.draw.rect(self.scr,(22,28,42),(px+14,y,bw,bh),border_radius=2)
            if fr>.005: pygame.draw.rect(self.scr,bc,(px+14,y,int(bw*fr),bh),border_radius=2)
            pygame.draw.rect(self.scr,C_DGRAY,(px+14,y,bw,bh),1,border_radius=2)
            y+=bh+4

        # Sección de Fases de Vuelo compactada a 2 columnas
        y+=6
        pygame.draw.line(self.scr,C_BORDER,(px+8,y),(px+PANEL_W-8,y),1)
        y+=4
        self.scr.blit(self.f_sm.render("FASES DE VUELO",True,C_CYAN),(px+10,y))
        y+=16
        plist=[("SRB+Core","ASCENT_SRB"),("Sep SRB","SEP_SRB"),("Core","ASCENT_CORE"),
               ("Sep Core","SEP_CORE"),("ICPS","CIRC_ICPS"),("Orbita","ORBIT")]
        pidx=-1
        for i,(n,pid) in enumerate(plist):
            if self.phase==pid: pidx=i

        col_w = PANEL_W // 2 - 10
        for i,(nm,pid) in enumerate(plist):
            col = i // 3
            row = i % 3
            dx_ = px + 15 + col * col_w
            dy_ = y + row * 16

            if i<pidx or self.phase=="ORBIT" and pid=="ORBIT":
                dc,tc=C_GREEN,C_GREEN
            elif i==pidx: dc,tc=C_ORANGE,C_ORANGE
            else: dc,tc=C_DGRAY,C_DGRAY
            pygame.draw.circle(self.scr,dc,(dx_,dy_+5),3)
            self.scr.blit(self.f_sm.render(nm,True,tc),(dx_+10,dy_))

        y += 3 * 16 + 6
        pygame.draw.line(self.scr,C_BORDER,(px+8,y),(px+PANEL_W-8,y),1)
        y+=4
        self.scr.blit(self.f_sm.render("ENTORNO (en vivo)",True,C_CYAN),(px+10,y))

    def _draw_end(self):
        sw,sh=self.sw,self.sh
        if self.space: self._draw_sim()
        ov=pygame.Surface((sw,sh),pygame.SRCALPHA); ov.fill((0,0,0,150)); self.scr.blit(ov,(0,0))

        if self.phase=="ORBIT":
            t=self.f_title.render("ORBITA ALCANZADA",True,C_GREEN)
        else:
            t=self.f_title.render("MISION FALLIDA",True,C_RED)
        self.scr.blit(t,(sw//2-t.get_width()//2, sh//3))

        if self.phase=="FAILED" and self.fail_msg:
            r=self.f_med.render(self.fail_msg,True,C_ORANGE)
            self.scr.blit(r,(sw//2-r.get_width()//2, sh//3+48))

        ms=self.sim_t*MISSION_TIME_MULT
        lines=[f"Tiempo mision: T+{int(ms//60):02d}:{int(ms%60):02d}"]
        for k,n in [("srb","SRB"),("core","Core"),("icps","ICPS")]:
            f=max(0,self.fuel[k]/self.fuelmax[k]*100) if self.fuelmax[k]>0 else 0
            lines.append(f"Combustible {n}: {f:.0f}%")
        y=sh//3+85
        for l in lines:
            s=self.f_sm.render(l,True,C_WHITE); self.scr.blit(s,(sw//2-s.get_width()//2,y)); y+=18

    # ── Game Loop ───────────────────────────────────────────────────────
    def run(self):
        end_delay = -1.

        while self.running:
            wdt=min(self.clock.tick(FPS)/1000., .05)

            for ev in pygame.event.get():
                if ev.type==pygame.QUIT: self.running=False; break
                if ev.type==pygame.VIDEORESIZE:
                    self.sw=max(960,ev.w); self.sh=max(560,ev.h)
                    self.scr=pygame.display.set_mode((self.sw,self.sh),pygame.RESIZABLE)
                    self.mgr.set_window_resolution((self.sw,self.sh))
                    if self.state=="MENU": self._build_menu()
                    elif self.state=="SIM": self._build_sim()
                    elif self.state=="END": self._build_end()

                self.mgr.process_events(ev)

                if ev.type==pygame_gui.UI_BUTTON_PRESSED:
                    if self.buttons.get("start") and ev.ui_element==self.buttons["start"]:
                        self._read_sliders(); self._init_physics()
                        self.phase="COUNTDOWN"; self.cd_tmr=5.
                        self.state="SIM"; self._build_sim(); end_delay=-1.
                    elif self.buttons.get("restart") and ev.ui_element==self.buttons["restart"]:
                        self.state="MENU"; self.phase="PREFLIGHT"; self._build_menu(); end_delay=-1.
                    elif self.buttons.get("quit") and ev.ui_element==self.buttons["quit"]:
                        self.running=False

                if ev.type==pygame_gui.UI_HORIZONTAL_SLIDER_MOVED:
                    self._read_sliders()

            if not self.running: break

            self.mgr.update(wdt); self.stars.update(wdt)
            ts = self.cfg["time_scale"] if self.state=="SIM" else 1.
            self.parts.update(wdt*ts); self.cam.update(wdt)

            if self.state=="SIM":
                self._update(wdt)
                if self.phase in ("ORBIT","FAILED"):
                    if end_delay<0: end_delay=2.5
                    end_delay-=wdt
                    if end_delay<=0:
                        self.state="END"; self._build_end(); end_delay=-1.
            elif self.state=="END" and self.phase=="ORBIT" and self.space:
                self._update(wdt)

            self._draw_all()

        pygame.quit(); sys.exit()

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================
if __name__=="__main__":
    Sim().run()
