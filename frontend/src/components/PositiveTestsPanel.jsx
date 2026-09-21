import { useState } from "react";
import { apiPost } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock } from "./common";

export default function PositiveTestsPanel() {
  const [form, setForm] = useState({ service_id: "0x22", subfunction_id: "", did: "", rid: "", project_id: "" });
  const [testCase, setTestCase] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setTestCase(null);
    try {
      const body = {
        service_id: form.service_id,
        subfunction_id: form.subfunction_id || null,
        did: form.did || null,
        rid: form.rid || null,
        parameters: {},
        project_id: form.project_id || null,
      };
      const result = await apiPost("/uds/tests/positive", body);
      setTestCase(result.test_case);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Positive Tests</h2>
      <Field label="Service ID">
        <input style={inputStyle} value={form.service_id} onChange={(e) => setForm({ ...form, service_id: e.target.value })} />
      </Field>
      <Field label="Subfunction ID (optional)">
        <input style={inputStyle} value={form.subfunction_id} onChange={(e) => setForm({ ...form, subfunction_id: e.target.value })} />
      </Field>
      <Field label="DID (optional)">
        <input style={inputStyle} value={form.did} onChange={(e) => setForm({ ...form, did: e.target.value })} />
      </Field>
      <Field label="RID (optional)">
        <input style={inputStyle} value={form.rid} onChange={(e) => setForm({ ...form, rid: e.target.value })} />
      </Field>
      <Field label="Project ID (optional — saves the test case if set)">
        <input style={inputStyle} value={form.project_id} onChange={(e) => setForm({ ...form, project_id: e.target.value })} />
      </Field>
      <button style={buttonStyle} onClick={generate} disabled={loading || !form.service_id}>
        {loading ? "Generating..." : "Generate Positive Test"}
      </button>

      <ErrorBanner message={error} />

      {testCase && (
        <div style={{ marginTop: "1rem" }}>
          <h3>{testCase.title}</h3>
          <p>{testCase.objective}</p>
          <p><strong>Preconditions:</strong> {testCase.preconditions.length ? testCase.preconditions.join(", ") : "none documented"}</p>
          <p><strong>Request:</strong> {testCase.request.request_bytes}</p>
          <p><strong>Expected response:</strong> {testCase.expected_response.service_id}{!testCase.is_complete && " (incomplete — see missing_info)"}</p>
          <p><strong>Pass criteria:</strong></p>
          <ul>{testCase.pass_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
          <p><strong>Fail criteria:</strong></p>
          <ul>{testCase.fail_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
          {testCase.source && (
            <p style={{ fontSize: "0.85rem", color: "var(--text)" }}>
              Source: {testCase.source.document_name} v{testCase.source.document_version}, page{" "}
              {testCase.source.page_number}, section {testCase.source.section_title}, chunk {testCase.source.chunk_id}
            </p>
          )}
          <JsonBlock data={testCase} />
        </div>
      )}
      {!testCase && !error && !loading && <EmptyState text="Enter a service and generate a positive test case." />}
    </div>
  );
}
