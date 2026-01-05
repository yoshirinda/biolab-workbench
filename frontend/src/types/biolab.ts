// 核心数据模型 (TypeScript Schema)

export interface Feature {
  id: string;
  name: string;
  type: 'CDS' | 'Promoter' | 'Gene' | 'Misc' | 'Enzyme' | 'Region' | string;
  start: number; // 1-based usually, but SeqViz uses 0-based. We will stick to 1-based in model, convert for view.
  end: number;
  strand: 1 | -1; // 1: Forward, -1: Reverse
  color?: string;
  notes?: Record<string, any>;
}

export interface BioSequence {
  meta: {
    name: string;
    length: number;
    created: string; // ISO date string
    topology: 'linear' | 'circular';
    gcContent?: number; // 需计算
    type: 'nucleotide' | 'protein';
  };
  seq: string; // 纯 DNA 序列字符串
  features: Feature[];
  description?: string;
  id: string; // Internal ID
}

export interface FileNode {
  key: string;
  title: string;
  isFolder: boolean;
  parentId: string | null;
  data?: BioSequence | null; // 仅文件节点持有数据
  children?: FileNode[];
}

export interface ClipboardState {
  node: FileNode | null; // 当前复制的节点数据
  operation: 'copy' | 'cut' | null;
}

export interface ApiResult<T> {
  success: boolean;
  data?: T;
  message?: string;
}