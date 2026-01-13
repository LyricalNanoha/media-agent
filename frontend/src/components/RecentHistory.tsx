"use client";

import { useEffect, useState } from "react";
import { History, ArrowRight, CheckCircle, XCircle, RotateCcw } from "lucide-react";

interface HistoryItem {
  id: number;
  originalPath: string;
  newPath: string;
  mediaType: string;
  title: string;
  status: string;
  renamedAt: string;
}

export function RecentHistory() {
  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 获取历史记录
    fetchHistory();
  }, []);

  const fetchHistory = async () => {
    try {
      const res = await fetch("/api/history?limit=5");
      if (res.ok) {
        const data = await res.json();
        setHistory(data.history || []);
      }
    } catch (error) {
      console.error("获取历史记录失败:", error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="w-4 h-4 text-emerald-400" />;
      case "failed":
        return <XCircle className="w-4 h-4 text-red-400" />;
      case "rollback":
        return <RotateCcw className="w-4 h-4 text-yellow-400" />;
      default:
        return null;
    }
  };

  const getMediaTypeLabel = (type: string) => {
    switch (type) {
      case "movie":
        return { text: "电影", color: "bg-purple-500/20 text-purple-400" };
      case "tv":
        return { text: "电视剧", color: "bg-blue-500/20 text-blue-400" };
      default:
        return { text: "未知", color: "bg-dark-700 text-dark-400" };
    }
  };

  const formatPath = (path: string) => {
    // 只显示文件名
    return path.split("/").pop() || path;
  };

  const formatTime = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleString("zh-CN", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  return (
    <div className="glass rounded-2xl p-5 h-full">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <History className="w-5 h-5 text-primary-400" />
          最近重命名
        </h3>
        <button className="text-sm text-primary-400 hover:text-primary-300 transition-colors">
          查看全部
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="w-6 h-6 border-2 border-primary-400 border-t-transparent rounded-full animate-spin" />
        </div>
      ) : history.length === 0 ? (
        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-dark-800 flex items-center justify-center">
            <History className="w-8 h-8 text-dark-500" />
          </div>
          <p className="text-dark-400 text-sm mb-2">暂无重命名记录</p>
          <p className="text-dark-500 text-xs">
            扫描目录后，重命名的文件会显示在这里
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item) => {
            const mediaLabel = getMediaTypeLabel(item.mediaType);
            return (
              <div
                key={item.id}
                className="p-3 bg-dark-900/50 rounded-xl border border-dark-800 hover:border-dark-700 transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full ${mediaLabel.color}`}
                      >
                        {mediaLabel.text}
                      </span>
                      <span className="text-xs text-dark-500">
                        {formatTime(item.renamedAt)}
                      </span>
                    </div>
                    <div className="text-sm font-medium text-white truncate">
                      {item.title || formatPath(item.newPath)}
                    </div>
                    <div className="flex items-center gap-2 mt-2 text-xs text-dark-500">
                      <span className="truncate max-w-[120px]">
                        {formatPath(item.originalPath)}
                      </span>
                      <ArrowRight className="w-3 h-3 flex-shrink-0" />
                      <span className="truncate max-w-[120px] text-dark-400">
                        {formatPath(item.newPath)}
                      </span>
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    {getStatusIcon(item.status)}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}





