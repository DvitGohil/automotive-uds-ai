import { useState } from "react";
import { apiPost } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock } from "./common";

const CATEGORIES = [
  "missing_required_field",
  "malformed_field",
  "unsupported_service",
  "precondition_violation",
  "security_violation",
  "documented_nrc",
];

export default function NegativeTestsPanel() {
  const [form, setForm] = useState({
    category: "missing_required_field",
    service_id: "0x22",
    subfunction_id: "",
    did: "",
    rid: "",
    invalid_condition: "",
    expected_nrc: "",
    expected_nrc_name: "",
  });
  const [testCase, setTestCase] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setTestCase(null);
    try {
      const body = {
        category: form.category,
        service_id: form.service_id,
        subfunction_id: form.subfunction_id || null,
        did: form.did || null,
        rid: form.rid || null,
        parameters: {},
        invalid_condition: form.invalid_condition || null,
        expected_nrc: form.expected_nrc || null,
        expected_nrc_name: form.expected_nrc_name || null,
      };
      const result = await apiPost("/uds/tests/negative", body);
      setTestCase(result.test_case);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Negative Tests</h2>
      <Field label="Scenario Category">
        <select style={inputStyle} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
      </Field>
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
      <Field label="Documented Invalid Condition (optional)">
        <input style={inputStyle} value={form.invalid_condition} onChange={(e) => setForm({ ...form, invalid_condition: e.target.value })} />
      </Field>
      <Field label="Documented Expected NRC (optional, e.g. 0x22)">
        <input style={inputStyle} value={form.expected_nrc} onChange={(e) => setForm({ ...form, expected_nrc: e.target.value })} />
      </Field>
      <button style={buttonStyle} onClick={generate} disabled={loading || !form.service_id}>
        {loading ? "Generating..." : "Generate Negative Test"}
      </button>

      <ErrorBanner message={error} />

      {testCase && (
        <div style={{ marginTop: "1rem" }}>
          <h3>{testCase.title}</h3>
          <p>{testCase.objective}</p>
          <p><strong>Invalid condition:</strong> {testCase.invalid_condition}</p>
          <p>
            <strong>Expected NRC:</strong>{" "}
            {testCase.expected_nrc_known ? testCase.expected_negative_response.nrc : "unknown (not documented)"}
          </p>
          <p><strong>Pass criteria:</strong></p>
          <ul>{testCase.pass_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul>
          {testCase.source && (
            <p style={{ fontSize: "0.85rem", color: "var(--text)" }}>
              Source: {testCase.source.document_name} v{testCase.source.document_version}, chunk {testCase.source.chunk_id}
            </p>
          )}
          <JsonBlock data={testCase} />
        </div>
      )}
      {!testCase && !error && !loading && <EmptyState text="Choose a scenario category and generate a negative test case." />}
    </div>
  );
}
