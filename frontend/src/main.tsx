import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

console.log("React App Starting...");

const rootElement = document.getElementById("root");
if (!rootElement) {
    console.error("Root element not found!");
} else {
    console.log("Root element found, mounting...");
    ReactDOM.createRoot(rootElement).render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    );
    console.log("Mount command sent.");
}
