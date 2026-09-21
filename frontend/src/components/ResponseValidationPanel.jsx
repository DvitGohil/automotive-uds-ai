import { useState } from "react";
import { apiPost } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock, StatusBadge } from "./common";

export default function ResponseValidationPanel() {
  const [testType, setTestType] = useState("positive");
  const [form, setForm] = useState({
    service_id: "0x22", subfunction_id: "", did: "", rid: "",
    category: "missing_required_field", invalid_condition: "", expected_nrc: "",
  });
  const [actualResponse, setActualResponse] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const validate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const generation =
        testType === "positive"
          ? {
              service_id: form.service_id,
              subfunction_id: form.subfunction_id || null,
              did: form.did || null,
              rid: form.rid || null,
              parameters: {},
            }
          : {
              category: form.category,
              service_id: form.service_id,
              subfunction_id: form.subfunction_id || null,
              did: form.did || null,
              rid: form.rid || null,
              parameters: {},
              invalid_condition: form.invalid_condition || null,
              expected_nrc: form.expected_nrc || null,
            };
      const body = { test_type: testType, generation, actual_response: actualResponse };
      const validated = await apiPost("/uds/response-validation", body);
      setResult(validated);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>ECU Response Validation</h2>
      <p style={{ color: "var(--text)" }}>
        Enter the actual raw ECU response (hex bytes, e.g. "62 F1 90 31 48 47"). Validation is performed
        entirely by the backend — this page only displays its result.
      </p>
      <Field label="Test Type">
        <select style={inputStyle} value={testType} onChange={(e) => setTestType(e.target.value)}>
          <option value="positive">Positive</option>
          <option value="negative">Negative</option>
        </select>
      </Field>
      {testType === "negative" && (
        <Field label="Scenario Category">
          <input style={inputStyle} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
        </Field>
      )}
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
      {testType === "negative" && (
        <Field label="Expected NRC (optional)">
          <input style={inputStyle} value={form.expected_nrc} onChange={(e) => setForm({ ...form, expected_nrc: e.target.value })} />
        </Field>
      )}
      <Field label="Actual ECU Response (hex bytes)">
        <input style={inputStyle} value={actualResponse} onChange={(e) => setActualResponse(e.target.value)} placeholder="62 F1 90 31 48 47" />
      </Field>
      <button style={buttonStyle} onClick={validate} disabled={loading || !form.service_id || !actualResponse}>
        {loading ? "Validating..." : "Validate Response"}
      </button>

      <ErrorBanner message={error} />

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <p><StatusBadge status={result.status} /></p>
          <p><strong>Test case:</strong> {result.test_case_id}</p>
          <p><strong>Request:</strong> {result.request_bytes}</p>
          <p><strong>Expected:</strong> {result.expected_response_summary}</p>
          <p><strong>Actual:</strong> {result.actual_response}</p>
          {result.nrc && <p><strong>NRC:</strong> {result.nrc}</p>}
          {result.mismatch_details?.length > 0 && (
            <>
              <p><strong>Mismatch details:</strong></p>
              <ul>{result.mismatch_details.map((m, i) => <li key={i}>{m}</li>)}</ul>
            </>
          )}
          <p><strong>Reason:</strong> {result.reason}</p>
          <JsonBlock data={result} />
        </div>
      )}
      {!result && !error && !loading && <EmptyState text="Fill in the request details and the actual ECU response, then validate." />}
    </div>
  );
}
