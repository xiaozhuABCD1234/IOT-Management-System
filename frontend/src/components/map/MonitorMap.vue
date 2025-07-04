<script setup lang="ts">
declare global {
  interface Window {
    _AMapSecurityConfig?: {
      securityJsCode: string;
    };
  }
}

import { onMounted, onUnmounted, ref } from "vue";
import AMapLoader from "@amap/amap-jsapi-loader";
import mqtt from "mqtt";
import { useConfigStore } from "@/stores/config";

const ConfigStore = useConfigStore();

interface Device {
  id: number;
  path: Array<[number, number]>; // 更明确的写法
  polyline: any;
  marker: any;
}

const mapRef = ref(null);
let map: any = null;
const devices = ref<Device[]>([]);
let mqttClient: mqtt.MqttClient | null = null;

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
    path: [[lng, lat]] as Array<[number, number]>, // 添加类型断言
    polyline,
    marker,
  };
};
import gcoord from 'gcoord';
// 更新设备位置
const updateDevicePosition = (
  AMap: any,
  msg: { id: number; lng: number; lat: number },
) => {
  let device = devices.value.find((d) => d.id === msg.id);

  if (!device) {
    // 创建新设备
    const gcjCoord = gcoord.transform([msg.lng, msg.lat], gcoord.WGS84, gcoord.GCJ02);
    const gcjLng = gcjCoord[0];
    const gcjLat = gcjCoord[1];
    device = createDevice(AMap, msg.id, gcjLng, gcjLat); // 用转换后的GCJ坐标创建设备
    devices.value.push(device);
  } else {
    // 更新现有设备时添加类型断言
    const gcjCoord = gcoord.transform([msg.lng, msg.lat], gcoord.WGS84, gcoord.GCJ02);
    const gcjLng = gcjCoord[0];
    const gcjLat = gcjCoord[1];
    const newPath = [
      ...device.path,
      [gcjLng, gcjLat] as [number, number], // 确保每个点都是元组，使用转换后的GCJ坐标
    ];
    device.path = newPath;
    device.polyline.setPath(newPath);
    device.marker.setPosition([gcjLng, gcjLat]); // 使用转换后的GCJ坐标更新位置
  }
};

onMounted(async () => {
  // 高德地图安全配置
  window._AMapSecurityConfig = {
    securityJsCode: ConfigStore.securityJsCode,
  };

  // 初始化地图
  AMapLoader.load({
    key: ConfigStore.key,
    version: "2.0",
    plugins: ["AMap.Polyline", "AMap.Marker"],
  }).then((AMap) => {
    map = new AMap.Map(mapRef.value, {
      viewMode: "3D",
      mapStyle: "amap://styles/normal",
      zoom: 17,
      center: [121.891751, 30.902079],
    });

    // 连接MQTT
    mqttClient = mqtt.connect(MQTT_CONFIG.url, MQTT_CONFIG.options);

    mqttClient.on("connect", () => {
      mqttClient!.subscribe(MQTT_CONFIG.topic);
    });

    mqttClient.on("message", (topic, payload) => {
      const msg = parseMessage(topic, payload);
      // console.log(msg);
      updateDevicePosition(AMap, msg);
    });
  }).catch(console.error);
});

onUnmounted(() => {
  // 清理MQTT连接
  if (mqttClient) {
    mqttClient.unsubscribe(MQTT_CONFIG.topic); // 显式取消订阅
    mqttClient.end(true); // 强制立即关闭连接
    mqttClient = null;
  }

  // 清理地图覆盖物
  devices.value.forEach((device) => {
    try {
      // 安全移除覆盖物（在map存在且未被销毁时）
      if (map && !map.isDestroyed()) {
        map.remove([device.polyline, device.marker]);
      }
      // 手动销毁覆盖物实例
      device.polyline?.destroy();
      device.marker?.destroy();
    } catch (e) {
      console.warn("Cleanup error:", e);
    } finally {
      // 清除引用
      device.polyline = null;
      device.marker = null;
    }
  });
  devices.value = []; // 清空设备数组

  // 销毁地图实例
  try {
    if (map && !map.isDestroyed()) {
      map.destroy();
      map = null;
    }
  } catch (e) {
    console.warn("Map destroy error:", e);
  }
});
</script>

<template>
  <div class="map-container">
    <div ref="mapRef" style="width: 100%; height: 100%"></div>
  </div>
</template>

<style lang="css" scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  background-color: rgba(255, 255, 255, 0.0);
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
