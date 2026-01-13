"use client";

import { ReactNode } from "react";

interface StatsCardProps {
  icon: ReactNode;
  label: string;
  value: number;
  color: "blue" | "purple" | "green" | "orange";
}

const colorMap = {
  blue: {
    bg: "bg-blue-500/10",
    text: "text-blue-400",
    border: "border-blue-500/20",
  },
  purple: {
    bg: "bg-purple-500/10",
    text: "text-purple-400",
    border: "border-purple-500/20",
  },
  green: {
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
    border: "border-emerald-500/20",
  },
  orange: {
    bg: "bg-primary-500/10",
    text: "text-primary-400",
    border: "border-primary-500/20",
  },
};

export function StatsCard({ icon, label, value, color }: StatsCardProps) {
  const colors = colorMap[color];

  return (
    <div
      className={`
        glass rounded-2xl p-5 border ${colors.border}
        hover:scale-[1.02] transition-transform duration-200
      `}
    >
      <div className="flex items-center gap-4">
        <div className={`p-3 rounded-xl ${colors.bg} ${colors.text}`}>
          {icon}
        </div>
        <div>
          <div className="text-2xl font-bold text-white">
            {value.toLocaleString()}
          </div>
          <div className="text-sm text-dark-400">{label}</div>
        </div>
      </div>
    </div>
  );
}





