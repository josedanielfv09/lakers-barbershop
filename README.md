# Los Lakers Barbershop – versión web (Flask)

## Probar en tu computador
    pip install -r requirements.txt
    python app.py          -> abre http://127.0.0.1:5000
Contraseña admin local: lakers2026 (atajo Ctrl + Shift + L en la página)

## Subir a Render (gratis)
1. Sube esta carpeta a un repositorio de GitHub (git init, git add ., git commit, git push).
2. En render.com: New + > Blueprint > elige tu repositorio (usa render.yaml). Plan Free.
3. Cuando te lo pida, escribe tu ADMIN_PASSWORD (tu contraseña de admin).
4. Espera el deploy y abre la URL que termina en .onrender.com

## Importante (plan gratis de Render)
- Se duerme tras ~15 min sin visitas; la primera carga tarda ~1 min.
- El disco es temporal: citas y ventas se borran cuando Render reinicia o redepliega.
  Para una sustentación, haz tus reservas de ejemplo justo antes de mostrarla.
- Las ventas y ganancias solo se ven con la contraseña de admin (el servidor rechaza todo sin sesión).
