
import tkinter as tk
from tkinter import messagebox
from tkcalendar import Calendar
from datetime import datetime
import sqlite3
from datetime import timedelta
import os
import sys

#---- COLORES ----

COLORES = [
    "#FF6B6B",  # rojo
    "#4D96FF",  # azul
    "#6BCB77",  # verde
    "#FFD93D",  # amarillo
    "#845EC2",  # morado
]

eventos_ids = []
proyecto_seleccionado_id =None
proyectos_abiertos = set()

def obtener_color_automatico():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM eventos")
    cantidad = cursor.fetchone()[0]
    conn.close()
    return COLORES[cantidad % len(COLORES)]

# -------------------- BASE DE DATOS --------------------

def ruta_base():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else: 
        return os.path.dirname(os.path.abspath(__file__))
RUTA_DB = os.path.join(ruta_base(), "eventos.db")

def conectar_db():
    return sqlite3.connect(RUTA_DB)



def inicializar_db():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS eventos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_inicio TEXT NOT NULL,
        fecha_fin TEXT NOT NULL,
        hora TEXT NOT NULL,
        texto TEXT NOT NULL,
        color TEXT NOT NULL,
        prioridad TEXT NOT NULL DEFAULT 'Media',
        tipo TEXT NOT NULL DEFAULT 'Tarea',
        proyecto_id INTEGER
    )
    """)

    conn.commit()
    conn.close()

inicializar_db()
#__________________________________________________

def asegurar_columna_tipo():
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE eventos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'Tarea'"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()

asegurar_columna_tipo()

def asegurar_columnas_proyectos():
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(eventos)")
    columnas = [c[1] for c in cursor.fetchall()]

    if "tipo" not in columnas:
        cursor.execute(
            "ALTER TABLE eventos ADD COLUMN tipo TEXT NOT NULL DEFAULT 'Tarea'"
        )

    if "proyecto_id" not in columnas:
        cursor.execute(
            "ALTER TABLE eventos ADD COLUMN proyecto_id INTEGER"
        )

    conn.commit()
    conn.close()

asegurar_columnas_proyectos()

def normalizar_tipos_antiguos():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE eventos
        SET tipo = 'Tarea'
        WHERE tipo IS NULL OR tipo = ''
    """)
    conn.commit()
    conn.close()
normalizar_tipos_antiguos()

def asegurar_columna_proyecto():
    conn = conectar_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "ALTER TABLE eventos ADD COLUMN proyecto_id INTEGER"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    conn.close()
asegurar_columna_proyecto()
#_________________________________________________
# -------------------- FUNCIONES BD --------------------

def menu_contextual(event, evento):
    evento_id, hora, texto, color, prioridad, tipo, proyecto_id = evento

    menu = tk.Menu(root, tearoff=0)

    menu.add_command(
        label="✏️ Editar",
        command=lambda: abrir_popup_agregar(evento_id)
    )

    menu.add_command(
        label="🗑 Eliminar",
        command=lambda: eliminar_evento(evento_id, texto)
    )

    menu.tk_popup(event.x_root, event.y_root)


def toggle_proyecto(proyecto_id):
    global proyecto_seleccionado_id

    proyecto_seleccionado_id = proyecto_id

    if proyecto_id in proyectos_abiertos:
        proyectos_abiertos.remove(proyecto_id)
    else:
        proyectos_abiertos.add(proyecto_id)

    mostrar_eventos()

def mover_mes(delta):
    fecha = cal_izq.selection_get()

    # calcular nuevo mes
    mes = fecha.month + delta
    anio = fecha.year

    if mes < 1:
        mes = 12
        anio -= 1
    elif mes > 12:
        mes = 1
        anio += 1

    nueva_fecha = fecha.replace(year=anio, month=mes, day=1)

    cal_izq.selection_set(nueva_fecha)
    cal_izq.see(nueva_fecha)

    sincronizar_calendarios()
    mostrar_eventos()
    marcar_dias_con_eventos()


def marcar_dias_con_eventos():
    for c in (cal_izq, cal_der):
        c.calevent_remove("all")

    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT fecha_inicio, fecha_fin, color
        FROM eventos
        WHERE tipo = 'Proyecto'
    """)

    dias_colores = {}

    for inicio, fin, color in cursor.fetchall():
        if not inicio or not fin:
            continue

        d1 = datetime.fromisoformat(inicio).date()
        d2 = datetime.fromisoformat(fin).date()

        while d1 <= d2:
            dias_colores.setdefault(d1, []).append(color)
            d1 += timedelta(days=1)

    conn.close()

    # dibujar hasta 3 marcas por día
    for dia, colores in dias_colores.items():
        for i, color in enumerate(colores[:3]):
            tag = f"mark_{dia}_{i}"

            for cal in (cal_izq, cal_der):
                cal.calevent_create(dia, "", tag)
                cal.tag_config(
                    tag,
                    background=color,
                    foreground="black"
                )


def agregar_proyecto_bd(fecha_inicio, fecha_fin, texto, color, prioridad):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO eventos
        (fecha_inicio, fecha_fin, hora, texto, color, prioridad, tipo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (fecha_inicio, fecha_fin, "00:00", texto, color, prioridad, "Proyecto"))
    conn.commit()
    conn.close()


def agregar_tarea_bd(fecha_inicio,fecha_fin, hora, texto, color, prioridad, proyecto_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO eventos
        (fecha_inicio, fecha_fin, hora, texto, color, prioridad, tipo, proyecto_id)
        VALUES (?, ?, ?, ?, ?, ?, 'Tarea', ?)
    """, (fecha_inicio, fecha_fin, hora, texto, color, prioridad, proyecto_id))
    conn.commit()
    conn.close()


def eliminar_evento_bd(evento_id):
    conn = conectar_db()
    cursor = conn.cursor()

    # eliminar tareas asociadas
    cursor.execute(
        "DELETE FROM eventos WHERE proyecto_id = ?",
        (evento_id,)
    )

    # eliminar el proyecto o tarea
    cursor.execute(
        "DELETE FROM eventos WHERE id = ?",
        (evento_id,)
    )

    conn.commit()
    conn.close()

def editar_evento_db(evento_id, nueva_hora, nuevo_texto):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE eventos SET hora = ?, texto = ? WHERE id = ?",
        (nueva_hora, nuevo_texto, evento_id)
    )
    conn.commit()
    conn.close()

def editar_proyecto_bd(evento_id, inicio, fin, texto, prioridad):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE eventos
        SET fecha_inicio = ?, fecha_fin = ?, texto = ?, prioridad = ?
        WHERE id = ?
    """, (inicio, fin, texto, prioridad, evento_id))
    conn.commit()
    conn.close()


def editar_tarea_bd(evento_id, fecha_inicio, fecha_fin, hora, texto, prioridad, proyecto_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE eventos
        SET fecha_inicio = ?, fecha_fin = ?, hora = ?, texto = ?, prioridad = ?, proyecto_id = ?
        WHERE id = ?
    """, (fecha_inicio, fecha_fin, hora, texto, prioridad, proyecto_id, evento_id))
    conn.commit()
    conn.close()


def obtener_tareas_por_fecha(fecha):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, hora, texto, color, prioridad
        FROM eventos
        WHERE tipo = 'Tarea'
          AND fecha_inicio <= ?
          AND fecha_fin >= ?
        ORDER BY
          CASE prioridad
            WHEN 'Alta' THEN 1
            WHEN 'Media' THEN 2
            WHEN 'Baja' THEN 3
          END,
          hora
    """, (fecha, fecha))
    tareas = cursor.fetchall()
    conn.close()
    return tareas


def obtener_eventos_por_fecha(fecha):
    conn = conectar_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, hora, texto, color, prioridad, tipo, proyecto_id
        FROM eventos
        WHERE fecha_inicio <= ? AND fecha_fin >= ?
        ORDER BY
          CASE tipo
            WHEN 'Proyecto' THEN 0
            ELSE 1
          END,
          proyecto_id,
          CASE prioridad
            WHEN 'Alta' THEN 1
            WHEN 'Media' THEN 2
            WHEN 'Baja' THEN 3
          END,
          hora
    """, (fecha, fecha))

    eventos = cursor.fetchall()
    conn.close()
    return eventos

def obtener_evento_por_id(evento_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, fecha_inicio, fecha_fin, hora, texto, color, prioridad, tipo, proyecto_id
        FROM eventos
        WHERE id = ?
    """, (evento_id,))
    return cursor.fetchone()


def obtener_color_proyecto(proyecto_id):
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT color FROM eventos WHERE id = ?",
        (proyecto_id,)
    )
    color = cursor.fetchone()[0]
    conn.close()
    return color

# -------------------- FUNCIONES UI --------------------

def limpiar_eventos():
    for widget in contenedor_eventos.winfo_children():
        widget.destroy()

def mostrar_eventos():
    for widget in contenedor_eventos.winfo_children():
        widget.destroy()

    fecha = cal_izq.selection_get().isoformat()
    eventos = obtener_eventos_por_fecha(fecha)

    proyectos = {}
    tareas = []

    # separar proyectos y tareas
    for e in eventos:
        evento_id, hora, texto, color, prioridad, tipo, proyecto_id = e
        if tipo == "Proyecto":
            proyectos[evento_id] = e
        else:
            tareas.append(e)

    # mostrar solo proyectos
    for proyecto_id, proyecto in proyectos.items():
        evento_id, hora, texto, color, prioridad, _, _ = proyecto

        prefijo = "🔴" if prioridad == "Alta" else "🟡" if prioridad == "Media" else "🟢"

        icono = "▼" if proyecto_id in proyectos_abiertos else "▶"

        lbl = tk.Label(
            contenedor_eventos,
            text=f"📁 {prefijo} {hora} - {texto}",
            bg=color,
            fg="black",
            padx=6,
            pady=4,
            font=("Arial", 10, "bold")
        )
        lbl.pack(fill=tk.X, pady=2)

        # CLICK IZQUIERDO → mostrar/ocultar tareas
        lbl.bind(
            "<Button-1>",
            lambda e, pid=proyecto_id: toggle_proyecto(pid)
        )

        # CLICK DERECHO → menú
        lbl.bind(
            "<Button-3>",
            lambda e, ev=proyecto: menu_contextual(e, ev)
        )

        # mostrar tareas SOLO si el proyecto está abierto
        if proyecto_id in proyectos_abiertos:
            for t in tareas:
                tid, hora, texto, color, prioridad, _, pid = t
                if pid == proyecto_id:
                    pref = "🔴" if prioridad == "Alta" else "🟡" if prioridad == "Media" else "🟢"

                    lbl_t = tk.Label(
                        contenedor_eventos,
                        text=f"    📝 {pref} {hora} - {texto}",
                        bg=color,
                        fg="black",
                        padx=12,
                        pady=2
                    )
                    lbl_t.pack(fill=tk.X, padx=15)

                    lbl_t.bind(
                        "<Button-3>",
                        lambda e, ev=t: menu_contextual(e, ev)
                    )



def hora_valida(hora):
    try:
        datetime.strptime(hora, "%H:%M")
        return True
    except ValueError:
        return False


def eliminar_evento(evento_id, texto):
    """
    Elimina un evento dado su ID.
    `texto` se pasa solo para mostrar en la confirmación.
    """
    if messagebox.askyesno("Confirmar", f"¿Eliminar el evento?\n\n{texto}"):
        eliminar_evento_bd(evento_id)
        mostrar_eventos()
        marcar_dias_con_eventos()


def mostrar_gantt():
    win = tk.Toplevel(root)
    win.title("Vista Gantt - Proyectos")
    win.geometry("900x500")

    frame = tk.Frame(win)
    frame.pack(fill="both", expand=True)

    canvas = tk.Canvas(frame, bg="white")
    canvas.pack(side="left", fill="both", expand=True)

    scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollbar.pack(side="right", fill="y")

    canvas.configure(yscrollcommand=scrollbar.set)

    inner = tk.Frame(canvas, bg="white")
    canvas.create_window((0, 0), window=inner, anchor="nw")

    # ---------------- DATOS ----------------
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT texto, fecha_inicio, fecha_fin, color
        FROM eventos
        WHERE tipo = 'Proyecto'
        ORDER BY fecha_inicio
    """)
    proyectos = cursor.fetchall()
    conn.close()

    if not proyectos:
        tk.Label(inner, text="No hay proyectos", bg="white").pack(pady=20)
        return

    fechas_inicio = [datetime.fromisoformat(p[1]) for p in proyectos]
    fechas_fin = [datetime.fromisoformat(p[2]) for p in proyectos]

    inicio_global = min(fechas_inicio)
    fin_global = max(fechas_fin)

    PIXELS_POR_DIA = 25
    ALTO_BARRA = 25
    ESPACIO = 15

    # ---------------- DIBUJO ----------------
    for i, (nombre, inicio, fin, color) in enumerate(proyectos):
        d1 = datetime.fromisoformat(inicio)
        d2 = datetime.fromisoformat(fin)

        dias_desde_inicio = (d1 - inicio_global).days
        duracion = (d2 - d1).days + 1

        x1 = dias_desde_inicio * PIXELS_POR_DIA + 150
        x2 = x1 + duracion * PIXELS_POR_DIA
        y1 = i * (ALTO_BARRA + ESPACIO) + 20
        y2 = y1 + ALTO_BARRA

        # nombre
        canvas.create_text(
            10,
            (y1 + y2) // 2,
            text=nombre,
            anchor="w",
            font=("Arial", 10)
        )

        # barra
        canvas.create_rectangle(
            x1, y1, x2, y2,
            fill=color,
            outline="black"
        )

    # ---------------- AJUSTES ----------------
    def actualizar_scroll(_):
        canvas.configure(scrollregion=canvas.bbox("all"))

    inner.bind("<Configure>", actualizar_scroll)

def obtener_proyectos():
    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, texto, fecha_inicio, fecha_fin, color, prioridad
        FROM eventos
        WHERE tipo = 'Proyecto'
        ORDER BY fecha_inicio
    """)
    proyectos = cursor.fetchall()
    conn.close()
    return proyectos

def sincronizar_calendarios():
    fecha = cal_izq.selection_get()

    cal_izq.see(fecha)

    if fecha.month == 12:
        siguiente = fecha.replace(year=fecha.year + 1, month=1, day=1)
    else:
        siguiente = fecha.replace(month=fecha.month + 1, day=1)

    cal_der.see(siguiente)

def sincronizar_desde_izquierdo():
    fecha = cal_izq.selection_get()
    cal_izq.see(fecha)

    if fecha.month == 12:
        siguiente = fecha.replace(year=fecha.year + 1, month=1, day=1)
    else:
        siguiente = fecha.replace(month=fecha.month + 1, day=1)

    cal_der.see(siguiente)


def sincronizar_desde_derecho():
    fecha = cal_der.selection_get()

    if fecha.month == 1:
        anterior = fecha.replace(year=fecha.year - 1, month=12, day=1)
    else:
        anterior = fecha.replace(month=fecha.month - 1, day=1)

    cal_izq.see(anterior)


def abrir_popup_agregar(evento_id=None):
    popup = tk.Toplevel(root)
    popup.title("Evento")
    popup.geometry("500x720")
    popup.resizable(False, False)
    popup.transient(root)
    popup.grab_set()

    modo_edicion = evento_id is not None

    # ---------------- VARIABLES ----------------
    nombre_var = tk.StringVar()
    tipo_var = tk.StringVar(value="Proyecto")
    prioridad_var = tk.StringVar(value="Media")
    fecha_inicio = tk.StringVar()
    fecha_fin = tk.StringVar()
    proyecto_var = tk.StringVar()

    # ---------------- CARGAR DATOS (EDICIÓN) ----------------
    if modo_edicion:
        evento = obtener_evento_por_id(evento_id)
        nombre_var.set(evento[4])
        tipo_var.set(evento[7])
        prioridad_var.set(evento[6])
        fecha_inicio.set(evento[1])
        fecha_fin.set(evento[2])
        if evento[7] == "Tarea" and evento[8]:
            proyecto_var.set(str(evento[8]))

    # ================= FORMULARIO =================
    frame_form = tk.Frame(popup)
    frame_form.pack(fill="x", padx=10, pady=5)

    tk.Label(frame_form, text="Nombre").pack(anchor="w")
    entry_texto = tk.Entry(frame_form, textvariable=nombre_var, width=45)
    entry_texto.pack()

    tk.Label(frame_form, text="Tipo").pack(anchor="w", pady=(10, 0))
    frame_tipo = tk.Frame(frame_form)
    frame_tipo.pack(anchor="w")

    tk.Radiobutton(frame_tipo, text="Proyecto", variable=tipo_var, value="Proyecto").pack(side="left")
    tk.Radiobutton(frame_tipo, text="Tarea", variable=tipo_var, value="Tarea").pack(side="left")

    tk.Label(frame_form, text="Prioridad").pack(anchor="w", pady=(10, 0))
    tk.OptionMenu(frame_form, prioridad_var, "Alta", "Media", "Baja").pack(anchor="w")

    # ================= PROYECTO =================
    frame_proyecto = tk.LabelFrame(popup, text="Proyecto")
    frame_proyecto.pack(fill="x", padx=10, pady=5)

    cal_proyecto = Calendar(frame_proyecto, selectmode="day", locale="es_ES")
    cal_proyecto.pack(pady=5)

    lbl_inicio = tk.Label(frame_proyecto, text="Inicio: -")
    lbl_inicio.pack(anchor="w")

    lbl_fin = tk.Label(frame_proyecto, text="Fin: -")
    lbl_fin.pack(anchor="w")

    if modo_edicion:
        if fecha_inicio.get():
            lbl_inicio.config(text=f"Inicio: {fecha_inicio.get()}")
            cal_proyecto.selection_set(
                datetime.fromisoformat(fecha_inicio.get()).date()
            )

        if fecha_fin.get():
            lbl_fin.config(text=f"Fin: {fecha_fin.get()}")


    lbl_inicio = tk.Label(frame_proyecto, text="Inicio: -")
    lbl_inicio.pack(anchor="w")

    lbl_fin = tk.Label(frame_proyecto, text="Fin: -")
    lbl_fin.pack(anchor="w")

    modo_fecha = tk.StringVar(value="inicio")
    frame_modo = tk.Frame(frame_proyecto)
    frame_modo.pack()

    tk.Radiobutton(frame_modo, text="Inicio", variable=modo_fecha, value="inicio").pack(side="left")
    tk.Radiobutton(frame_modo, text="Fin", variable=modo_fecha, value="fin").pack(side="left")

    def seleccionar_fecha(_):
        fecha = cal_proyecto.selection_get().isoformat()
        if modo_fecha.get() == "inicio":
            fecha_inicio.set(fecha)
            lbl_inicio.config(text=f"Inicio: {fecha}")
        else:
            fecha_fin.set(fecha)
            lbl_fin.config(text=f"Fin: {fecha}")

    cal_proyecto.bind("<<CalendarSelected>>", seleccionar_fecha)

    # ================= TAREA =================
    frame_tarea = tk.LabelFrame(popup, text="Tarea")
    frame_tarea.pack(fill="x", padx=10, pady=5)

    frame_hora = tk.Frame(frame_tarea)
    frame_hora.pack(anchor="w")

    spin_h = tk.Spinbox(frame_hora, from_=0, to=23, width=3)
    spin_m = tk.Spinbox(frame_hora, from_=0, to=59, width=3)
    spin_h.pack(side="left")
    tk.Label(frame_hora, text=":").pack(side="left")
    spin_m.pack(side="left")

    tk.Label(frame_tarea, text="Proyecto").pack(anchor="w", pady=(5, 0))

    proyectos = obtener_proyectos()
    opciones = {f"{p[1]} (#{p[0]})": p[0] for p in proyectos}

    if opciones:
        primera = next(iter(opciones))
        proyecto_var.set(primera)
        tk.OptionMenu(frame_tarea, proyecto_var, primera, *opciones.keys()).pack(anchor="w")
    else:
        tk.Label(frame_tarea, text="No hay proyectos", fg="red").pack(anchor="w")


    # ================= MOSTRAR / OCULTAR =================
    def actualizar_vista(*_):
        # El calendario SIEMPRE visible
        frame_proyecto.pack(fill="x", padx=10, pady=5)

        if tipo_var.get() == "Proyecto":
            frame_tarea.forget()
        else:
            frame_tarea.pack(fill="x", padx=10, pady=5)


    # ================= GUARDAR =================
    frame_btn = tk.Frame(popup)
    frame_btn.pack(side="bottom", pady=15)

    def guardar():
        texto = nombre_var.get().strip()
        if not texto:
            messagebox.showwarning("Error", "Nombre vacío")
            return

        if tipo_var.get() == "Proyecto":
            if fecha_fin.get() < fecha_inicio.get():
                messagebox.showwarning("Error", "Fechas inválidas")
                return

            if modo_edicion:
                editar_proyecto_bd(
                    evento_id,
                    fecha_inicio.get(),
                    fecha_fin.get(),
                    texto,
                    prioridad_var.get()
                )
            else:
                color = obtener_color_automatico()
                agregar_proyecto_bd(
                    fecha_inicio.get(),
                    fecha_fin.get(),
                    texto,
                    color,
                    prioridad_var.get()
                )

        else:  # TAREA
            if not opciones:
                messagebox.showwarning("Error", "No hay proyectos")
                return

            pid = opciones[proyecto_var.get()]
            hora = f"{int(spin_h.get()):02d}:{int(spin_m.get()):02d}"
            inicio = fecha_inicio.get()
            fin = fecha_fin.get()

            if not inicio or not fin:
                messagebox.showwarning("Error", "Selecciona inicio y fin de la tarea")
                return

            if fin < inicio:
                messagebox.showwarning("Error", "Fechas inválidas")
                return

            # --- VALIDAR CONTRA PROYECTO ---
            conn = conectar_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT fecha_inicio, fecha_fin FROM eventos WHERE id = ?",
                (pid,)
            )
            p_inicio, p_fin = cursor.fetchone()
            conn.close()

            if inicio < p_inicio or fin > p_fin:
                messagebox.showwarning(
                    "Error",
                    "La tarea debe estar dentro del rango del proyecto"
                )
                return

            if modo_edicion:
                editar_tarea_bd(
                    evento_id,
                    inicio,
                    fin,
                    hora,
                    texto,
                    prioridad_var.get(),
                    pid
                )
            else:
                color = obtener_color_proyecto(pid)
                agregar_tarea_bd(
                    inicio,
                    fin,
                    hora,
                    texto,
                    color,
                    prioridad_var.get(),
                    pid
                )


        popup.destroy()
        mostrar_eventos()
        marcar_dias_con_eventos()

    texto_btn = "Guardar cambios" if modo_edicion else "Crear"
    tk.Button(frame_btn, text=texto_btn, command=guardar).pack()

# -------------------- INTERFAZ --------------------
proyectos_abiertos = set()

root = tk.Tk()
root.title("Calendario con Eventos")

# pantalla completa real desde el inicio
root.attributes("-fullscreen", True)

# teclas
root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))
root.bind("<F11>", lambda e: root.attributes("-fullscreen", True))

CAL_FONT = ("Arial", 14)

frame_centro = tk.Frame(root)
frame_centro.pack(expand=True)

frame_calendarios = tk.Frame(frame_centro)
frame_calendarios.pack(pady=10)


cal_izq = Calendar( #calendario izquierdo mostrara el primer mes
    frame_calendarios,
    selectmode="day",
    locale="es_ES",
    font=CAL_FONT,
    headersbackground="#2c3e50",
    headersforeground="white",
    selectbackground="#3498db",
    weekendbackground="#ecf0f1"
)
cal_izq.pack(side=tk.LEFT, padx=15)

cal_der = Calendar( #calendario derecho mostrara el segundo mes
    frame_calendarios,
    selectmode="day",
    locale="es_ES",
    font=CAL_FONT,
    headersbackground="#2c3e50",
    headersforeground="white",
    selectbackground="#3498db",
    weekendbackground="#ecf0f1"
)
cal_der.pack(side=tk.LEFT, padx=15)

cal_izq.bind("<<CalendarDisplayed>>", lambda e: sincronizar_desde_izquierdo())
cal_der.bind("<<CalendarDisplayed>>", lambda e: sincronizar_desde_derecho())



frame_botones = tk.Frame(frame_centro)
frame_botones.pack(pady=10)

tk.Button(frame_botones, text="Agregar", command=abrir_popup_agregar).pack(side=tk.LEFT, padx=5)

contenedor_eventos = tk.Frame(frame_centro)
contenedor_eventos.pack(fill="both", expand=True, pady=10, padx=40)

#__________________________

cal_izq.bind("<<CalendarSelected>>", lambda e: (
    sincronizar_calendarios(),
    mostrar_eventos(),
    marcar_dias_con_eventos()
))


tk.Button(
    frame_botones,
    text="Vista Gantt",
    command=mostrar_gantt
).pack(side=tk.LEFT, padx=5)
#_________________________


frame_nav = tk.Frame(root)
frame_nav.pack()

tk.Button(frame_nav, text="◀ Mes anterior", command=lambda: mover_mes(-1)).pack(side=tk.LEFT, padx=10)
tk.Button(frame_nav, text="Mes siguiente ▶", command=lambda: mover_mes(1)).pack(side=tk.LEFT, padx=10)



mostrar_eventos()
marcar_dias_con_eventos()

root.mainloop()
