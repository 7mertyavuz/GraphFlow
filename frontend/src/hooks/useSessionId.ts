"use client";

import { useEffect, useState } from "react";

function generateUUID(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === "x" ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export function useSessionId(): string {
  const [sessionId, setSessionId] = useState<string>("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const key = "gf-session-id";
    let id = window.localStorage.getItem(key);
    if (!id) {
      id = generateUUID();
      window.localStorage.setItem(key, id);
    }
    setSessionId(id);
  }, []);

  return sessionId;
}

export function getStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("gf-session-id");
}
