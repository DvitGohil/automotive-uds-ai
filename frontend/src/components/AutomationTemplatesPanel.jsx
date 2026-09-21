import { useState } from "react";
import { apiPost } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock } from "./common";

export default function AutomationTemplatesPanel() {
  const [testType, setTestType] = useState("positive");
  const [form, setForm] = useState({
    service_id: "0x22", subfunction_id: "", did: "", rid: "",
    category: "missing_required_field", invalid_condition: "", expected_nrc: "",
  });
  const [template, setTemplate] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    setError(null);
    setTemplate(null);
    try {
      const path = testType === "positive" ? "/uds/automation-templates/positive" : "/uds/automation-templates/negative";
      const body =
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
      const result = await apiPost(path, body);
      setTemplate(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Automation Templates</h2>
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
      <button style={buttonStyle} onClick={generate} disabled={loading || !form.service_id}>
        {loading ? "Generating..." : "Generate Template"}
      </button>

      <ErrorBanner message={error} />

      {template && (
        <div style={{ marginTop: "1rem" }}>
          <h3>{template.title}</h3>
          <p><strong>Template ID:</strong> {template.template_id}</p>
          <p><strong>Test Case ID:</strong> {template.test_case_id}</p>
          <p>{template.objective}</p>
          <p><strong>Requires engineering review:</strong> {String(template.requires_engineering_review)}</p>
          <p><strong>Validation conditions:</strong></p>
          <ul>{template.validation_conditions.map((c, i) => <li key={i}>{c}</li>)}</ul>
          {template.source && (
            <p style={{ fontSize: "0.85rem", color: "var(--text)" }}>
              Source: {template.source.document_name} v{template.source.document_version}, chunk {template.source.chunk_id}
            </p>
          )}
          <JsonBlock data={template} />
        </div>
      )}
      {!template && !error && !loading && <EmptyState text="Generate an automation-ready template from a positive or negative test case." />}
    </div>
  );
}
