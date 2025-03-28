import React from "react";
import Map from "./components/Map";
import SearchPanel from "./components/SearchPanel";
import "./App.css";

function App() {
  return (
    <div className="App">
      <div className="left-panel">
        <header className="App-header">
          <h1>McDonald's Outlets in Kuala Lumpur</h1>
        </header>
        <SearchPanel />
      </div>
      <div className="right-panel">
        <Map />
      </div>
    </div>
  );
}

export default App;
