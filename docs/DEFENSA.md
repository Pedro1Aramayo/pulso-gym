# Análisis y demostración del trabajo final

## Problema y actores

Recepción necesita decidir automáticamente si una persona puede entrenar. El reconocimiento responde **quién es**; las reglas determinan **si puede ingresar**. El socio confirma su marcación y el administrativo gestiona altas, pagos, horarios y consultas.

## Casos de uso

1. Registrar socio con tres fotografías y datos mínimos; rechazar DNI repetido.
2. Registrar pago y plan; crear un mes calendario, cerrar cualquier período anterior.
3. Configurar días y turnos de atención.
4. Identificar al socio por el rostro, consultar elegibilidad y proponer un ingreso.
5. Confirmar y persistir, o cancelar sin consumir entrenamientos.
6. Consultar ingresos por socio y fecha; exportar Excel/PDF con estado de membresías.
7. Desactivar/reactivar al socio sin perder su historial.

## Flujo principal

Cámara → un solo rostro → FaceNet512 → socio → estado y membresía → horario → antirrebote → cupo/regla diaria → panel Confirmar/Cancelar → revalidación transaccional → ingreso.

La cámara permanece abierta durante el modal y actualiza el video. La variable `modal` impide enviar nuevas inferencias. `finally` restablece ese estado incluso cuando la base falla. La operación de consulta no contiene INSERT ni UPDATE. Al confirmar se toma un bloqueo por socio; si dos solicitudes llegan simultáneamente, solo una puede consumir el último cupo. Las respuestas de una sesión de cámara anterior se descartan.

## Qué se reutilizó

Del Incremento 6: CameraManager, captura de fotografías, Haar Cascade, embeddings FaceNet512, distancia coseno, caché de referencias y puente a un proceso facial independiente. Se adaptaron sus consultas de alumnos a socios y se eliminó la escritura escolar del trabajador facial.

Se reemplazaron: tablas escolares, jornadas, entrada/salida de clase, formulario académico, login escolar y reportes de alumnos. Se agregaron: dominio de membresías, reglas de acceso, transacciones, pantallas de gimnasio, informes propios y nuevas pruebas.

## Guion de exposición (10–15 minutos)

1. Mostrar las dos ramas y explicar que el sistema escolar original quedó conservado.
2. Mostrar el DER: seguir la relación socio → membresía → ingreso y explicar horario como configuración global.
3. Abrir Horarios y agregar una franja del día actual si hace falta. Explicar cierre exclusivo y turnos separados.
4. Registrar a una persona voluntaria con fotos frontal y dos giros leves. Mostrar rechazo de un DNI duplicado.
5. Registrar un pago con plan de 8 entrenamientos. Ver vigencia y saldo inicial.
6. Abrir cámara, verificar nombre y DNI en el modal, elegir Cancelar. Mostrar que no cambió el saldo ni aparece un ingreso.
7. Esperar al menos 10 segundos, volver a identificarse y elegir OK. Mostrar un ingreso y saldo 7.
8. Volver a mirar inmediatamente: explicar supresión de propuestas y antirrebote persistido de 30 segundos.
9. Renovar con Todos los días; esperar a que pase el antirrebote. Si ya ingresó hoy se rechaza por la regla diaria, aunque el ingreso pertenezca al período anterior.
10. Renovar con Pase libre. Mostrar que admite otro ingreso después de los 30 segundos, explicando la pérdida de saldo/período anterior.
11. Quitar la franja actual o cerrar el día; el reconocimiento debe informar gimnasio cerrado sin registrar nada.
12. Exportar Excel/PDF y mostrar las dos secciones: ingresos del período consultado y membresías actuales.
13. Ejecutar pruebas automáticas para demostrar fin de mes, cupo agotado, vencimiento y concurrencia sin cambiar el reloj del equipo.

## Preguntas que conviene saber responder

- ¿Por qué 2 veces por semana no se controla por semana? Porque la guía define ocho accesos libres dentro del mes.
- ¿Por qué no son 30 días? Porque pide vencer el mismo día del siguiente mes; se ajusta al último día cuando no existe.
- ¿Qué ocurre si cancela? No se ejecuta la función de escritura; el saldo sigue igual.
- ¿Qué ocurre si renueva antes? Empieza un período nuevo en la fecha del pago, se cierra el anterior y se advierte que pierde el remanente.
- ¿Cómo se evitan duplicados? Intervalos de supresión, bloqueo por socio, revalidación y UUID único de solicitud.
- ¿Para qué sigue existiendo un socio sin membresía? Para conservar identidad/historial y permitir renovar sin volver a registrar sus fotografías.
- ¿Se reconocen varias personas a la vez? No: la escena debe tener un solo rostro.
- ¿Se registran salidas? No las requiere este contexto; cada ingreso confirmado es un entrenamiento.

## Alcance y límites explícitos

Prototipo académico local de recepción, sin autenticación por roles, cobros en línea ni apertura física de molinetes. No incorpora detección de vida, reconocimiento a prueba de fotografías, gestión de feriados ni horarios que crucen medianoche. No almacena auditoría de rechazos; sí muestra su motivo. Los errores técnicos se muestran con un mensaje comprensible y su detalle aparece en la terminal.

Se debe hacer la demostración facial con personas que acepten participar. No se incluyeron fotografías privadas ni datos reales en el ZIP. Los resultados automáticos no sustituyen la prueba con webcam, iluminación y rostros del aula.

## Antes de entregar al docente

- Completar nombre del alumno, curso y fecha de presentación según corresponda.
- Guardar el DER en DrawSQL y revisar las relaciones importadas.
- Publicar la rama en el repositorio propio conservando `main`.
- Ejecutar desde una instalación nueva, cargar los socios de demostración y probar la webcam.
- Leer estas decisiones y practicar el guion para poder explicar el código.
