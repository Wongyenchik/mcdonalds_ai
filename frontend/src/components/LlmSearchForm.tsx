import React, { useState } from "react";

interface LlmSearchFormProps {
  addLlmResponse: (response: string) => void;
}

const LlmSearchForm: React.FC<LlmSearchFormProps> = ({ addLlmResponse }) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (searchQuery) {
      setIsLoading(true);
      try {
        await addLlmResponse(searchQuery);
        setSearchQuery("");
      } catch (error) {
        console.error("Error submitting query:", error);
      } finally {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="search-panel">
      <div className="search-container">
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Ask about McDonald's outlets..."
            className="search-input"
          />
          <button
            type="submit"
            className="search-button"
            disabled={isLoading}
            style={{
              width: "40px",
              height: "40px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              backgroundColor: "#da291c",
              border: "none",
              borderRadius: "50%",
              cursor: "pointer",
              padding: 0,
            }}
          >
            {isLoading ? (
              <div
                style={{
                  width: "24px",
                  height: "24px",
                  border: "3px solid #f3f3f3",
                  borderTop: "3px solid #da291c",
                  borderRadius: "50%",
                  animation: "spin 1s linear infinite",
                }}
              />
            ) : (
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="white"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            )}
          </button>
        </form>
      </div>
      <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default LlmSearchForm;
