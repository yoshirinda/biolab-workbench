
import React, { useState } from "react";
import { Layout, Menu, theme, ConfigProvider, Empty, Breadcrumb } from "antd";
import { PanelGroup, Panel, PanelResizeHandle } from "react-resizable-panels";
import { DirectoryTreeProps, TreeDataNode } from "antd/es/tree";
import DirectoryTree from "antd/es/tree/DirectoryTree";
import { Folder, FileText, Dna, Activity } from "lucide-react";
import BioSequenceViewer from "./components/BioSequenceViewer";

// 文件节点类型
type FileNodeType = "folder" | "gb" | "fasta" | "ab1";
interface FileNode extends TreeDataNode {
  type: FileNodeType;
  seq?: string;
  annotations?: any[];
}

// 简洁模拟数据
const projectTree: FileNode[] = [
  {
    key: "0",
    title: "My Database",
    type: "folder",
    children: [
      {
        key: "0-0",
        title: "Cloning Project 2025",
        type: "folder",
        children: [
          {
            key: "0-0-0",
            title: "pBR322.gb",
            type: "gb",
            isLeaf: true,
            seq: "AGCTTTCATTCTGACTGCAACGGGCAATATGTC",
            annotations: [
              { name: "AmpR", start: 2, end: 20, color: "#ff9800" }
            ]
          },
          {
            key: "0-0-1",
            title: "GFP.fasta",
            type: "fasta",
            isLeaf: true,
            seq: "ATGGTGAGCAAGGGCGAGGAGCTGTTCACCGG",
            annotations: [
              { name: "GFP", start: 1, end: 15, color: "#00e676" }
            ]
          },
          {
            key: "0-0-2",
            title: "Sample1.ab1",
            type: "ab1",
            isLeaf: true
          }
        ]
      },
      {
        key: "0-1",
        title: "Reference Sequences",
        type: "folder",
        children: [
          {
            key: "0-1-0",
            title: "lambda.gb",
            type: "gb",
            isLeaf: true,
            seq: "GGGAATTCGCGGCCGCTTCTAGAGGATCCCCG",
            annotations: []
          }
        ]
      }
    ]
  }
];

// 文件类型图标
const getIcon = (type: FileNodeType) => {
  switch (type) {
    case "folder": return <Folder size={18} />;
    case "gb": return <Dna size={18} color="#ff9800" />;
    case "fasta": return <FileText size={18} color="#00e676" />;
    case "ab1": return <Activity size={18} color="#90caf9" />;
    default: return <FileText size={18} />;
  }
};

const darkTheme = {
  token: {
    colorBgBase: "#1f1f1f",
    colorBgContainer: "#141414",
    colorText: "#fff",
    colorPrimary: "#1677ff"
  },
  components: {
    Layout: {
      headerBg: "#181a1b",
      siderBg: "#141414",
      bodyBg: "#1f1f1f"
    }
  }
};

const { Header, Sider, Content } = Layout;

function App() {
  const [selectedFile, setSelectedFile] = useState<FileNode | null>(null);

  // 递归查找文件节点
  const findFileNode = (key: string, nodes: FileNode[]): FileNode | null => {
    for (const node of nodes) {
      if (node.key === key) return node;
      if (node.children) {
        const found = findFileNode(key, node.children as FileNode[]);
        if (found) return found;
      }
    }
    return null;
  };

  // antd Tree onSelect
  const handleSelect: DirectoryTreeProps["onSelect"] = (keys, info) => {
    if (info.node.isLeaf) {
      setSelectedFile(findFileNode(info.node.key as string, projectTree));
    }
  };

  // 生成面包屑
  const getBreadcrumb = (node: FileNode | null): string[] => {
    if (!node) return [];
    const path: string[] = [node.title];
    let parentKey = node.key.split("-").slice(0, -1).join("-");
    let parent = parentKey ? findFileNode(parentKey, projectTree) : null;
    while (parent) {
      path.unshift(parent.title);
      parentKey = parent.key.split("-").slice(0, -1).join("-");
      parent = parentKey ? findFileNode(parentKey, projectTree) : null;
    }
    return path;
  };

  return (
    <ConfigProvider theme={darkTheme}>
      <Layout style={{ minHeight: "100vh", background: "#1f1f1f" }}>
        <Header style={{ height: 48, background: "#181a1b", display: "flex", alignItems: "center", padding: 0 }}>
          <Menu
            mode="horizontal"
            theme="dark"
            style={{ flex: 1, background: "#181a1b", borderBottom: "none" }}
            items={["File", "Edit", "View", "Tools"].map((k) => ({ key: k, label: k }))}
          />
          <div style={{ color: "#90caf9", fontWeight: 700, fontSize: 18, padding: "0 24px" }}>BioLab Workbench</div>
        </Header>
        <Layout>
          <PanelGroup direction="horizontal" style={{ height: "calc(100vh - 48px)" }}>
            <Panel defaultSize={22} minSize={15} maxSize={40} style={{ background: "#141414", borderRight: "1px solid #23272e", display: "flex", flexDirection: "column" }}>
              <div style={{ padding: 12, color: "#fff", fontWeight: 600, fontSize: 16 }}>Project Explorer</div>
              <DirectoryTree
                style={{ background: "#141414", color: "#fff", flex: 1, padding: "0 8px" }}
                treeData={projectTree.map((n) => ({ ...n, icon: getIcon(n.type) }))}
                showIcon
                onSelect={handleSelect}
                defaultExpandAll
              />
            </Panel>
            <PanelResizeHandle style={{ width: 5, background: "#23272e", cursor: "col-resize", transition: "background 0.2s" }} />
            <Panel minSize={40} style={{ background: "#1f1f1f", display: "flex", flexDirection: "column" }}>
              <div style={{ height: 44, display: "flex", alignItems: "center", borderBottom: "1px solid #23272e", padding: "0 20px", background: "#191b1e" }}>
                {selectedFile ? (
                  <Breadcrumb style={{ color: "#fff" }} separator=">">
                    {getBreadcrumb(selectedFile).map((t, i) => (
                      <Breadcrumb.Item key={i}>{t}</Breadcrumb.Item>
                    ))}
                  </Breadcrumb>
                  ) : (
                  <span style={{ color: "#888" }}>No file selected</span>
                )}
              </div>
              <div style={{ flex: 1, minHeight: 0, minWidth: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
                {selectedFile && (selectedFile.type === "gb" || selectedFile.type === "fasta") ? (
                  <div style={{ flex: 1, minHeight: 0, minWidth: 0, display: "flex", flexDirection: "column" }}>
                    <div style={{ color: "#90caf9", fontWeight: 500, fontSize: 16, margin: "12px 0 0 20px" }}>
                      {selectedFile.title} - {selectedFile.seq?.length || 0} bp
                    </div>
                    <div style={{ flex: 1, minHeight: 0, minWidth: 0, margin: 12, background: "#181a1b", borderRadius: 8, boxShadow: "0 2px 8px #0002", padding: 8, overflow: "hidden" }}>
                      <BioSequenceViewer
                        name={selectedFile.title}
                        seq={selectedFile.seq || ""}
                        annotations={selectedFile.annotations || []}
                      />
                    </div>
                  </div>
                ) : (
                  <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
                    <Empty description="Select a sequence to start" style={{ color: "#bbb" }} />
                  </div>
                )}
              </div>
            </Panel>
          </PanelGroup>
        </Layout>
      </Layout>
    </ConfigProvider>
  );
}

export default App;
