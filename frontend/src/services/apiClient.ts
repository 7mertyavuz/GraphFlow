"use client";

import axios from "axios";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const sessionId = window.localStorage.getItem("gf-session-id");
    if (sessionId) {
      config.headers["X-Session-Id"] = sessionId;
    }
  }
  return config;
});
