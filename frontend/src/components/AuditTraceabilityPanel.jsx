import { useState } from "react";
import { apiGet } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock, StatusBadge } from "./common";

export default function AuditTraceabilityPanel() {
  const [projectId, setProjectId] = useState("");
  const [auditRecords, setAuditRecords] = useState(null);
  const [testCaseRowId, setTestCaseRowId] = useState("");
  const [trace, setTrace] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const loadAudit = async () => {
    setLoading(true);
    setError(null);
    setAuditRecords(null);
    try {
      setAuditRecords(await apiGet(`/uds/audit/${projectId}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const loadTrace = async () => {
    setLoading(true);
    setError(null);
    setTrace(null);
    try {
      setTrace(await apiGet(`/uds/traceability/test-case/${testCaseRowId}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Audit &amp; Traceability</h2>

      <section style={{ marginBottom: "2rem" }}>
        <h3>Audit Log</h3>
        <Field label="Project ID">
          <input style={inputStyle} value={projectId} onChange={(e) => setProjectId(e.target.value)} />
        </Field>
        <button style={buttonStyle} onClick={loadAudit} disabled={loading || !projectId}>
          {loading ? "Loading..." : "Load Audit Records"}
        </button>
        {auditRecords && (
          <div style={{ marginTop: "0.75rem" }}>
            {auditRecords.length === 0 ? (
              <EmptyState text="No audit records for this project yet." />
            ) : (
              <ul>
                {auditRecords.map((a) => (
                  <li key={a.id} style={{ marginBottom: "0.4rem" }}>
                    <strong>{a.action}</strong> — {a.entity_type} {a.entity_id ? `(${a.entity_id})` : ""} —{" "}
                    <span style={{ color: "var(--text)" }}>{new Date(a.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      <section>
        <h3>Test Case Traceability</h3>
        <p style={{ color: "var(--text)" }}>
          Trace a test case back to its source document and forward to its validation results and templates.
        </p>
        <Field label="Test Case (row) ID">
          <input style={inputStyle} value={testCaseRowId} onChange={(e) => setTestCaseRowId(e.target.value)} />
        </Field>
        <button style={buttonStyle} onClick={loadTrace} disabled={loading || !testCaseRowId}>
          {loading ? "Loading..." : "Trace"}
        </button>

        <ErrorBanner message={error} />

        {trace && (
          <div style={{ marginTop: "0.75rem" }}>
            <p><strong>Title:</strong> {trace.test_case.title}</p>
            <p><strong>Type:</strong> {trace.test_case.is_negative_case ? "Negative" : "Positive"}</p>
            <p>
              <strong>Source:</strong>{" "}
              {trace.source
                ? `${trace.source.document_name || "?"} v${trace.source.document_version || "?"}, page ${
                    trace.source.page_number || "?"
                  }, chunk ${trace.source.chunk_id || "?"}`
                : "not documented"}
            </p>
            <p><strong>Validation results:</strong></p>
            {trace.validation_results.length === 0 ? (
              <EmptyState text="No ECU response validation has been run against this test case yet." />
            ) : (
              <ul>
                {trace.validation_results.map((v) => (
                  <li key={v.id}>
                    <StatusBadge status={v.passed ? "PASS" : "FAIL"} /> {v.validation_type} —{" "}
                    {new Date(v.created_at).toLocaleString()}
                  </li>
                ))}
              </ul>
            )}
            <p><strong>Audit trail for this test case:</strong></p>
            <ul>
              {trace.audit_trail.map((a) => (
                <li key={a.id}>
                  {a.action} — {new Date(a.created_at).toLocaleString()}
                </li>
              ))}
            </ul>
            <JsonBlock data={trace} />
          </div>
        )}
        {!trace && !error && !loading && <EmptyState text="Enter a test case row ID (returned when generating a test with a project ID) to trace it." />}
      </section>
    </div>
  );
}
