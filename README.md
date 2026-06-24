# Simulador de Lanzamiento Artemis II — SLS Block 1

Este simulador está programado en Python utilizando **Pygame** para la interfaz visual y el renderizado, **Pymunk** como motor de física en 2D, y **pygame_gui** para los controles interactivos. 

El objetivo del proyecto es simular el lanzamiento del cohete **Space Launch System (SLS)** de la misión Artemis II, pasando por la separación de etapas, el ascenso atmosférico y la circularización en una órbita terrestre estable.

---

## Estructura y Explicación del Código Paso a Paso

El archivo principal `artemis_ii_simulator.py` está estructurado en secciones modulares. A continuación se describe el funcionamiento de cada una de ellas:

### 1. Sección 1: Constantes y Datos Técnicos
En esta sección se definen:
*   **Colores del Tema NASA Oscuro:** Colores RGB para la interfaz gráfica (HUD), el planeta, la atmósfera y el espacio.
*   **Parámetros Físicos por Defecto:** 
    *   `G_CONST` (12000): Constante de gravitación universal adaptada a la escala de la simulación.
    *   `P_MASS` (100): Masa del planeta Tierra.
    *   `DEF_PR` (200 px): Radio de la Tierra en píxeles.
    *   Multiplicadores de atmósfera (`ATM_MULT = 1.8`) y órbita objetivo (`ORB_MULT = 2.5`).
*   **Especificaciones del Artemis II (SLS):** Pesos reales (propulsores, combustible de cada etapa, cápsula Orión) y empujes (SRB, Core Stage, ICPS) según la documentación oficial de la NASA, normalizados a la escala física del motor Pymunk.

---

### 2. Sección 3: Sistema de Partículas (`Particles` y `Particle`)
Se encarga de los efectos visuales del simulador (fuego de motores, humo y explosiones):
*   **Clase `Particle`:** Representa una partícula individual con posición (`x`, `y`), velocidad (`vx`, `vy`), tiempo de vida (`life`), color y tamaño. Al actualizarse, disminuye su tiempo de vida y se desplaza según su velocidad.
*   **Clase `Particles`:** Contiene una lista de partículas activas y provee métodos específicos para generarlas en grupo:
    *   `fire(x, y, dx, dy, count)`: Emite partículas de fuego naranjas/amarillas detrás de las toberas del cohete.
    *   `smoke(x, y, dx, dy)`: Crea partículas grises de humo (con dispersión) durante la fase atmosférica.
    *   `explosion(x, y, count)`: Genera una explosión expansiva de partículas multicolores si el cohete se estrella.
    *   `sep(x, y)`: Pequeña explosión de partículas de gas para simular la pirotecnia de separación de etapas.

---

### 3. Sección 4: Sistema de Cámara (`Camera`)
La clase `Camera` maneja el desplazamiento y el zoom dinámico de la pantalla:
*   Realiza una transición suave (`snap` y `target`) entre las coordenadas del cohete y la posición de la cámara usando interpolación lineal (Lerp).
*   **Dos vistas dinámicas:**
    1.  **VISTA LATERAL (Seguimiento cercano):** Comienza con un zoom muy cercano (`6.0`) para ver el despegue detallado del cohete y disminuye paulatinamente a medida que el cohete gana altitud, permitiendo observar la transición atmosférica.
    2.  **VISTA ORBITAL (Panorámica global):** Se activa al salir de la atmósfera inferior. Aleja la cámara (`zoom <= 1.0`) y la centra en el planeta Tierra para poder visualizar la órbita completa y el cohete dando vueltas alrededor del planeta.

---

### 4. Sección 5: Dibujo Programático del Cohete
Para evitar depender de imágenes externas que limitaran la escala y rotación, el cohete se dibuja usando polígonos vectoriales rotados geométricamente:
*   **Función `_rot(pts, angle, cx, cy)`:** Rota una lista de puntos 2D alrededor de un centro `(cx, cy)` aplicando matrices de rotación trigonométrica (`cos` y `sin`).
*   **Función `draw_rocket`:** Renderiza el cohete articulado en sus 4 componentes clave:
    1.  **SRBs (Solid Rocket Boosters):** Los dos aceleradores laterales blancos con toberas oscuras.
    2.  **Core Stage:** La etapa central naranja (tanque de hidrógeno/oxígeno líquido) con sus 4 motores RS-25 en la base.
    3.  **ICPS (Interim Cryogenic Propulsion Stage):** La etapa de empuje orbital superior.
    4.  **Orion:** La cápsula de tripulación en la punta del cohete.
    
    *Nota: Si una etapa se separa, su flag de estado en el diccionario `stg` cambia a `False` y deja de dibujarse en el cohete principal.*
*   **Lógica de Flamas:** Si los motores están encendidos (`flames=True`), dibuja polígonos oscilantes de color amarillo y rojo simulando la pluma de escape.
*   **Función `draw_rocket_small`:** Si la cámara se aleja demasiado (zoom orbital muy bajo), dibuja el cohete como un pequeño triángulo simplificado rodeado de un halo cian para que no se pierda de vista.

---

### 5. Sección 6: Simulador Principal (Clase `Sim`)

Maneja el bucle de juego, la física de Pymunk y la lógica de vuelo.

#### A. Inicialización Física (`_init_physics`)
Crea el espacio físico de Pymunk y define:
1.  **La Tierra:** Un cuerpo estático (`pymunk.Body(body_type=pymunk.Body.STATIC)`) ubicado en `(0, 0)` con una forma circular (`pymunk.Circle`) del radio configurado.
2.  **El Cohete:** Un cuerpo dinámico (`pymunk.Body`) con una masa inicial correspondiente a la suma de todas las etapas activas. Comienza en posición vertical sobre la superficie del planeta.

#### B. Modelo de Fuerzas Físicas
Durante el bucle de actualización, se aplican tres fuerzas principales en cada fotograma sobre el cohete:
1.  **Gravedad Real (`_grav`):**
    $$F_g = \frac{G \cdot M_{planeta} \cdot m_{cohete}}{r^2}$$
    Se aplica en dirección hacia el centro del planeta.
2.  **Resistencia Aerodinámica (`_drag`):**
    $$F_d = \frac{1}{2} \cdot \rho \cdot v^2 \cdot C_d \cdot A$$
    La densidad atmosférica $\rho$ decae exponencialmente con la altitud:
    $$\rho = \rho_{base} \cdot e^{-\frac{\text{altitud}}{\text{escala de altura}}}$$
    Se opone a la dirección del vector de velocidad del cohete.
3.  **Viento (`_wind`):** Aplica una fuerza lateral constante según el slider de viento configurado.

#### C. Autopiloto Inteligente (`_thrust`)
La función de empuje controla la magnitud y dirección de la fuerza aplicada según la fase de vuelo:

*   **Fase `ASCENT_SRB` (Despegue y Ascenso SRB):**
    El cohete despega y en cada fotograma calcula pequeñas desviaciones laterales para empezar a trazar la parábola de Coriolis a medida que se aleja del planeta.
    La velocidad tangencial objetivo crece de forma gradual según la altitud:
    $$v_{t\_target} = 14.0 \cdot \min\left(1.0, \frac{\text{altitud}}{300}\right)$$
    Un controlador proporcional ajusta el vector de empuje lateral para cumplir con esta velocidad.

*   **Fase `ASCENT_CORE` (Ascenso Core Stage):**
    Los SRB se han separado. Para evitar que el cohete sobrepase la órbita, se implementa un **Controlador PD (Proporcional-Derivativo)** en el eje vertical (radial):
    $$F_r = (K_p \cdot e_d - K_d \cdot v_r) \cdot m_{cohete}$$
    Donde $e_d$ es el error de distancia a la órbita y $v_r$ es la velocidad radial. Al mismo tiempo, la velocidad tangencial objetivo sigue aumentando suavemente para inclinar progresivamente el cohete en preparación para la órbita.

*   **Fase `CIRC_ICPS` (Circularización en Órbita):**
    La etapa central Core se separa e inicia la etapa ICPS. El piloto automático realiza un control estricto:
    1.  Usa el controlador PD radial para estabilizar la altitud exactamente sobre el diámetro de la órbita objetivo, amortiguando cualquier oscilación.
    2.  Acelera tangencialmente hasta que el cohete alcanza la **velocidad orbital teórica**:
        $$v_{orbital} = \sqrt{\frac{G \cdot M_{planeta}}{r}}$$
        Una vez alcanzada la velocidad (con menos del 4% de error radial y tangencial durante 2.5 segundos), el piloto automático apaga los motores y el cohete entra en órbita.

#### D. Consumo de Combustible (`_burn_fuel`)
En cada fotograma, el cohete consume combustible de las etapas activas en función de la aceleración (`throttle`). A medida que el combustible se agota:
*   Se reduce dinámicamente la masa (`mass`) del cuerpo físico de Pymunk.
*   Se recalcula el momento de inercia (`moment`), permitiendo que el cohete sea más ligero y acelere más rápido a medida que se vacían los tanques.

#### E. Máquina de Estados de Vuelo (`_check_phases`)
Controla la secuencia lógica del lanzamiento:
1.  `PREFLIGHT`: Menú de configuración inicial.
2.  `COUNTDOWN`: Cuenta regresiva de 5 segundos.
3.  `ASCENT_SRB`: Vuelo con propulsores sólidos (SRB) y etapa Core activos.
4.  `SEP_SRB`: Transición de 1.2 segundos donde se expulsan los SRB (creando escombros físicos que caen al planeta).
5.  `ASCENT_CORE`: Vuelo exclusivo con la etapa central Core activa.
6.  `SEP_CORE`: Transición de 1.2 segundos donde se expulsa el Core Stage y queda solo la etapa orbital ICPS con la cápsula Orión.
7.  `CIRC_ICPS`: Encendido del ICPS para circularizar la órbita.
8.  `ORBIT`: Motores apagados. El cohete orbita de forma infinita alrededor del planeta equilibrando la fuerza centrífuga y la gravedad.

---

## Requisitos de Ejecución

Para ejecutar el simulador necesitas tener instalado:
*   Python 3.10 o superior
*   Pygame CE (`pip install pygame-ce`)
*   Pymunk (`pip install pymunk`)
*   Pygame GUI (`pip install pygame_gui`)

### Comando para correr la simulación:
```powershell
python artemis_ii_simulator.py
```
