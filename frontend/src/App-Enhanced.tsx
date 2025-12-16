import React, { useState, useCallback } from "react";
import {
  Layout,
  Menu,
  ConfigProvider,
  Empty,
  Descriptions,
  Tag,
  Dropdown,
  Modal,
  Input,
  message,
  Upload,
  Button,
  Space,
} from "antd";
import type { MenuProps } from 'antd';
import { PanelGroup, Panel, PanelResizeHandle } from "react-resizable-panels";
import { DirectoryTreeProps } from "antd/es/tree";
import DirectoryTree from "antd/es/tree/DirectoryTree";
import { 
  Folder, 
  Dna, 
  Upload as UploadIcon,
  Copy,
  Download,
  FileText,
  Scissors
} from "lucide-react";
import AdvancedSequenceEditor from "./components/AdvancedSequenceEditor";
import { parseSequenceFile, toGenbankFormat, toFastaFormat, downloadTextFile } from "./utils/fileParser";
import { v4 as uuidv4 } from 'uuid';

const { Dragger } = Upload;

// 数据模型
interface BioSequence {
  name: string;
  seq: string;
  type: "dna" | "rna" | "protein";
  circular: boolean;
  features: Array<{
    name: string;
    start: number;
    end: number;
    direction: 1 | -1;
    color?: string;
    type?: "CDS" | "promoter" | "enzyme" | "misc_feature";
  }>;
  description?: string;
}

interface FileNode {
  key: string;
  title: string;
  isFolder: boolean;
  children?: FileNode[];
  data?: BioSequence | null;
}

// 初始示例数据
const initialProjectData: FileNode[] = [
  {
    key: "0",
    title: "BioLab Projects",
    isFolder: true,
    children: [
      {
        key: "0-0",
        title: "Plasmid Library",
        isFolder: true,
        children: [
          {
            key: "0-0-0",
            title: "pFA6a-GFP(S65T)-kanMX6",
            isFolder: false,
            data: {
              name: "pFA6a-GFP(S65T)-kanMX6",
              seq: "ATGGCTAGCAAAGGAGAAGAACTTTTCACTGGAGTTGTCCCAATTCTTGTTGAATTAGATGGTGATGTTAATGGGCACAAATTTTCTGTCAGTGGAGAGGGTGAAGGTGATGCAACATACGGAAAACTTACCCTTAAATTTATTTGCACTACTGGAAAACTACCTGTTCCATGGCCAACACTTGTCACTACTTTCTCTTATGGTGTTCAATGCTTTTCCCGTTATCCGGATCATATGAAACGGCATGACTTTTTCAAGAGTGCCATGCCCGAAGGTTATGTACAGGAACGCACTATATCTTTCAAAGATGACGGGAACTACAAGACGCGTGCTGAAGTCAAGTTTGAAGGTGATACCCTTGTTAATCGTATCGAGTTAAAAGGTATTGATTTTAAAGAAGATGGAAACATTCTCGGACACAAACTCGAGTACAACTATAACTCACACAATGTATACATCACGGCAGACAAACAAAAGAATGGAATCAAAGCTAACTTCAAAATTCGCCACAACATTGAAGATGGATCCGTTCAACTAGCAGACCATTATCAACAAAATACTCCAATTGGCGATGGCCCTGTCCTTTTACCAGACAACCATTACCTGTCGACACAATCTGCCCTTTCGAAAGATCCCAACGAAAAGCGTGACCACATGGTCCTTCTTGAGTTTGTAACTGCTGCTGGGATTACACATGGCATGGATGAGCTCTACAAATAA",
              type: "dna",
              circular: true,
              features: [
                { 
                  name: "GFP(S65T)", 
                  start: 1, 
                  end: 720, 
                  direction: 1, 
                  color: "#7ed321", 
                  type: "CDS" 
                },
              ],
              description: "Yeast expression vector with GFP and kanamycin resistance"
            },
          },
        ],
      },
    ],
  },
];

const { Header, Content } = Layout;

function App() {
  const [projectData, setProjectData] = useState<FileNode[]>(initialProjectData);
  const [activeSequence, setActiveSequence] = useState<BioSequence | null>(null);
  const [contextMenu, setContextMenu] = useState<{ 
    visible: boolean; 
    x: number; 
    y: number; 
    node: FileNode | null;
  }>({ visible: false, x: 0, y: 0, node: null });
  
  const [modal, setModal] = useState<{ 
    visible: boolean; 
    type: 'newFile' | 'newFolder' | 'rename'; 
    node: FileNode | null;
  }>({ visible: false, type: 'newFile', node: null });
  
  const [inputValue, setInputValue] = useState("");
  const [uploadModalVisible, setUploadModalVisible] = useState(false);

  // 递归文件操作
  const recursiveMap = (nodes: FileNode[], callback: (node: FileNode) => FileNode | null): FileNode[] => {
    return nodes.map(node => {
      const newNode = callback(node);
      if (!newNode) return null;
      if (newNode.children) {
        newNode.children = recursiveMap(newNode.children, callback);
      }
      return newNode;
    }).filter((node): node is FileNode => node !== null);
  };

  // 拖拽上传处理
  const handleFileUpload = useCallback(async (file: File) => {
    try {
      message.loading({ content: `解析 ${file.name}...`, key: 'upload' });
      
      const sequences = await parseSequenceFile(file);
      
      if (sequences.length === 0) {
        message.error({ content: '未能从文件中解析出序列', key: 'upload' });
        return;
      }

      // 将解析的序列添加到项目树
      const newNodes: FileNode[] = sequences.map(seq => ({
        key: uuidv4(),
        title: seq.name,
        isFolder: false,
        data: {
          name: seq.name,
          seq: seq.seq,
          type: seq.type || 'dna',
          circular: seq.circular || false,
          features: (seq.features || []).map(f => ({
            name: f.name,
            start: f.start,
            end: f.end,
            direction: f.direction || 1,
            color: f.color,
            type: f.type as "CDS" | "promoter" | "enzyme" | "misc_feature" | undefined
          })),
          description: seq.description
        }
      }));

      // 添加到根目录或当前选中的文件夹
      setProjectData(oldTree => [...oldTree, ...newNodes]);
      
      message.success({ 
        content: `成功导入 ${sequences.length} 个序列`, 
        key: 'upload',
        duration: 2
      });

      // 自动选择第一个序列
      if (newNodes.length > 0 && newNodes[0].data) {
        setActiveSequence(newNodes[0].data);
      }

    } catch (error: any) {
      message.error({ 
        content: `文件解析失败: ${error.message}`, 
        key: 'upload',
        duration: 3
      });
    }
  }, []);

  // Dragger 配置
  const uploadProps = {
    name: 'file',
    multiple: true,
    accept: '.gb,.genbank,.fasta,.fa,.faa,.fna,.dna,.json',
    beforeUpload: (file: File) => {
      handleFileUpload(file);
      return false; // 阻止自动上传
    },
    showUploadList: false,
  };

  // 右键菜单项
  const getContextMenuItems = (node: FileNode | null): MenuProps['items'] => {
    if (!node) {
      return [
        {
          key: 'import',
          label: '导入序列文件',
          icon: <UploadIcon size={16} />,
          onClick: () => setUploadModalVisible(true)
        },
        {
          key: 'newFolder',
          label: '新建文件夹',
          icon: <Folder size={16} />
        }
      ];
    }

    const items: MenuProps['items'] = [];

    if (node.isFolder) {
      items.push(
        {
          key: 'newFile',
          label: '新建序列',
          icon: <Dna size={16} />
        },
        {
          key: 'newFolder',
          label: '新建子文件夹',
          icon: <Folder size={16} />
        },
        { type: 'divider' }
      );
    } else {
      items.push(
        {
          key: 'open',
          label: '打开',
          icon: <FileText size={16} />
        },
        { type: 'divider' },
        {
          key: 'export',
          label: '导出为',
          icon: <Download size={16} />,
          children: [
            { key: 'export-gb', label: 'GenBank (.gb)' },
            { key: 'export-fasta', label: 'FASTA (.fasta)' },
          ]
        },
        {
          key: 'duplicate',
          label: '复制',
          icon: <Copy size={16} />
        },
        { type: 'divider' }
      );
    }

    items.push(
      {
        key: 'rename',
        label: '重命名'
      },
      {
        key: 'delete',
        label: '删除',
        danger: true
      }
    );

    return items;
  };

  // 处理右键菜单操作
  const handleMenuClick = (key: string, node: FileNode | null) => {
    setContextMenu({ ...contextMenu, visible: false });

    switch(key) {
      case 'export-gb':
        if (node?.data) {
          const gbContent = toGenbankFormat(node.data);
          downloadTextFile(gbContent, `${node.data.name}.gb`, 'text/plain');
          message.success('已导出为 GenBank 格式');
        }
        break;
      case 'export-fasta':
        if (node?.data) {
          const fastaContent = toFastaFormat([node.data]);
          downloadTextFile(fastaContent, `${node.data.name}.fasta`, 'text/plain');
          message.success('已导出为 FASTA 格式');
        }
        break;
      case 'duplicate':
        if (node) {
          const duplicated: FileNode = {
            ...node,
            key: uuidv4(),
            title: `${node.title} (copy)`
          };
          setProjectData(oldTree => [...oldTree, duplicated]);
          message.success('序列已复制');
        }
        break;
      case 'rename':
        if (node) {
          setInputValue(node.title);
          setModal({ visible: true, type: 'rename', node });
        }
        break;
      case 'delete':
        if (node) {
          Modal.confirm({
            title: `删除 '${node.title}'?`,
            content: '此操作无法撤销',
            okText: '删除',
            okType: 'danger',
            cancelText: '取消',
            onOk: () => {
              setProjectData(oldTree => recursiveMap(oldTree, n => n.key === node.key ? null : n));
              if (activeSequence && node.data?.name === activeSequence.name) {
                setActiveSequence(null);
              }
              message.success('已删除');
            },
          });
        }
        break;
    }
  };

  // Project Explorer
  const ProjectExplorer: React.FC = () => {
    const handleSelect: DirectoryTreeProps["onSelect"] = (_, info) => {
      const node = info.node as any;
      if (!node.isLeaf && node.data) {
        setActiveSequence(node.data);
      }
    };

    const getIcon = (isFolder: boolean) => 
      isFolder ? <Folder size={18} /> : <Dna size={18} color="#00e676" />;

    const renderTreeData = (nodes: FileNode[]): any[] =>
      nodes.map((node) => ({
        ...node,
        isLeaf: !node.isFolder,
        icon: getIcon(node.isFolder),
        children: node.children ? renderTreeData(node.children) : [],
      }));

    return (
      <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
        <div style={{ 
          padding: "12px 16px", 
          color: "#fff", 
          fontWeight: 600, 
          fontSize: 16, 
          borderBottom: '1px solid #23272e',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <span>序列库</span>
          <Button 
            type="primary" 
            size="small"
            icon={<UploadIcon size={14} />}
            onClick={() => setUploadModalVisible(true)}
          >
            导入
          </Button>
        </div>
        
        {/* 拖拽上传区域 */}
        <div style={{ padding: '12px' }}>
          <Dragger {...uploadProps} style={{ background: 'transparent' }}>
            <p className="ant-upload-drag-icon">
              <UploadIcon size={32} style={{ margin: '0 auto' }} />
            </p>
            <p className="ant-upload-text" style={{ fontSize: 12 }}>
              拖拽文件到此处
            </p>
            <p className="ant-upload-hint" style={{ fontSize: 10 }}>
              支持 .gb, .fasta, .dna 等格式
            </p>
          </Dragger>
        </div>

        <div style={{flex: 1, overflowY: 'auto', padding: '0 8px'}}>
          <DirectoryTree
            style={{ background: "transparent", color: "#fff" }}
            treeData={renderTreeData(projectData)}
            showIcon
            onSelect={handleSelect}
            onRightClick={({ event, node }: any) => {
              event.preventDefault();
              setContextMenu({ 
                visible: true, 
                x: event.clientX, 
                y: event.clientY, 
                node 
              });
            }}
            defaultExpandAll
          />
        </div>
      </div>
    );
  };

  // Sequence Inspector
  const SequenceInspector: React.FC<{ sequence: BioSequence | null }> = ({ sequence }) => {
    if (!sequence) {
      return (
        <div style={{ padding: 20, color: '#888' }}>
          选择一个序列查看其属性
        </div>
      );
    }

    return (
      <div style={{ padding: "12px", color: "#fff", height: '100%', overflowY: 'auto' }}>
        <div style={{ 
          padding: "0 4px 12px 4px", 
          fontWeight: 600, 
          fontSize: 16, 
          borderBottom: '1px solid #23272e', 
          marginBottom: 12 
        }}>
          属性检查器
        </div>
        
        <Descriptions title="基本信息" bordered column={1} size="small">
          <Descriptions.Item label="名称">{sequence.name}</Descriptions.Item>
          <Descriptions.Item label="长度">{sequence.seq.length} bp</Descriptions.Item>
          <Descriptions.Item label="类型">
            {sequence.type.toUpperCase()}
          </Descriptions.Item>
          <Descriptions.Item label="拓扑">
            {sequence.circular ? "环状" : "线性"}
          </Descriptions.Item>
        </Descriptions>

        <Descriptions 
          title="注释特征" 
          bordered 
          column={1} 
          size="small" 
          style={{marginTop: 20}}
        >
          {sequence.features && sequence.features.length > 0 ? (
            sequence.features.map((ann, i) => (
              <Descriptions.Item key={i} label={ann.name}>
                {ann.start}..{ann.end} 
                <Tag color={ann.color} style={{marginLeft: 8}}>
                  {ann.type}
                </Tag>
              </Descriptions.Item>
            ))
          ) : (
            <Descriptions.Item label="无">暂无注释</Descriptions.Item>
          )}
        </Descriptions>

        {sequence.description && (
          <div style={{ marginTop: 16 }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>描述</div>
            <div style={{ 
              padding: 8, 
              background: '#2a2a2a', 
              borderRadius: 4,
              fontSize: 12,
              color: '#ccc'
            }}>
              {sequence.description}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <ConfigProvider theme={{
      token: { 
        colorBgBase: "#1f1f1f", 
        colorBgContainer: "#141414", 
        colorText: "#fff", 
        colorPrimary: "#1677ff" 
      },
      components: { 
        Layout: { headerBg: "#181a1b", bodyBg: "#1f1f1f" },
        Upload: { colorBorder: '#444' }
      }
    }}>
      <Layout style={{ minHeight: "100vh", background: "#1f1f1f" }}>
        <Header style={{ 
          height: 48, 
          background: "#181a1b", 
          display: "flex", 
          alignItems: "center", 
          padding: "0 24px", 
          borderBottom: '1px solid #23272e' 
        }}>
          <div style={{ 
            color: "#90caf9", 
            fontWeight: 700, 
            fontSize: 18, 
            marginRight: 24 
          }}>
            BioLab Workbench 
            <span style={{ 
              fontSize: 12, 
              color: '#666', 
              marginLeft: 8 
            }}>
              | Geneious-like Web Edition
            </span>
          </div>
          
          <Menu 
            mode="horizontal" 
            theme="dark" 
            style={{ 
              flex: 1, 
              background: "transparent", 
              borderBottom: "none" 
            }} 
            items={[
              { key: "file", label: "文件" },
              { key: "edit", label: "编辑" },
              { key: "tools", label: "工具" },
              { key: "help", label: "帮助" }
            ].map(k => ({ ...k }))} 
          />
        </Header>
        
        <Layout>
          <PanelGroup direction="horizontal" style={{ height: "calc(100vh - 48px)" }}>
            {/* 左侧项目浏览器 */}
            <Panel 
              defaultSize={20} 
              minSize={15} 
              maxSize={35} 
              style={{ 
                background: "#141414", 
                borderRight: "1px solid #23272e" 
              }}
            >
              <ProjectExplorer />
            </Panel>
            
            <PanelResizeHandle style={{ 
              width: 5, 
              background: "#23272e", 
              cursor: "col-resize" 
            }} />
            
            {/* 中间序列编辑器 */}
            <Panel minSize={30}>
              <Content style={{ 
                height: '100%', 
                display: 'flex', 
                flexDirection: 'column', 
                background: '#1f1f1f',
                padding: '16px'
              }}>
                {activeSequence ? (
                  <AdvancedSequenceEditor
                    sequence={activeSequence}
                    onSave={(savedSeq) => {
                      // 更新序列数据
                      setProjectData(oldTree => recursiveMap(oldTree, node => {
                        if (node.data?.name === activeSequence.name) {
                          node.data = savedSeq;
                        }
                        return node;
                      }));
                      setActiveSequence(savedSeq);
                    }}
                    height="100%"
                  />
                ) : (
                  <div style={{ 
                    flex: 1, 
                    display: "flex", 
                    alignItems: "center", 
                    justifyContent: "center" 
                  }}>
                    <Empty 
                      description="选择一个序列文件开始编辑" 
                      style={{ color: '#888' }}
                    />
                  </div>
                )}
              </Content>
            </Panel>
            
            <PanelResizeHandle style={{ 
              width: 5, 
              background: "#23272e", 
              cursor: "col-resize" 
            }} />
            
            {/* 右侧属性面板 */}
            <Panel 
              defaultSize={20} 
              minSize={15} 
              maxSize={35} 
              style={{ 
                background: "#141414", 
                borderLeft: "1px solid #23272e" 
              }}
            >
              <SequenceInspector sequence={activeSequence} />
            </Panel>
          </PanelGroup>
        </Layout>
      </Layout>

      {/* 右键菜单 */}
      <Dropdown
        menu={{ 
          items: getContextMenuItems(contextMenu.node),
          onClick: ({ key }) => handleMenuClick(key, contextMenu.node)
        }}
        open={contextMenu.visible}
        onOpenChange={(flag) => !flag && setContextMenu({ ...contextMenu, visible: false })}
      >
        <div style={{ 
          position: 'fixed', 
          top: contextMenu.y, 
          left: contextMenu.x 
        }} />
      </Dropdown>

      {/* 重命名对话框 */}
      <Modal
        title="重命名"
        open={modal.visible && modal.type === 'rename'}
        onOk={() => {
          if (modal.node && inputValue) {
            setProjectData(oldTree => recursiveMap(oldTree, n => {
              if (n.key === modal.node!.key) {
                n.title = inputValue;
                if (n.data) n.data.name = inputValue;
              }
              return n;
            }));
            setModal({ visible: false, type: 'newFile', node: null });
            setInputValue("");
            message.success('重命名成功');
          }
        }}
        onCancel={() => {
          setModal({ visible: false, type: 'newFile', node: null });
          setInputValue("");
        }}
      >
        <Input
          placeholder="输入新名称"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={() => {
            if (inputValue) {
              // 触发 OK 按钮的逻辑
              document.querySelector<HTMLButtonElement>('.ant-modal-footer .ant-btn-primary')?.click();
            }
          }}
          autoFocus
        />
      </Modal>

      {/* 上传对话框 */}
      <Modal
        title="导入序列文件"
        open={uploadModalVisible}
        onCancel={() => setUploadModalVisible(false)}
        footer={null}
        width={600}
      >
        <Dragger {...uploadProps}>
          <p className="ant-upload-drag-icon">
            <UploadIcon size={48} style={{ margin: '0 auto' }} />
          </p>
          <p className="ant-upload-text">
            点击或拖拽文件到此区域上传
          </p>
          <p className="ant-upload-hint">
            支持 GenBank (.gb), FASTA (.fasta), SnapGene (.dna) 等格式
            <br />
            支持批量上传多个文件
          </p>
        </Dragger>
      </Modal>
    </ConfigProvider>
  );
}

export default App;