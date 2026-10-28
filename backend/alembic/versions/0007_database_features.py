"""Install aggregate views, feedback audit trigger and a controlled procedure.

Revision ID: 0007_database_features
"""
from alembic import op

revision = "0007_database_features"
down_revision = "0006_batch_filenames"
branch_labels = None
depends_on = None


VIEWS = [
    """CREATE VIEW vw_batch_analysis_summary AS
    SELECT b.batch_analysis_id, b.requested_by_user_id, b.source_filename,
           b.status, b.row_count, b.accepted_count, b.rejected_count,
           b.inference_run_id, COUNT(p.fraud_prediction_id) AS scored_count,
           COALESCE(SUM(CASE WHEN p.predicted_label = 1 THEN 1 ELSE 0 END),0) AS flagged_count,
           AVG(p.risk_score) AS mean_risk
    FROM batch_analyses b LEFT JOIN fraud_predictions p
      ON p.inference_run_id = b.inference_run_id
    GROUP BY b.batch_analysis_id, b.requested_by_user_id, b.source_filename,
             b.status, b.row_count, b.accepted_count, b.rejected_count, b.inference_run_id""",
    """CREATE VIEW vw_product_review_summary AS
    SELECT p.product_id, p.source_system, p.external_product_key, p.display_name,
           COUNT(r.review_id) AS review_count, AVG(r.rating) AS mean_rating
    FROM products p LEFT JOIN reviews r ON r.product_id = p.product_id
    GROUP BY p.product_id, p.source_system, p.external_product_key, p.display_name""",
]

AUDIT_FUNCTION = """
CREATE FUNCTION audit_review_feedback() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE old_data jsonb; new_data jsonb; actor bigint; record_key bigint;
BEGIN
  actor := NULLIF(current_setting('neurograph.actor_id', true), '')::bigint;
  IF TG_OP <> 'INSERT' THEN
    old_data := jsonb_build_object('review_id', OLD.review_id,
      'submitted_by_user_id', OLD.submitted_by_user_id, 'feedback_type', OLD.feedback_type,
      'ground_truth_label', OLD.ground_truth_label, 'status', OLD.status);
    record_key := OLD.feedback_id;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    new_data := jsonb_build_object('review_id', NEW.review_id,
      'submitted_by_user_id', NEW.submitted_by_user_id, 'feedback_type', NEW.feedback_type,
      'ground_truth_label', NEW.ground_truth_label, 'status', NEW.status);
    record_key := NEW.feedback_id;
  END IF;
  INSERT INTO audit_logs(actor_user_id, action, entity_type, entity_key, before_data, after_data)
  VALUES (actor, 'feedback.' || lower(TG_OP), 'review_feedback', record_key::text, old_data, new_data);
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$
"""

PROCEDURE = """
CREATE PROCEDURE resolve_review_feedback(p_feedback_id bigint, p_actor_id bigint, p_status text)
LANGUAGE plpgsql AS $$
BEGIN
  IF p_status NOT IN ('triaged','resolved','rejected') THEN
    RAISE EXCEPTION 'Invalid feedback resolution' USING ERRCODE = '22023';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM users u JOIN roles r ON r.role_id = u.role_id
                 WHERE u.user_id = p_actor_id AND u.is_active AND r.role_key = 'ADMIN') THEN
    RAISE EXCEPTION 'Administrator required' USING ERRCODE = '42501';
  END IF;
  PERFORM set_config('neurograph.actor_id', p_actor_id::text, true);
  UPDATE review_feedback SET status = p_status WHERE feedback_id = p_feedback_id;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Feedback not found' USING ERRCODE = 'P0002';
  END IF;
END $$
"""


def upgrade():
    for statement in VIEWS:
        op.execute(statement)
    op.create_index('ix_feedback_owner_status', 'review_feedback', ['submitted_by_user_id', 'status', 'created_at'])
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(AUDIT_FUNCTION)
        op.execute("CREATE TRIGGER trg_review_feedback_audit AFTER INSERT OR UPDATE OR DELETE ON review_feedback FOR EACH ROW EXECUTE FUNCTION audit_review_feedback()")
        op.execute(PROCEDURE)
        op.execute("REVOKE ALL ON PROCEDURE resolve_review_feedback(bigint, bigint, text) FROM PUBLIC")


def downgrade():
    if op.get_bind().dialect.name == 'postgresql':
        op.execute("DROP PROCEDURE resolve_review_feedback(bigint, bigint, text)")
        op.execute("DROP TRIGGER trg_review_feedback_audit ON review_feedback")
        op.execute("DROP FUNCTION audit_review_feedback()")
    op.drop_index('ix_feedback_owner_status', table_name='review_feedback')
    op.execute("DROP VIEW vw_product_review_summary")
    op.execute("DROP VIEW vw_batch_analysis_summary")
