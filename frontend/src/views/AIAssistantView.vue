<template>
  <div class="ai-assistant-container">
    <div class="chat-header">
      <h2>AI 助手 <span class="powered-by">(Powered by DeepSeek)</span></h2>
      <div class="api-notice">
        <el-alert
          title="使用后端代理转发请求到DeepSeek API，请确保后端服务已启动。"
          type="info"
          :closable="false"
          show-icon
        />
      </div>
      
      <!-- 模型选择 -->
      <div class="model-selector">
        <span class="model-label">选择模型:</span>
        <el-select v-model="selectedModel" size="small" style="width: 200px">
          <el-option label="DeepSeek R1" value="deepseek-r1" />
          <el-option label="DeepSeek R1 Lite" value="deepseek-r1-lite" />
        </el-select>
        <span class="model-description">{{ modelDescription }}</span>
      </div>
    </div>
    
    <div class="chat-container" ref="chatContainerRef">
      <div v-if="messages.length === 0" class="empty-chat">
        <el-empty description="开始一段新的对话">
          <div class="model-info">
            <h3>当前使用模型: {{ selectedModel }}</h3>
            <p>{{ modelDescription }}</p>
          </div>
          <el-button type="primary" @click="focusInput">开始聊天</el-button>
        </el-empty>
      </div>
      
      <div v-else class="messages-container">
        <div 
          v-for="(message, index) in messages" 
          :key="index" 
          :class="['message', message.role === 'user' ? 'user-message' : 'assistant-message']"
        >
          <div class="message-avatar">
            <el-avatar :icon="message.role === 'user' ? 'UserFilled' : 'Service'" :size="36" />
          </div>
          <div class="message-content">
            <div class="message-role">{{ message.role === 'user' ? '你' : 'AI 助手' }}</div>
            <div class="message-text" v-html="formatMessage(message.content)"></div>
            <div v-if="message.role === 'assistant'" class="message-actions">
              <el-button type="text" size="small" @click="copyToClipboard(message.content)">
                复制
              </el-button>
            </div>
          </div>
        </div>
        
        <div v-if="isLoading" class="loading-message">
          <div class="message-avatar">
            <el-avatar icon="Service" :size="36" />
          </div>
          <div class="message-content">
            <div class="message-role">AI 助手</div>
            <div class="message-text">
              <el-skeleton :rows="3" animated />
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <div class="chat-input">
      <el-input
        v-model="userInput"
        type="textarea"
        :rows="3"
        placeholder="输入您的问题..."
        resize="none"
        @keydown.enter.prevent="sendMessage"
        ref="inputRef"
      />
      <div class="input-actions">
        <el-button 
          type="primary" 
          :disabled="!userInput.trim() || isLoading" 
          @click="sendMessage"
        >
          发送
        </el-button>
        <el-button 
          type="info" 
          @click="clearChat"
          :disabled="messages.length === 0 || isLoading"
        >
          清空对话
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import axios from 'axios';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { useAuthStore } from '@/stores/auth';

// DeepSeek API 配置
const DEEPSEEK_API_KEY = 'sk-bec0a15f8ede4672a6869bc4b1e4e9c5';
const DEEPSEEK_API_URL = 'https://api.deepseek.com/v1/chat/completions';
// 后端代理URL
const PROXY_API_URL = import.meta.env.VITE_API_BASE_URL + '/api/utils/proxy/deepseek';

// 获取认证信息
const authStore = useAuthStore();

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

const messages = ref<Message[]>([]);
const userInput = ref('');
const isLoading = ref(false);
const chatContainerRef = ref<HTMLElement | null>(null);
const inputRef = ref<HTMLElement | null>(null);
const selectedModel = ref('deepseek-r1');

// 模型描述
const modelDescription = computed(() => {
  switch (selectedModel.value) {
    case 'deepseek-r1':
      return 'DeepSeek R1是一个强大的推理模型，擅长逻辑思维和复杂问题解决';
    case 'deepseek-r1-lite':
      return 'DeepSeek R1 Lite是R1的轻量版本，响应更快，适合一般对话场景';
    default:
      return '选择一个模型开始对话';
  }
});

// 格式化消息，支持Markdown
const formatMessage = (content: string): string => {
  const html = marked.parse(content) as string;
  return DOMPurify.sanitize(html);
};

// 发送消息到DeepSeek API
const sendMessage = async () => {
  const input = userInput.value.trim();
  if (!input || isLoading.value) return;
  
  // 添加用户消息
  messages.value.push({ role: 'user', content: input });
  userInput.value = '';
  isLoading.value = true;
  
  // 自动滚动到底部
  await nextTick();
  scrollToBottom();
  
  const requestData = {
    model: selectedModel.value,
    messages: [
      {
        role: 'system',
        content: '你是一个专业、友善、乐于助人的AI助手，提供准确、有用的回答。'
      },
      ...messages.value.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    ],
    temperature: 0.7,
    max_tokens: 2000,
  };
  
  try {
    // 尝试使用后端代理发送请求
    const response = await axios.post(
      PROXY_API_URL,
      requestData,
      {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authStore.accessToken}`
        }
      }
    );
    
    // 添加AI响应
    if (response.data && response.data.choices && response.data.choices.length > 0) {
      const assistantMessage = response.data.choices[0].message.content;
      messages.value.push({ role: 'assistant', content: assistantMessage });
    } else {
      messages.value.push({ role: 'assistant', content: '抱歉，我无法生成回复。请重试。' });
    }
    
    // 自动滚动到底部
    await nextTick();
    scrollToBottom();
    
  } catch (error) {
    console.error('API 请求失败:', error);
    
    // 如果后端代理失败，尝试直接请求DeepSeek API（可能会遇到CORS限制）
    try {
      console.log('尝试直接请求DeepSeek API...');
      const directResponse = await axios.post(
        DEEPSEEK_API_URL,
        requestData,
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${DEEPSEEK_API_KEY}`
          }
        }
      );
      
      if (directResponse.data && directResponse.data.choices && directResponse.data.choices.length > 0) {
        const assistantMessage = directResponse.data.choices[0].message.content;
        messages.value.push({ role: 'assistant', content: assistantMessage });
      } else {
        messages.value.push({ role: 'assistant', content: '抱歉，我无法生成回复。请重试。' });
      }
      
    } catch (directError) {
      console.error('直接请求DeepSeek API也失败:', directError);
      
      // 添加错误消息
      let errorMessage = '抱歉，AI助手暂时无法回应。请稍后再试。';
      
      if (directError instanceof Error) {
        // 可能是CORS错误或网络错误
        if (directError.message.includes('Network Error') || directError.message.includes('CORS')) {
          errorMessage = 'API访问被阻止。这可能是由于CORS策略或网络连接问题，请确认后端服务已启动。';
        }
        
        if (axios.isAxiosError(directError) && directError.response) {
          const status = directError.response.status;
          if (status === 401) {
            errorMessage = 'API密钥无效或已过期，请联系管理员。';
          } else if (status === 429) {
            errorMessage = 'API请求次数已达上限，请稍后再试。';
          } else if (status >= 500) {
            errorMessage = 'DeepSeek服务器暂时不可用，请稍后再试。';
          }
        }
      }
      
      messages.value.push({ role: 'assistant', content: errorMessage });
      ElMessage.error('请求失败，请查看详细错误信息');
    }
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 自动滚动到底部
const scrollToBottom = () => {
  if (chatContainerRef.value) {
    chatContainerRef.value.scrollTop = chatContainerRef.value.scrollHeight;
  }
};

// 复制内容到剪贴板
const copyToClipboard = (text: string) => {
  navigator.clipboard.writeText(text)
    .then(() => {
      ElMessage.success('已复制到剪贴板');
    })
    .catch(err => {
      console.error('复制失败:', err);
      ElMessage.error('复制失败，请手动选择并复制');
    });
};

// 清空对话历史
const clearChat = () => {
  ElMessageBox.confirm(
    '确定要清空所有对话历史吗？此操作不可恢复。',
    '清空对话',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(() => {
      messages.value = [];
      ElMessage.success('对话已清空');
    })
    .catch(() => {
      // 用户取消操作
    });
};

// 聚焦输入框
const focusInput = () => {
  if (inputRef.value) {
    (inputRef.value as any).focus();
  }
};

onMounted(() => {
  focusInput();
});
</script>

<style scoped>
.ai-assistant-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  background-color: #f9fafc;
}

.chat-header {
  padding: 16px 0;
  border-bottom: 1px solid #eaeaea;
}

.chat-header h2 {
  margin: 0;
  font-size: 24px;
  color: #303133;
}

.api-notice {
  margin-top: 8px;
}

.model-selector {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-label {
  font-size: 14px;
  color: #606266;
}

.model-description {
  font-size: 13px;
  color: #909399;
  font-style: italic;
}

.model-info {
  margin-bottom: 20px;
  text-align: center;
}

.model-info h3 {
  margin: 0 0 8px;
  color: #409eff;
}

.model-info p {
  margin: 0;
  color: #606266;
}

.powered-by {
  font-size: 14px;
  color: #909399;
  font-weight: normal;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  margin-bottom: 20px;
}

.empty-chat {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.messages-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.message {
  display: flex;
  gap: 16px;
}

.user-message {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-avatar {
  flex-shrink: 0;
}

.message-content {
  background-color: #f5f7fa;
  padding: 12px 16px;
  border-radius: 12px;
  max-width: 80%;
  line-height: 1.5;
  box-shadow: 0 2px 4px rgba(0,0,0,0.05);
}

.user-message .message-content {
  background-color: #ecf5ff;
}

.message-role {
  font-weight: bold;
  margin-bottom: 8px;
  font-size: 14px;
  color: #409eff;
}

.user-message .message-role {
  color: #67c23a;
}

.message-text {
  word-break: break-word;
}

.message-text :deep(pre) {
  background-color: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}

.message-text :deep(code) {
  background-color: rgba(175, 184, 193, 0.2);
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: monospace;
}

.message-text :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.message-text :deep(a:hover) {
  text-decoration: underline;
}

.message-text :deep(p) {
  margin: 0.5em 0;
}

.message-text :deep(ul, ol) {
  margin: 0.5em 0;
  padding-left: 2em;
}

.message-actions {
  margin-top: 8px;
  text-align: right;
}

.loading-message {
  display: flex;
  gap: 16px;
}

.loading-message .message-content {
  min-width: 300px;
}

.chat-input {
  border-top: 1px solid #eaeaea;
  padding: 20px;
  margin-bottom: 20px;
  background-color: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
  gap: 8px;
}
</style> 