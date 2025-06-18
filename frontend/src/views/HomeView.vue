<script setup lang="ts">
import MonitorMap from "@/components/map/MonitorMap.vue";
import UWBMap from "@/components/map/UWBMap.vue";
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue';

// 存储键名
const STORAGE_KEY = 'map-split-percentage';

// 从localStorage获取上次保存的百分比，默认为65%
const getInitialPercentage = (): number => {
  const savedValue = localStorage.getItem(STORAGE_KEY);
  if (savedValue) {
    const percentage = parseFloat(savedValue);
    return !isNaN(percentage) && percentage >= 10 && percentage <= 90 
      ? percentage 
      : 65;
  }
  return 65; // 默认左侧占65%，右侧占35%
};

// 左侧地图占的比例
const leftSizePercentage = ref(getInitialPercentage());
const isDragging = ref(false);
const container = ref<HTMLDivElement | null>(null);

// 计算右侧地图的宽度，并根据宽度调整布局样式
const rightMapWidth = computed(() => {
  return 100 - leftSizePercentage.value;
});

// 计算右侧地图的布局模式 - 当宽度小于30%时切换为紧凑模式
const isRightMapCompact = computed(() => {
  return rightMapWidth.value < 30;
});

// 处理拖动事件
const handleMouseDown = (e: MouseEvent) => {
  isDragging.value = true;
  // 添加拖动类，用于修改全局光标样式
  document.body.classList.add('resizing');
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
  // 防止选择文本
  e.preventDefault();
};

// 处理鼠标移动
const handleMouseMove = (e: MouseEvent) => {
  if (!isDragging.value || !container.value) return;
  
  const containerRect = container.value.getBoundingClientRect();
  const containerWidth = containerRect.width;
  const mouseX = e.clientX - containerRect.left;
  
  // 计算左侧地图占的百分比（限制在10%到90%之间）
  let percentage = (mouseX / containerWidth) * 100;
  percentage = Math.max(10, Math.min(90, percentage));
  
  // 设置宽度百分比，使用整数值减少重绘次数
  leftSizePercentage.value = Math.round(percentage * 10) / 10;
};

// 处理鼠标松开
const handleMouseUp = () => {
  isDragging.value = false;
  // 移除拖动类
  document.body.classList.remove('resizing');
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  
  // 保存当前分割比例到localStorage
  localStorage.setItem(STORAGE_KEY, leftSizePercentage.value.toString());
};

// 组件挂载和卸载时的清理
onMounted(() => {
  // 监听窗口大小变化，更新UI
  window.addEventListener('resize', handleResize);
  
  // 清理，确保不会留下resizing类
  document.body.classList.remove('resizing');
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  document.removeEventListener('mousemove', handleMouseMove);
  document.removeEventListener('mouseup', handleMouseUp);
  document.body.classList.remove('resizing');
});

const handleResize = () => {
  // 窗口大小变化时，可能需要重新调整地图组件
};
</script>

<template>
  <div class="container" ref="container">
    <div class="map-container">
      <!-- 左侧地图 -->
      <div class="left-map" :style="{ width: `${leftSizePercentage}%` }">
        <MonitorMap />
      </div>
      
      <!-- 可拖动分隔条 -->
      <div 
        class="resize-bar" 
        :class="{ 'active': isDragging }"
        @mousedown="handleMouseDown"
        title="拖动调整两侧地图的大小"
      >
        <div class="resize-bar-handle"></div>
      </div>
      
      <!-- 右侧地图 - 添加紧凑布局类，移除过渡动画 -->
      <div 
        class="right-map" 
        :class="{ 'compact-mode': isRightMapCompact }"
        :style="{ width: `${rightMapWidth}%` }"
      >
        <UWBMap />
      </div>
    </div>
  </div>
</template>

<style scoped>
.container {
  position: relative;
  width: 100%;
  height: calc(100vh - 60px); /* 减去顶部导航栏的高度 */
  overflow: hidden;
}

.map-container {
  display: flex;
  width: 100%;
  height: 100%;
  position: relative;
  background-color: #f8f9fa;
}

.left-map, .right-map {
  height: 100%;
  position: relative;
  overflow: hidden;
  flex-shrink: 0; /* 防止被压缩 */
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  margin: 4px;
  /* 移除宽度过渡动画，防止拖动时的晃动 */
  will-change: width; /* 提示浏览器这个属性会变化，优化渲染 */
}

/* 右侧地图紧凑模式样式 */
.right-map.compact-mode :deep(.controls) {
  flex-direction: column;
  width: auto;
  max-width: 180px;
  padding: 10px;
}

.right-map.compact-mode :deep(.controls .el-button) {
  margin: 4px 0;
  padding: 8px;
  font-size: 12px;
}

.right-map.compact-mode :deep(.controls .el-switch) {
  margin: 4px 0;
  transform: scale(0.9);
}

.right-map.compact-mode :deep(.controls .tip) {
  font-size: 11px;
  margin-top: 6px;
}

.right-map.compact-mode :deep(.distance-panel) {
  width: auto;
  max-width: 90%;
  padding: 10px;
}

.right-map.compact-mode :deep(.distance-panel h3) {
  font-size: 14px;
  margin-bottom: 8px;
}

.right-map.compact-mode :deep(.distance-inputs) {
  flex-direction: column;
}

.right-map.compact-mode :deep(.input-column) {
  width: 100%;
  margin-bottom: 8px;
}

/* 分隔条样式 */
.resize-bar {
  width: 8px; /* 更窄的分隔条 */
  height: 100%;
  background-color: #e9ecef;
  cursor: col-resize;
  flex-shrink: 0; /* 防止被压缩 */
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 100;
  margin: 0;
  position: relative;
  transition: background-color 0.2s;
  /* 移除宽度过渡动画 */
}

.resize-bar:hover {
  background-color: #dee2e6;
}

.resize-bar.active {
  background-color: #adb5bd;
}

.resize-bar-handle {
  width: 4px;
  height: 40px;
  background-color: #adb5bd;
  border-radius: 2px;
  transition: background-color 0.2s, height 0.2s;
}

.resize-bar:hover .resize-bar-handle {
  background-color: #6c757d;
  height: 60px;
}

.resize-bar.active .resize-bar-handle {
  background-color: #495057;
  height: 80px;
}
</style>

<style>
/* 全局样式 */
body.resizing {
  cursor: col-resize !important;
  user-select: none;
}

body.resizing * {
  cursor: col-resize !important;
}

/* 为UWB地图组件中的控制面板添加自适应样式 */
.el-button {
  transition: all 0.2s;
}

.el-switch {
  transition: all 0.2s;
}

/* 拖动分割线时禁用所有过渡效果 */
body.resizing .left-map,
body.resizing .right-map,
body.resizing .resize-bar {
  transition: none !important;
  animation: none !important;
}

/* 优化P5地图组件渲染 */
.p5-canvas-container canvas {
  will-change: transform;
}
</style>
