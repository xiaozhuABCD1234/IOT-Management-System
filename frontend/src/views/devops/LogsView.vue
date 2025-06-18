<template>
  <div class="logs-container">
    <h2>MQTT 日志管理</h2>
    <div class="logs-controls">
      <el-button type="primary" @click="startListening" :disabled="isListening || !isMqttLoaded">开始监听</el-button>
      <el-button type="danger" @click="stopListening" :disabled="!isListening">停止监听</el-button>
      <el-button type="warning" @click="clearLogs">清空日志</el-button>
    </div>
    <div class="mqtt-topic-selector">
      <el-input v-model="mqttTopic" placeholder="MQTT主题 (例如: device/+/data)" class="topic-input">
        <template #prepend>主题</template>
      </el-input>
    </div>
    <div v-if="!isMqttLoaded" class="mqtt-loading-message">
      <el-alert
        title="正在加载MQTT库..."
        type="info"
        :closable="false"
        show-icon
      />
    </div>
    <div class="logs-display">
      <el-card class="log-card" shadow="hover">
        <template #header>
          <div class="card-header">
            <span>实时MQTT日志</span>
            <span class="status" :class="{ 'connected': isListening }">
              {{ isListening ? '已连接' : '未连接' }}
            </span>
          </div>
        </template>
        <div class="logs-content">
          <div v-if="logs.length === 0" class="no-logs">
            暂无日志数据，请开始监听MQTT
          </div>
          <div v-else class="log-entries" ref="logContainer">
            <div v-for="(log, index) in logs" :key="index" class="log-entry">
              <div class="log-time">{{ log.time }}</div>
              <div class="log-topic">{{ log.topic }}</div>
              <div class="log-message">
                <pre>{{ formatMessage(log.message) }}</pre>
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue';
import { useConfigStore } from '@/stores/config';

// 定义日志条目接口
interface LogEntry {
  time: string;
  topic: string;
  message: string;
}

const configStore = useConfigStore();
const logs = ref<LogEntry[]>([]);
const isListening = ref(false);
const isMqttLoaded = ref(false);
const mqttTopic = ref('device/#');
const logContainer = ref<HTMLElement | null>(null);
const client = ref<any>(null);

const formatMessage = (message: string) => {
  try {
    // 尝试格式化JSON
    const parsed = JSON.parse(message);
    return JSON.stringify(parsed, null, 2);
  } catch (e) {
    // 如果不是JSON，直接返回原始消息
    return message;
  }
};

const addLog = (topic: string, message: string) => {
  const now = new Date();
  const timeString = `${now.toLocaleDateString()} ${now.toLocaleTimeString()}`;
  
  logs.value.push({
    time: timeString,
    topic,
    message
  });
  
  // 限制日志数量，防止内存占用过大
  if (logs.value.length > 200) {
    logs.value = logs.value.slice(-200);
  }
  
  // 自动滚动到底部
  nextTick(() => {
    if (logContainer.value) {
      logContainer.value.scrollTop = logContainer.value.scrollHeight;
    }
  });
};

const startListening = () => {
  if (isListening.value || !isMqttLoaded.value) return;
  
  try {
    // 使用全局变量方式访问MQTT
    const mqtt = (window as any).mqtt;
    
    if (!mqtt || typeof mqtt.connect !== 'function') {
      throw new Error('MQTT库未正确加载，请刷新页面重试');
    }
    
    const brokerUrl = 'ws://106.14.209.20:8083/mqtt';
    
    client.value = mqtt.connect(brokerUrl, {
      clientId: `mqtt_logs_${Math.random().toString(16).substr(2, 8)}`,
      clean: true
    });
    
    client.value.on('connect', () => {
      isListening.value = true;
      client.value?.subscribe(mqttTopic.value);
      addLog('system', '已连接到MQTT服务器');
    });
    
    client.value.on('message', (topic: string, message: Buffer) => {
      addLog(topic, message.toString());
    });
    
    client.value.on('error', (err: Error) => {
      addLog('system', `MQTT错误: ${err.message}`);
      stopListening();
    });
    
  } catch (error: any) {
    console.error('MQTT连接失败:', error);
    addLog('system', `MQTT连接失败: ${error.message}`);
  }
};

// 加载MQTT脚本
onMounted(() => {
  const script = document.createElement('script');
  script.src = 'https://unpkg.com/mqtt/dist/mqtt.min.js';
  script.async = true;
  script.onload = () => {
    console.log('MQTT库加载成功');
    isMqttLoaded.value = true;
  };
  script.onerror = () => {
    console.error('MQTT库加载失败');
    addLog('system', 'MQTT库加载失败，请刷新页面重试');
  };
  document.body.appendChild(script);
});

const stopListening = () => {
  if (client.value && client.value.connected) {
    client.value.end();
    addLog('system', 'MQTT连接已断开');
  }
  isListening.value = false;
  client.value = null;
};

const clearLogs = () => {
  logs.value = [];
};

// 监听主题变化，重新订阅
watch(mqttTopic, (newTopic) => {
  if (isListening.value && client.value && client.value.connected) {
    client.value.unsubscribe(mqttTopic.value);
    client.value.subscribe(newTopic);
    addLog('system', `已更改订阅主题为: ${newTopic}`);
  }
});

// 组件卸载时断开连接
onUnmounted(() => {
  stopListening();
});
</script>

<style scoped>
.logs-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.logs-controls {
  margin-bottom: 15px;
  display: flex;
  gap: 10px;
}

.mqtt-topic-selector {
  margin-bottom: 15px;
}

.mqtt-loading-message {
  margin-bottom: 15px;
}

.topic-input {
  width: 400px;
}

.logs-display {
  flex: 1;
  overflow: hidden;
}

.log-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.status {
  font-size: 0.9em;
  padding: 2px 8px;
  border-radius: 4px;
  background-color: #f56c6c;
  color: white;
}

.status.connected {
  background-color: #67c23a;
}

.logs-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.no-logs {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
  font-style: italic;
}

.log-entries {
  overflow-y: auto;
  height: 100%;
  padding-right: 5px;
}

.log-entry {
  margin-bottom: 10px;
  padding: 8px;
  border-radius: 4px;
  background-color: #f8f8f8;
  border-left: 3px solid #409eff;
}

.log-time {
  font-size: 0.8em;
  color: #606266;
  margin-bottom: 5px;
}

.log-topic {
  font-weight: bold;
  margin-bottom: 5px;
  color: #409eff;
}

.log-message {
  white-space: pre-wrap;
  word-break: break-word;
  background-color: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-family: monospace;
  max-height: 300px;
  overflow-y: auto;
}

pre {
  margin: 0;
}
</style> 