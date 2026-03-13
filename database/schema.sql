-- ==============================================================================
-- CEREBRO IA - ESQUEMA DE BASE DE DATOS E INGESTA (TIMESCALE DB)
-- Activo Inicial: XAUUSD (Oro)
-- ==============================================================================

-- 1. Habilitar el motor de series temporales (Crítico)
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ==============================================================================
-- TABLA 1: VELAS M1 (Minuto a Minuto)
-- ==============================================================================
CREATE TABLE IF NOT EXISTS xauusd_m1 (
    time TIMESTAMPTZ NOT NULL, -- Obliga a guardar en UTC (Vital para evitar bugs horarios)
    open DOUBLE PRECISION NOT NULL,
    high DOUBLE PRECISION NOT NULL,
    low DOUBLE PRECISION NOT NULL,
    close DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL
);

-- Convertir la tabla estándar en una Hypertable particionada por tiempo (chunks de 1 semana por defecto)
SELECT create_hypertable('xauusd_m1', 'time', if_not_exists => TRUE);

-- Índice de compresión y búsqueda rápida para el Backtester
CREATE INDEX IF NOT EXISTS ix_xauusd_m1_time ON xauusd_m1 (time DESC);


-- ==============================================================================
-- TABLA 2: DATA DE TICKS (Alta Frecuencia)
-- ==============================================================================
-- Nota del Arquitecto: Los ticks consumen muchísimo espacio. Se usarán para 
-- modelar el spread dinámico y el flujo de órdenes (Order Flow) del broker Vantage.
CREATE TABLE IF NOT EXISTS xauusd_ticks (
    time TIMESTAMPTZ NOT NULL,
    bid DOUBLE PRECISION NOT NULL,
    ask DOUBLE PRECISION NOT NULL,
    bid_volume DOUBLE PRECISION NOT NULL,
    ask_volume DOUBLE PRECISION NOT NULL
);

-- Los ticks generan gigabytes de data, la partición por tiempo es obligatoria
SELECT create_hypertable('xauusd_ticks', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS ix_xauusd_ticks_time ON xauusd_ticks (time DESC);
ALTER TABLE xauusd_m1 ADD CONSTRAINT xauusd_m1_time_unique UNIQUE (time);