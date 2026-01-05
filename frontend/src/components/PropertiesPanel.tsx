import React, { useEffect } from 'react';
import { Form, Input, InputNumber, Select, Button, Table, Typography, Space, message, Tabs, Empty, Descriptions, Tag } from 'antd';
import { PlusOutlined, DeleteOutlined } from '@ant-design/icons';
import { BioSequence, Feature } from '../types/biolab';
import { addFeature, deleteFeature } from '../api';

const { Option } = Select;

interface PropertiesPanelProps {
  sequence: BioSequence | null;
  projectPath: string | null; // Keep for API compatibility
  selection?: { start: number; end: number; clockwise: boolean } | null;
  onUpdate: () => void;
  onFeatureClick?: (feature: Feature) => void;
}

const PropertiesPanel: React.FC<PropertiesPanelProps> = ({ sequence, projectPath, selection, onUpdate, onFeatureClick }) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (selection) {
      form.setFieldsValue({
        start: selection.start,
        end: selection.end,
        strand: selection.clockwise === false ? '-' : '+'
      });
    }
  }, [selection, form]);

  const handleAddFeature = async (values: any) => {
    if (!sequence || !projectPath) return;
    try {
      // In a real app we'd call API. For now we might just be updating local state if using the new App.tsx approach
      // But keeping API call for compatibility with backend storage
      // Note: sequence.id might be different from file name path in backend. 
      // Assuming projectPath is the folder, and sequence.id is the file name/ID.
      
      const feature = {
        ...values,
        strand: values.strand === '+' ? 1 : -1
      };
      
      await addFeature(projectPath, sequence.id, feature);
      message.success('Feature added');
      form.resetFields();
      onUpdate();
    } catch (error) {
      console.error(error);
      message.error('Failed to add feature (Backend might not support new ID structure yet)');
    }
  };

  if (!sequence) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#888' }}>
        <Empty description="No sequence selected" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  const GeneralTab = () => (
    <div style={{ padding: 16 }}>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="Name">{sequence.meta?.name || sequence.id}</Descriptions.Item>
        <Descriptions.Item label="Length">{sequence.meta?.length?.toLocaleString()} bp</Descriptions.Item>
        <Descriptions.Item label="Type">{sequence.meta?.type?.toUpperCase()}</Descriptions.Item>
        <Descriptions.Item label="Topology">{sequence.meta?.topology}</Descriptions.Item>
        {sequence.meta?.type === 'nucleotide' && (
            <Descriptions.Item label="GC Content">{sequence.meta?.gcContent}%</Descriptions.Item>
        )}
        <Descriptions.Item label="Created">{new Date(sequence.meta?.created || '').toLocaleDateString()}</Descriptions.Item>
      </Descriptions>
      <div style={{ marginTop: 16 }}>
        <Typography.Text type="secondary">Description:</Typography.Text>
        <div style={{ marginTop: 4, padding: 8, background: '#f5f5f5', borderRadius: 4, minHeight: 60 }}>
          {sequence.description || 'No description'}
        </div>
      </div>
    </div>
  );

  const AnnotationsTab = () => (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table 
          dataSource={sequence.features} 
          rowKey="id" 
          size="small" 
          pagination={false}
          onRow={(record) => ({
            onClick: () => onFeatureClick && onFeatureClick(record),
            style: { cursor: 'pointer' }
          })}
          columns={[
            { title: 'Name', dataIndex: 'label', key: 'label', render: (t, r) => <span style={{color: r.color}}>{r.name || r.type}</span> },
            { title: 'Type', dataIndex: 'type', key: 'type', render: t => <Tag>{t}</Tag> },
            { title: 'Start', dataIndex: 'start', key: 'start', width: 60 },
            { title: 'End', dataIndex: 'end', key: 'end', width: 60 },
          ]}
        />
      </div>
      <div style={{ padding: 12, borderTop: '1px solid #f0f0f0', background: '#fafafa' }}>
        <Typography.Text strong style={{ marginBottom: 8, display: 'block' }}>Add Annotation</Typography.Text>
        <Form form={form} onFinish={handleAddFeature} layout="vertical" size="small">
          <Form.Item name="label" label="Name" rules={[{ required: true }]}>
            <Input placeholder="Feature Name" />
          </Form.Item>
          <Form.Item name="type" label="Type" initialValue="misc_feature">
            <Select>
              <Option value="CDS">CDS</Option>
              <Option value="gene">Gene</Option>
              <Option value="promoter">Promoter</Option>
              <Option value="misc_feature">Misc Feature</Option>
            </Select>
          </Form.Item>
          <Space>
            <Form.Item name="start" label="Start" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 70 }} />
            </Form.Item>
            <Form.Item name="end" label="End" rules={[{ required: true }]}>
              <InputNumber min={1} style={{ width: 70 }} />
            </Form.Item>
            <Form.Item name="strand" label="Strand" initialValue="+">
              <Select style={{ width: 60 }}>
                <Option value="+">+</Option>
                <Option value="-">-</Option>
              </Select>
            </Form.Item>
          </Space>
          <Button type="primary" htmlType="submit" icon={<PlusOutlined />} block>
            Add Feature
          </Button>
        </Form>
      </div>
    </div>
  );

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <Tabs 
        defaultActiveKey="general" 
        size="small"
        tabBarStyle={{ paddingLeft: 16, marginBottom: 0 }}
        items={[
          { key: 'general', label: 'General', children: <GeneralTab /> },
          { key: 'annotations', label: `Annotations (${sequence.features?.length || 0})`, children: <AnnotationsTab /> }
        ]}
      />
    </div>
  );
};

export default PropertiesPanel;