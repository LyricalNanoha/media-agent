"use client";

import { HardDrive, Plus, CheckCircle, XCircle } from "lucide-react";

interface Connection {
  id: number;
  name: string;
  url: string;
  type: string;
  isActive: boolean;
}

interface ConnectionStatusProps {
  connections: Connection[];
}

export function ConnectionStatus({ connections }: ConnectionStatusProps) {
  return (
    <div className="glass rounded-2xl p-5 h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <HardDrive className="w-5 h-5 text-primary-400" />
          WebDAV连接
        </h3>
        <button className="p-2 hover:bg-dark-800 rounded-lg transition-colors">
          <Plus className="w-4 h-4 text-dark-400" />
        </button>
      </div>

      {connections.length === 0 ? (
        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-dark-800 flex items-center justify-center">
            <HardDrive className="w-8 h-8 text-dark-500" />
          </div>
          <p className="text-dark-400 text-sm mb-2">暂无连接</p>
          <p className="text-dark-500 text-xs">
            在对话框中告诉我你的WebDAV服务器信息
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {connections.map((conn) => (
            <div
              key={conn.id}
              className="p-3 bg-dark-900/50 rounded-xl border border-dark-800 hover:border-dark-700 transition-colors"
            >
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium text-white text-sm">
                    {conn.name}
                  </div>
                  <div className="text-xs text-dark-500 mt-1 truncate max-w-[180px]">
                    {conn.url}
                  </div>
                </div>
                {conn.isActive ? (
                  <CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                ) : (
                  <XCircle className="w-4 h-4 text-red-400 flex-shrink-0" />
                )}
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-dark-800 text-dark-400">
                  {conn.type}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}





