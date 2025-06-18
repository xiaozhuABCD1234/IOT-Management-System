<script setup lang="ts">
declare global {
  interface Window {
    _AMapSecurityConfig?: {
      securityJsCode: string;
    };
  }
}

import { onMounted, onUnmounted, ref, shallowRef, watch, type Ref } from "vue";
import AMapLoader from "@amap/amap-jsapi-loader";
import mqtt from "mqtt";
import { useConfigStore } from "@/stores/config";
import { ElNotification } from 'element-plus';
import gcoord from 'gcoord';

interface ExposedMonitorMap {
  toggleFenceDrawing: () => void;
  resetFences: () => void;
  showFence: Ref<boolean>;
}

const ConfigStore = useConfigStore();

interface Device {
  id: number;
  path: Array<[number, number]>; // 更明确的写法
  polyline: any;
  marker: any;
}

interface Fence {
  id: string;
  polygon: any;
  editor: any;
}

const mapRef = ref(null);
let map: any = null;
let AMap: any = null; // Store AMap instance
let mouseTool: any = null; // Store MouseTool instance
const devices = ref<Device[]>([]);
let mqttClient: mqtt.MqttClient | null = null;

// 围栏相关状态
const drawingFence = ref(false);
const showFence = ref(false);
const fences = shallowRef<Fence[]>([]); // Use shallowRef for objects that won't be deeply mutated

// MQTT配置
const MQTT_CONFIG = {
  url: ConfigStore.mqtturl,
  options: {
    clean: true,
    connectTimeout: 4000,
    clientId: ConfigStore.mqttclientid +
      Math.random().toString(16).substr(2, 8) + "map",
    username: ConfigStore.mqttuser,
    password: ConfigStore.mqttpwd,
  },
  topic: ConfigStore.mqtttopic,
};

// 解析MQTT消息
const parseMessage = (topic: string, payload: Buffer) => {
  const data = JSON.parse(payload.toString());
  const id = data.id;
  const sensors = data.sensors;
  return {
    id,
    lng: sensors[0].data.value[0],
    lat: sensors[0].data.value[1],
  };
};

// 创建设备地图元素
const createDevice = (AMap: any, id: number, lng: number, lat: number) => {
  const colors = ["#1890ff", "#52c41a", "#fadb14", "#ff4d4f", "#722ed1"];
  const color = colors[id % colors.length];

  // 创建轨迹线
  const polyline = new AMap.Polyline({
    path: [[lng, lat]],
    strokeColor: color,
    strokeWeight: 3,
    lineJoin: "round",
  });

  // 创建设备标记
  const marker = new AMap.Marker({
    position: [lng, lat],
    content: `
      <div class="device-marker" style="background: ${color}">
        ${id}
      </div>`,
    offset: new AMap.Pixel(-12, -12),
  });

  // 添加到地图
  map.add([polyline, marker]);

  return {
    id,
    path: [[lng, lat]] as Array<[number, number]>,
    polyline,
    marker,
  };
};

// 检查设备是否在围栏内
const checkFenceViolation = (deviceId: number, lng: number, lat: number) => {
  const point = new AMap.LngLat(lng, lat);
  let isViolating = false;
  for (const fence of fences.value) {
    if (fence.polygon.contains(point)) {
      isViolating = true;
      break;
    }
  }

  if (isViolating) {
    ElNotification({
      title: "围栏警告",
      message: `设备 ${deviceId} 已进入电子围栏区域！`,
      type: "warning",
      duration: 3000,
    });
  }
};

// 更新设备位置
const updateDevicePosition = (
  AMapInstance: any,
  msg: { id: number; lng: number; lat: number },
) => {
  let device = devices.value.find((d) => d.id === msg.id);

  // 转换坐标系 (WGS84 -> GCJ02)
  const gcjCoord = gcoord.transform([msg.lng, msg.lat], gcoord.WGS84, gcoord.GCJ02);
  const gcjLng = gcjCoord[0];
  const gcjLat = gcjCoord[1];

  if (!device) {
    device = createDevice(AMapInstance, msg.id, gcjLng, gcjLat);
    devices.value.push(device);
  } else {
    const newPath = [
      ...device.path,
      [gcjLng, gcjLat] as [number, number],
    ];
    device.path = newPath;
    device.polyline.setPath(newPath);
    device.marker.setPosition([gcjLng, gcjLat]);
  }

  // 检查围栏违规
  if (showFence.value && fences.value.length > 0) {
    checkFenceViolation(msg.id, gcjLng, gcjLat);
  }
};

// 应用围栏样式
const applyFenceStyle = (polygon: any) => {
  if (polygon) {
    polygon.setOptions({
      strokeColor: "#FF0000", 
      strokeWeight: 4,        
      strokeOpacity: 1.0,     
      fillColor: "#FF0000",   
      fillOpacity: 0.2,
      zIndex: 50,
      strokeStyle: "solid",   // 实线样式
      strokeDasharray: [0, 0], // 不使用虚线
      borderWeight: 1        // 边框粗细
    });
    // 强制刷新
    polygon.setPath(polygon.getPath());
  }
};

// 重置绘制状态
const resetDrawingState = () => {
  if (mouseTool) {
    try {
      mouseTool.off('draw'); // 移除所有draw事件监听器
      mouseTool.close(true);
      mouseTool = null;
    } catch (e) {
      console.warn('Error resetting drawing tool:', e);
    }
  }
  
  // 移除调试用的地图点击事件监听器
  if (map && clickHandler) {
    try {
      map.off('click', clickHandler);
      console.log('MonitorMap: Removed map click handler');
      // 不要设置clickHandler为null，因为可能需要重用该引用
    } catch (e) {
      console.warn('Error removing map click handler:', e);
    }
  }
  
  drawingFence.value = false;
};

// 全局保存点击事件处理函数，以便后续能正确移除
let clickHandler: any = null;

// 切换围栏绘制模式
const toggleFenceDrawing = () => {
  console.log('MonitorMap: toggleFenceDrawing called. Current drawingFence:', drawingFence.value);
  if (!AMap || !map) {
    console.log('MonitorMap: AMap or map not initialized.');
    return;
  }

  // 如果已经在绘制中，则停止绘制
  if (drawingFence.value) {
    console.log('MonitorMap: Stopping fence drawing.');
    // 停止绘制
    resetDrawingState();
    ElNotification({
      title: '停止绘制围栏',
      message: '电子围栏绘制已停止。',
      type: 'info',
      duration: 3000,
    });
    return;
  }

  // 开始绘制
  console.log('MonitorMap: Starting fence drawing.');
  drawingFence.value = true;
  
  // 确保mouseTool为空
  resetDrawingState();
  
  // 创建新的MouseTool实例
  mouseTool = new AMap.MouseTool(map);
  mouseTool.polygon({
    strokeColor: "#FF0000", // 鲜红色边框
    strokeWeight: 4,        // 加粗边框
    strokeOpacity: 1.0,     // 完全不透明的边框
    fillColor: "#FF0000",   // 红色填充
    fillOpacity: 0.2,       // 降低填充透明度
    zIndex: 50,
    strokeStyle: "solid"    // 实线样式
  });
  
  // 绘制完成事件监听
  const drawListener = (event: any) => {
    console.log('MonitorMap: Draw event triggered, resetting draw mode.');
    
    // 立即重置绘制状态
    resetDrawingState();
    
    const newPolygon = event.obj;
    
    // 确保绘制完成后保持相同的样式
    applyFenceStyle(newPolygon);
    
    const fenceId = `fence-${Date.now()}`;
    const editor = new AMap.PolyEditor(map, newPolygon);
    
    // 配置编辑器样式 - 使用on方法而不是addListener
    editor.on('adjust', () => {
      // 当编辑完成时，确保样式保持一致
      applyFenceStyle(newPolygon);
      console.log('MonitorMap: Fence adjusted');
    });
    
    editor.on('end', () => {
      // 编辑结束时，重新应用样式
      applyFenceStyle(newPolygon);
      console.log('MonitorMap: Editor ended');
    });
    
    editor.open();

    fences.value = [...fences.value, { id: fenceId, polygon: newPolygon, editor }];
    console.log('MonitorMap: Fence drawn. New fences array:', fences.value);
    
    // 延迟一点时间再应用一次样式，确保红线可见
    setTimeout(() => {
      applyFenceStyle(newPolygon);
    }, 100);
    
    ElNotification({
      title: '围栏创建成功',
      message: `已创建新围栏 (ID: ${fenceId})`,
      type: 'success',
      duration: 3000,
    });
  };
  
  // 添加事件监听
  mouseTool.on('draw', drawListener);
  
  // 监听地图点击事件，用于调试
  clickHandler = (e: any) => {
    console.log('Map clicked while drawing fence:', e.lnglat.getLng(), e.lnglat.getLat());
  };
  map.on('click', clickHandler);
  
  // 在一段时间后检查绘制状态，如果仍在绘制中则提示用户
  setTimeout(() => {
    if (drawingFence.value) {
      console.log('MonitorMap: Still in drawing mode after 30 seconds');
    }
  }, 30000);
  
  ElNotification({
    title: '开始绘制围栏',
    message: '请在地图上点击绘制多边形，双击完成绘制。',
    type: 'info',
    duration: 5000,
  });
};

// 重置所有围栏
const resetFences = () => {
  console.log('MonitorMap: resetFences called. Current fences before clear:', fences.value.length);
  
  // 先确保绘制模式已关闭
  resetDrawingState();
  
  fences.value.forEach(fence => {
    if (fence.editor) {
      try {
        // 先移除事件监听器
        try {
          fence.editor.off && fence.editor.off('adjust');
          fence.editor.off && fence.editor.off('end');
        } catch (e) {
          console.warn("Editor event cleanup error:", e);
        }
        
        fence.editor.close();
      } catch (e) {
        console.warn("Editor cleanup error:", e);
      }
      fence.editor = null;
    }
    if (map && !map.isDestroyed()) {
      try {
        map.remove(fence.polygon);
      } catch (e) {
        console.warn("Polygon removal error:", e);
      }
    }
    try {
      fence.polygon?.destroy();
    } catch (e) {
      console.warn("Polygon destroy error:", e);
    }
    fence.polygon = null;
  });
  fences.value = [];
  showFence.value = false;
  console.log('MonitorMap: Fences cleared. Current fences after clear:', fences.value.length);
  ElNotification({
    title: '围栏已重置',
    message: '所有电子围栏已清除。',
    type: 'info',
    duration: 3000,
  });
};

// 监听 showFence 变化，控制围栏的显示/隐藏
watch(showFence, (newVal) => {
  console.log('MonitorMap: showFence watch triggered. New value:', newVal);
  fences.value.forEach(fence => {
    if (fence.polygon) {
      fence.polygon.setVisible(newVal);
      if (newVal) {
        // 当显示围栏时，重新应用样式确保红线可见
        applyFenceStyle(fence.polygon);
      }
      console.log(`MonitorMap: Fence ${fence.id} visibility set to ${newVal}. Current visible: ${fence.polygon.getVisible()}`);
    }
  });
});

onMounted(async () => {
  window._AMapSecurityConfig = {
    securityJsCode: ConfigStore.securityJsCode,
  };

  AMapLoader.load({
    key: ConfigStore.key,
    version: "2.0",
    plugins: ["AMap.Polyline", "AMap.Marker", "AMap.MouseTool", "AMap.PolyEditor"],
  }).then((AMapInstance) => {
    AMap = AMapInstance; // Store AMap instance
    map = new AMap.Map(mapRef.value, {
      viewMode: "3D",
      mapStyle: "amap://styles/normal",
      zoom: 17,
      center: [121.891751, 30.902079],
    });
    
    // 自定义PolyEditor样式
    AMap.PolyEditor.prototype._createNodesMarker = function(Polygon, point, idx) {
      const marker = new AMap.Marker({
        map: map,
        position: point,
        content: `<div style="background-color:white;width:10px;height:10px;border:2px solid #FF0000;border-radius:50%"></div>`,
        offset: new AMap.Pixel(-5, -5),
        zIndex: 200,
        cursor: 'move',
        extData: {
          isNode: true,
          index: idx
        }
      });
      return marker;
    };
    
    // 自定义中间节点样式
    AMap.PolyEditor.prototype._createMidMarker = function(Polygon, point, idx) {
      const marker = new AMap.Marker({
        map: map,
        position: point,
        content: `<div style="background-color:white;width:8px;height:8px;border:2px solid #FF0000;border-radius:50%"></div>`,
        offset: new AMap.Pixel(-4, -4),
        zIndex: 195,
        cursor: 'pointer',
        extData: {
          isMid: true,
          index: idx
        }
      });
      return marker;
    };
    
    // 地图加载完成事件
    map.on('complete', () => {
      console.log('MonitorMap: Map loading completed.');
      // 确保在地图加载完成后应用围栏样式
      setTimeout(() => {
        // 检查并应用围栏样式
        if (fences.value.length > 0) {
          console.log('MonitorMap: Applying fence styles to', fences.value.length, 'existing fences');
          fences.value.forEach(fence => {
            if (fence.polygon) {
              applyFenceStyle(fence.polygon);
            }
          });
        }
        
        // 确保初始状态正确
        drawingFence.value = false;
        if (mouseTool) {
          console.log('MonitorMap: Cleaning up orphaned mouseTool');
          resetDrawingState();
        }
      }, 500);
    });
    
    // 监听地图右键点击事件，用于退出绘制模式
    map.on('rightclick', () => {
      if (drawingFence.value) {
        console.log('MonitorMap: Right-click detected, stopping draw mode');
        resetDrawingState();
        ElNotification({
          title: '绘制已取消',
          message: '通过右键点击取消了围栏绘制',
          type: 'info',
          duration: 3000,
        });
      }
    });
    
    mqttClient = mqtt.connect(MQTT_CONFIG.url, MQTT_CONFIG.options);

    mqttClient.on("connect", () => {
      mqttClient!.subscribe(MQTT_CONFIG.topic);
    });

    mqttClient.on("message", (topic, payload) => {
      const msg = parseMessage(topic, payload);
      updateDevicePosition(AMap, msg);
    });
  }).catch(console.error);
});

onUnmounted(() => {
  console.log('MonitorMap: Component unmounted. Starting cleanup.');
  if (mqttClient) {
    mqttClient.unsubscribe(MQTT_CONFIG.topic);
    mqttClient.end(true);
    mqttClient = null;
  }

  devices.value.forEach((device) => {
    try {
      if (map && !map.isDestroyed()) {
        map.remove([device.polyline, device.marker]);
      }
      device.polyline?.destroy();
      device.marker?.destroy();
    } catch (e) {
      console.warn("Cleanup error:", e);
    } finally {
      device.polyline = null;
      device.marker = null;
    }
  });
  devices.value = [];

  // 确保先重置绘制状态
  resetDrawingState();

  fences.value.forEach(fence => {
    if (fence.editor) {
      try {
        // 先移除事件监听器
        try {
          fence.editor.off && fence.editor.off('adjust');
          fence.editor.off && fence.editor.off('end');
        } catch (e) {
          console.warn("Editor event cleanup error:", e);
        }
        
        fence.editor.close();
      } catch (e) {
        console.warn("Editor cleanup error:", e);
      }
      fence.editor = null;
    }
    if (map && !map.isDestroyed()) {
      try {
        map.remove(fence.polygon);
      } catch (e) {
        console.warn("Polygon removal error:", e);
      }
    }
    try {
      fence.polygon?.destroy();
    } catch (e) {
      console.warn("Polygon destroy error:", e);
    }
    fence.polygon = null;
  });
  fences.value = [];

  try {
    if (mouseTool) {
      // 确保移除所有事件监听器
      mouseTool.off && mouseTool.off();
      mouseTool.close(true);
      mouseTool = null;
    }
  } catch (e) {
    console.warn("MouseTool cleanup error:", e);
  }

  try {
    if (map && !map.isDestroyed()) {
      // 确保所有事件监听器被移除
      if (clickHandler) {
        map.off('click', clickHandler);
        clickHandler = null;
      }
      map.off('rightclick');
      map.off('click');  // 移除所有点击监听器
      map.destroy();
      map = null;
    }
  } catch (e) {
    console.warn("Map destroy error:", e);
  }
  
  console.log('MonitorMap: Cleanup finished.');
});

defineExpose<ExposedMonitorMap>({
  toggleFenceDrawing,
  resetFences,
  showFence,
});
</script>

<template>
  <div class="map-container">
    <div ref="mapRef" style="width: 100%; height: 100%"></div>
    <div class="map-controls">
      <el-switch v-model="showFence" active-text="显示围栏区域" />
      <el-button 
        type="primary" 
        :class="{ 'active': drawingFence }"
        @click="toggleFenceDrawing"
      >
        {{ drawingFence ? '完成围栏' : '绘制电子围栏' }}
      </el-button>
      <el-button 
        type="info"
        @click="resetFences"
      >
        清除所有围栏
      </el-button>
    </div>
    
    <!-- 绘制模式提示 -->
    <div v-if="drawingFence" class="drawing-hint">
      <el-alert
        title="正在绘制围栏"
        type="warning"
        description="点击地图添加围栏点，双击结束绘制，右键点击取消绘制"
        :closable="false"
        show-icon
      />
    </div>
  </div>
</template>

<style lang="css" scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 98vh;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  background-color: rgba(255, 255, 255, 0.0);
}

.map-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  display: flex;
  gap: 10px;
  align-items: center;
}

.drawing-hint {
  position: absolute;
  top: 60px;
  left: 50%;
  transform: translateX(-50%);
  width: 80%;
  max-width: 500px;
  z-index: 1000;
}

.active {
  background-color: #E6A23C;
  border-color: #E6A23C;
}
</style>

<style>
.device-marker {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border: 2px solid white;
}
</style>
