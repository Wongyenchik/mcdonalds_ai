import React, { useEffect, useState } from "react";
import api from "../api";
import LlmSearchForm from "./LlmSearchForm";

interface LlmResponse {
  llmresponse: string;
}

const SearchPanel: React.FC = () => {
  const [llmresponse, setLlmResponse] = useState<string>("");

  const getLlmResponse = async () => {
    try {
      const response = await api.get<LlmResponse>("/llmresponses");
      setLlmResponse(response.data.llmresponse);
    } catch (error) {
      console.error("Error fetching response:", error);
    }
  };

  const addLlmResponse = async (query: string) => {
    try {
      await api.post("/llmresponses", { llmresponse: query });
      await getLlmResponse();
    } catch (error) {
      console.error("Error adding response:", error);
    }
  };

  useEffect(() => {
    getLlmResponse();
  }, []);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <LlmSearchForm addLlmResponse={addLlmResponse} />
      {llmresponse && (
        <div
          style={{
            paddingLeft: "1rem",
            paddingRight: "1rem",
            borderRadius: "8px",
          }}
        >
          {llmresponse}
        </div>
      )}
    </div>
  );
};

export default SearchPanel;
