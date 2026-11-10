# Validación realizada

Fecha: 10 de noviembre de 2026.

## Resultado

**21 pruebas automatizadas aprobadas**, sin omisiones en la ejecución con PostgreSQL:

- 8 pruebas de reglas: mes calendario y bisiesto, vigencia, los tres cupos, ausencia de límite semanal artificial, planes diarios, antirrebote, franjas horarias y socio inválido.
- 6 pruebas de interfaz: Cancelar no persiste, OK invoca una sola confirmación, video activo sin nuevas inferencias durante el modal, rechazo sin modal, descarte de respuesta antigua y reanudación tras error.
- 7 pruebas con PostgreSQL real: consulta sin escritura e idempotencia, renovación y revalidación de plan, concurrencia sobre el último cupo, cambio de horario durante confirmación, superposición de franjas, Todos los días frente a Pase libre, vencimiento e inactividad.

Se creó una base temporal independiente para estas comprobaciones. No se usaron ni modificaron las tablas del proyecto escolar.

## Otras comprobaciones

- Compilación de los módulos Python.
- Carga del modelo **FaceNet512 real**, primera inferencia y lectura de referencias desde un esquema PostgreSQL vacío mediante el proceso facial reutilizado. No se usaron fotografías personales para esa prueba.
- Exportación de un Excel de dos hojas y lectura posterior de sus valores. Verificación de que el contenido textual se guarda como texto y no como fórmula.
- Exportación de un PDF de dos páginas, renderizado y revisión visual de ambas páginas.
- Capturas de las pantallas Acceso facial y Membresías, con revisión visual de textos, disposición y legibilidad. Las capturas usan datos ficticios de ejemplo.
- DER SVG generado a partir del esquema implementado y revisado visualmente.

Entorno: Windows, Python 3.12.6, PySide6 6.11.2, DeepFace 0.0.101 y PostgreSQL 17 temporal. El archivo Docker propone PostgreSQL 16; su arranque no se comprobó porque Docker Desktop no estaba en ejecución. El esquema usa funcionalidades presentes en ambas versiones.

## Verificaciones pendientes antes de exponer

- Instalar las dependencias desde cero con Internet en el equipo de entrega; en esta preparación se usó el entorno disponible del proyecto original.
- Iniciar el stack Docker con su volumen nuevo.
- Registrar rostros voluntarios y demostrar reconocimiento real con webcam, confirmación y rechazo. Se comprobó el motor, pero **no se midió su precisión ni se hizo una prueba facial completa con una persona**.
- Publicar la rama del trabajo en GitHub y guardar el DER en DrawSQL. El ZIP no equivale a esas publicaciones.

No se afirma que estas comprobaciones sustituyan la demostración funcional requerida por el docente.
