-- Contexto B: identidad, membresías y accesos. Base independiente.
CREATE TABLE socio (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    apellido VARCHAR(100) NOT NULL,
    dni VARCHAR(20) NOT NULL UNIQUE,
    celular VARCHAR(40) NOT NULL DEFAULT '',
    correo_electronico VARCHAR(200) NOT NULL DEFAULT '',
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE foto_socio (
    id SERIAL PRIMARY KEY,
    socio_id INTEGER NOT NULL REFERENCES socio(id),
    angulo VARCHAR(20) NOT NULL CHECK (angulo IN ('frontal','izquierdo','derecho')),
    imagen BYTEA NOT NULL,
    UNIQUE(socio_id, angulo)
);
CREATE TABLE plan (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    cupo INTEGER CHECK (cupo > 0),
    una_vez_dia BOOLEAN NOT NULL DEFAULT FALSE
);
INSERT INTO plan(nombre,cupo,una_vez_dia) VALUES
('2 veces por semana',8,FALSE), ('3 veces por semana',12,FALSE),
('5 veces por semana',20,FALSE), ('Todos los días',NULL,TRUE),
('Pase libre',NULL,FALSE);
CREATE TABLE membresia (
    id SERIAL PRIMARY KEY,
    socio_id INTEGER NOT NULL REFERENCES socio(id),
    plan_id INTEGER NOT NULL REFERENCES plan(id),
    inicio DATE NOT NULL,
    vence DATE NOT NULL CHECK (vence > inicio),
    cerrada_en TIMESTAMPTZ,
    pagado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    importe NUMERIC(12,2) NOT NULL CHECK (importe >= 0)
);
-- La renovación anticipada cierra el período anterior, sin borrar su historial.
CREATE UNIQUE INDEX una_membresia_abierta ON membresia(socio_id) WHERE cerrada_en IS NULL;
CREATE TABLE horario (
    id SERIAL PRIMARY KEY,
    dia INTEGER NOT NULL CHECK (dia BETWEEN 0 AND 6),
    abre TIME NOT NULL,
    cierra TIME NOT NULL CHECK (cierra > abre),
    UNIQUE(dia, abre, cierra)
);
-- Configuración inicial editable: lunes a viernes, 07:00 a 22:00.
INSERT INTO horario(dia,abre,cierra) SELECT d, '07:00'::time, '22:00'::time FROM generate_series(0,4) d;
CREATE TABLE ingreso (
    id BIGSERIAL PRIMARY KEY,
    membresia_id INTEGER NOT NULL REFERENCES membresia(id),
    instante TIMESTAMPTZ NOT NULL DEFAULT now(),
    solicitud UUID NOT NULL UNIQUE
);
CREATE INDEX ingreso_membresia_fecha ON ingreso(membresia_id,instante);
