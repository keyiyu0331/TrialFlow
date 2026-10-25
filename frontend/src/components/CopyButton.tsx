"use client";

import { useState } from "react";

export default function CopyButton({ text, label = "Copy message" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      setTimeout(() => setDone(false), 1800);
    } catch {
      window.prompt("Copy this message:", text);
    }
  }
  return (
    <button className="btn" onClick={copy}>
      {done ? "Copied ✓" : label}
    </button>
  );
}
