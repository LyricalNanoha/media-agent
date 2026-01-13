/* tslint:disable */
/* eslint-disable */
/**
/* This file was automatically generated from pydantic models by running pydantic2ts.
/* Do not modify it by hand - just update the pydantic models and then re-run the script
*/

/**
 * 媒体类型
 */
export type MediaType = "tv" | "movie";
/**
 * 子分类
 */
export type SubCategory = "animation" | "documentary" | "music" | "variety" | "default";

/**
 * 分类结果
 */
export interface Classification {
  /**
   * TMDB ID
   */
  tmdb_id: number;
  /**
   * 系列名称
   */
  name: string;
  type: MediaType;
  /**
   * 年份
   */
  year?: number | null;
  /**
   * TMDB Genres
   */
  genres?: string[];
  sub_category?: SubCategory;
  /**
   * TV 季数据
   */
  seasons?: {
    [k: string]: ClassifiedFile[];
  };
  /**
   * 电影文件列表
   */
  files?: ClassifiedFile[];
}
/**
 * 已分类的文件
 */
export interface ClassifiedFile {
  /**
   * 原始路径
   */
  path: string;
  /**
   * 文件名
   */
  name: string;
  /**
   * 集数（TMDB episode_number）
   */
  episode: number;
  /**
   * 季数
   */
  season: number;
  /**
   * 关联的字幕文件
   */
  subtitles?: SubtitleFile[];
}
/**
 * 字幕文件
 */
export interface SubtitleFile {
  /**
   * 原始路径
   */
  path: string;
  /**
   * 文件名
   */
  name: string;
  /**
   * 字幕语言: chs, cht, eng, jpn
   */
  language: string;
}
/**
 * 单个分类结果项（前端显示）
 */
export interface ClassificationResultItem {
  /**
   * 媒体名称
   */
  name: string;
  /**
   * 文件数量
   */
  file_count: number;
  /**
   * 剧集范围，如 E01-E220
   */
  ep_range?: string;
  /**
   * 媒体类型
   */
  type: "tv" | "movie";
}
/**
 * 分类配置（Agent 生成）
 */
export interface ClassifyConfig {
  /**
   * 分类项列表
   */
  items: ClassifyItem[];
}
/**
 * 单个分类项
 */
export interface ClassifyItem {
  /**
   * TMDB ID
   */
  tmdb_id: number;
  type: MediaType;
  /**
   * 系列名称
   */
  name: string;
  /**
   * 分类规则列表
   */
  rules: ClassifyRule[];
}
/**
 * 分类规则
 */
export interface ClassifyRule {
  match: MatchRule;
  /**
   * 固定季号
   */
  season?: number | null;
  /**
   * 自动分季（根据 TMDB）
   */
  auto_season?: boolean;
  /**
   * 集数偏移（续作重编号）
   */
  episode_offset?: number;
}
/**
 * 匹配条件
 */
export interface MatchRule {
  /**
   * 目录名包含
   */
  directory?: string | null;
  /**
   * 文件名包含
   */
  filename?: string | null;
  /**
   * 集数范围 [start, end]
   */
  episode_range?: number[] | null;
  /**
   * 文件大于 X MB
   */
  size_mb_greater?: number | null;
}
/**
 * 当前工具状态（前端显示）
 */
export interface CurrentToolOutput {
  /**
   * 工具名称
   */
  name?: string;
  /**
   * 执行状态
   */
  status?: "idle" | "executing" | "complete" | "error";
  /**
   * 工具描述
   */
  description?: string;
  /**
   * 执行进度
   */
  progress?: ToolProgressOutput | null;
}
/**
 * 工具执行进度（前端显示）
 */
export interface ToolProgressOutput {
  /**
   * 当前进度
   */
  current?: number;
  /**
   * 总数
   */
  total?: number;
  /**
   * 进度消息
   */
  message?: string;
  /**
   * 百分比 0-100
   */
  percentage?: number;
}
/**
 * 匹配规则
 */
export interface MatchRule1 {
  /**
   * 目录名包含
   */
  directory?: string | null;
  /**
   * 文件名包含
   */
  filename?: string | null;
  /**
   * 集数范围 [start, end]
   */
  episode_range?: number[] | null;
  /**
   * 文件大于 X MB
   */
  size_mb_greater?: number | null;
}
/**
 * 扫描结果摘要（前端显示）
 */
export interface ScanResultOutput {
  /**
   * 总文件数
   */
  total_files?: number;
  /**
   * 视频文件数
   */
  video_count?: number;
  /**
   * 字幕文件数
   */
  subtitle_count?: number;
  /**
   * 示例文件名（前10个）
   */
  sample_files?: string[];
}
/**
 * 扫描到的文件
 */
export interface ScannedFile {
  /**
   * 文件名
   */
  name: string;
  /**
   * 完整路径
   */
  path: string;
  /**
   * 文件类型: video | subtitle
   */
  type: string;
  /**
   * 文件大小（字节）
   */
  size: number;
  /**
   * 所在目录
   */
  directory: string;
  /**
   * 提取的集数
   */
  episode?: number | null;
  /**
   * 字幕语言: chs, cht, eng, jpn
   */
  language?: string | null;
  /**
   * 关联的视频文件路径
   */
  video_ref?: string | null;
}
/**
 * 存储连接配置（前端显示）
 */
export interface StorageConfigOutput {
  /**
   * 存储 URL
   */
  url?: string;
  /**
   * 用户名
   */
  username?: string;
  /**
   * 存储类型: alist | webdav
   */
  type?: string;
  /**
   * 扫描路径
   */
  scan_path?: string;
  /**
   * 目标路径
   */
  target_path?: string;
  /**
   * 是否已连接
   */
  connected?: boolean;
}
/**
 * 用户配置（Chat 过程中收集）
 *
 * 注意：路径配置已移到各自的 storage_config/strm_target_config 中：
 * - storage_config.target_path: 传统整理的目标路径
 * - strm_target_config.target_path: STRM 输出路径
 */
export interface UserConfig {
  /**
   * 扫描延迟（秒）
   */
  scan_delay?: number;
  /**
   * 上传延迟（秒）
   */
  upload_delay?: number;
  /**
   * 命名语言: zh | en
   */
  naming_language?: string;
  /**
   * 是否使用复制模式
   */
  use_copy?: boolean;
}
