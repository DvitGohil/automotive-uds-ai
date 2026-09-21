import { useState } from "react";
import { apiGet } from "../api";
import { buttonStyle, EmptyState, ErrorBanner, Field, inputStyle, JsonBlock } from "./common";

export default function UdsKnowledgePanel() {
  const [documentVersionId, setDocumentVersionId] = useState("");
  const [unitType, setUnitType] = useState("service");
  const [identifier, setIdentifier] = useState("");
  const [entity, setEntity] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const lookup = async () => {
    setLoading(true);
    setError(null);
    setEntity(null);
    try {
      const result = await apiGet(`/uds/knowledge/${documentVersionId}/${unitType}/${identifier}`);
      setEntity(result);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>UDS Knowledge</h2>
      <p style={{ color: "var(--text)" }}>
        Look up a structured UDS knowledge entity (service, subfunction, DID, RID, NRC) by its document
        version and identifier, as extracted from an approved source document.
      </p>
      <Field label="Document Version ID">
        <input style={inputStyle} value={documentVersionId} onChange={(e) => setDocumentVersionId(e.target.value)} />
      </Field>
      <Field label="Entity Type">
        <select style={inputStyle} value={unitType} onChange={(e) => setUnitType(e.target.value)}>
          <option value="service">Service</option>
          <option value="did">DID</option>
          <option value="rid">RID</option>
          <option value="nrc">NRC</option>
        </select>
      </Field>
      <Field label="Identifier (e.g. 0x22, 0xF190)">
        <input style={inputStyle} value={identifier} onChange={(e) => setIdentifier(e.target.value)} />
      </Field>
      <button style={buttonStyle} onClick={lookup} disabled={loading || !documentVersionId || !identifier}>
        {loading ? "Looking up..." : "Look up"}
      </button>

      <ErrorBanner message={error} />

      {entity && (
        <div style={{ marginTop: "1rem" }}>
          <h3>{entity.service_name || entity.name || entity.nrc_name || identifier}</h3>
          {entity.source && (
            <p style={{ fontSize: "0.85rem", color: "var(--text)" }}>
              Source: {entity.source.document_name} v{entity.source.document_version}, page{" "}
              {entity.source.page_number}, section {entity.source.section_title}, chunk {entity.source.chunk_id}
            </p>
          )}
          <JsonBlock data={entity} />
        </div>
      )}
      {!entity && !error && !loading && <EmptyState text="Enter a document version, type, and identifier to look up." />}
    </div>
  );
}
