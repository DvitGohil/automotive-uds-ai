import { useState } from "react";
import { apiPost } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock } from "./common";

export default function RequestConstructionPanel() {
  const [form, setForm] = useState({ service_id: "0x22", subfunction_id: "", did: "", rid: "" });
  const [result, setResult] = useState(null);
  const [validation, setValidation] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const payload = () => ({
    service_id: form.service_id,
    subfunction_id: form.subfunction_id || null,
    did: form.did || null,
    rid: form.rid || null,
    parameters: {},
  });

  const construct = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setValidation(null);
    try {
      const body = payload();
      const constructed = await apiPost("/uds/requests/construct", body);
      setResult(constructed);
      const validated = await apiPost("/uds/requests/validate", body);
      setValidation(validated);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Request Construction</h2>
      <Field label="Service ID (e.g. 0x22)">
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
      <button style={buttonStyle} onClick={construct} disabled={loading || !form.service_id}>
        {loading ? "Constructing..." : "Construct & Validate"}
      </button>

      <ErrorBanner message={error} />

      {result && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Constructed Request {result.success ? "✓" : "✗"}</h3>
          <JsonBlock data={result} />
        </div>
      )}
      {validation && (
        <div style={{ marginTop: "1rem" }}>
          <h3>Validation Result — {validation.valid ? "VALID" : "INVALID"}</h3>
          {validation.errors?.length > 0 && (
            <ul style={{ color: "#a11" }}>
              {validation.errors.map((e, i) => (
                <li key={i}>{e}</li>
              ))}
            </ul>
          )}
          <JsonBlock data={validation} />
        </div>
      )}
      {!result && !error && !loading && <EmptyState text="Enter a service ID and construct a request." />}
    </div>
  );
}
