"use client";

import { useRouter } from "next/navigation";

export default function PersonSelect({
  options,
  value,
}: {
  options: { value: string; label: string; href: string }[];
  value: string;
}) {
  const router = useRouter();
  return (
    <select
      className="select"
      value={value}
      aria-label="Person"
      onChange={(e) => router.push(options.find((o) => o.value === e.target.value)?.href ?? "/tasks")}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
