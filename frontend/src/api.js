import axios from "axios";

const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Create an instance of axios with the base URL
const api = axios.create({
  baseURL: API_URL,
});

// Export the Axios instance
export default api;
