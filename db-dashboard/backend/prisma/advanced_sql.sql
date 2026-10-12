-- ==============================================================================
-- Advanced SQL for NeuroGraph-DB (VIT BCSE302P Mandatory Rubric Requirements)
-- 1. Raw SQL View: v_model_performance_summary
-- 2. Stored Procedure: sp_record_experiment_run
-- 3. Trigger & Function: trg_audit_experiment_runs
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. Raw SQL View: v_model_performance_summary
-- Aggregates experiment runs by model and variant with rankings and averages.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_model_performance_summary AS
SELECT 
    m.name AS model_name,
    v.name AS variant_name,
    COUNT(r.id) AS total_runs,
    ROUND(AVG(r."f1Macro")::numeric, 4) AS avg_f1_macro,
    ROUND(AVG(r.auc)::numeric, 4) AS avg_auc,
    ROUND(AVG(r.precision)::numeric, 4) AS avg_precision,
    ROUND(AVG(r.recall)::numeric, 4) AS avg_recall,
    ROUND(AVG(r."timeSec")::numeric, 2) AS avg_time_sec,
    MAX(r.auc) AS peak_auc,
    MAX(r."f1Macro") AS peak_f1
FROM "ExperimentRun" r
JOIN "MLModel" m ON r."mlModelId" = m.id
JOIN "GraphVariant" v ON r."graphVariantId" = v.id
GROUP BY m.name, v.name
ORDER BY avg_auc DESC;

-- ------------------------------------------------------------------------------
-- 2. Stored Procedure: sp_record_experiment_run
-- Inserts or updates an experiment run transactionally.
-- ------------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE sp_record_experiment_run(
    p_model_name TEXT,
    p_variant_name TEXT,
    p_seed INT,
    p_time_sec FLOAT8,
    p_f1_macro FLOAT8,
    p_precision FLOAT8,
    p_recall FLOAT8,
    p_auc FLOAT8
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_model_id INT;
    v_variant_id INT;
BEGIN
    -- Ensure ML Model exists
    SELECT id INTO v_model_id FROM "MLModel" WHERE name = p_model_name;
    IF v_model_id IS NULL THEN
        INSERT INTO "MLModel" (name, description) VALUES (p_model_name, 'Created by stored procedure')
        RETURNING id INTO v_model_id;
    END IF;

    -- Ensure Graph Variant exists
    SELECT id INTO v_variant_id FROM "GraphVariant" WHERE name = p_variant_name;
    IF v_variant_id IS NULL THEN
        INSERT INTO "GraphVariant" (name, description) VALUES (p_variant_name, 'Created by stored procedure')
        RETURNING id INTO v_variant_id;
    END IF;

    -- Upsert Experiment Run
    INSERT INTO "ExperimentRun" (
        seed, "timeSec", "f1Macro", precision, recall, auc, "graphVariantId", "mlModelId"
    )
    VALUES (
        p_seed, p_time_sec, p_f1_macro, p_precision, p_recall, p_auc, v_variant_id, v_model_id
    )
    ON CONFLICT ("graphVariantId", "mlModelId", seed)
    DO UPDATE SET
        "timeSec" = EXCLUDED."timeSec",
        "f1Macro" = EXCLUDED."f1Macro",
        precision = EXCLUDED.precision,
        recall = EXCLUDED.recall,
        auc = EXCLUDED.auc;
        
    RAISE NOTICE 'Recorded experiment run for model %, variant %, seed %', p_model_name, p_variant_name, p_seed;
END;
$$;

-- ------------------------------------------------------------------------------
-- 3. Trigger & Function: trg_audit_experiment_runs
-- Automatically writes an audit entry into AuditLog upon INSERT or DELETE
-- ------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_audit_experiment_run_change()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF (TG_OP = 'INSERT') THEN
        INSERT INTO "AuditLog" ("action", "method", "endpoint", "details", "timestamp")
        VALUES (
            'EXPERIMENT_RUN_INSERTED',
            'TRIGGER',
            'TABLE:ExperimentRun',
            json_build_object('runId', NEW.id, 'mlModelId', NEW."mlModelId", 'auc', NEW.auc, 'f1', NEW."f1Macro")::text,
            NOW()
        );
        RETURN NEW;
    ELSIF (TG_OP = 'DELETE') THEN
        INSERT INTO "AuditLog" ("action", "method", "endpoint", "details", "timestamp")
        VALUES (
            'EXPERIMENT_RUN_DELETED',
            'TRIGGER',
            'TABLE:ExperimentRun',
            json_build_object('runId', OLD.id, 'mlModelId', OLD."mlModelId")::text,
            NOW()
        );
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO "AuditLog" ("action", "method", "endpoint", "details", "timestamp")
        VALUES (
            'EXPERIMENT_RUN_UPDATED',
            'TRIGGER',
            'TABLE:ExperimentRun',
            json_build_object('runId', NEW.id, 'old_auc', OLD.auc, 'new_auc', NEW.auc)::text,
            NOW()
        );
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_audit_experiment_runs ON "ExperimentRun";
CREATE TRIGGER trg_audit_experiment_runs
AFTER INSERT OR UPDATE OR DELETE ON "ExperimentRun"
FOR EACH ROW
EXECUTE FUNCTION fn_audit_experiment_run_change();
