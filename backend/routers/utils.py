from fastapi import APIRouter, HTTPException, Depends, Body, Request
from fastapi.responses import JSONResponse
import httpx
import os
import logging
from typing import Dict, Any, List
from utils import color

router = APIRouter()

# 配置日志
logger = logging.getLogger("deepseek_proxy")
logger.setLevel(logging.INFO)

@router.get("/generate_colors/{n}")
async def generate_colors(n: int) -> list[str]:
    return color.generate_colors(n)

@router.post("/proxy/deepseek", tags=["utils"])
async def proxy_deepseek_api(request: Request):
    """
    代理转发请求到DeepSeek API，解决前端CORS问题
    """
    try:
        # 从请求中读取数据
        data = await request.json()
        logger.info(f"接收到DeepSeek API代理请求: {data.get('model', '未指定模型')}")
        
        # 获取DeepSeek API密钥（应该通过环境变量或安全方式获取）
        api_key = os.environ.get("DEEPSEEK_API_KEY", "sk-bec0a15f8ede4672a6869bc4b1e4e9c5")
        
        # 设置DeepSeek API的URL
        model = data.get('model', 'deepseek-r1')
        
        # 根据模型选择合适的API端点
        if model.startswith('deepseek-r1'):
            deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        else:
            deepseek_url = "https://api.deepseek.com/v1/chat/completions"
            
        logger.info(f"使用API端点: {deepseek_url}, 模型: {model}")
        
        # 使用httpx进行API请求
        async with httpx.AsyncClient(timeout=60.0) as client:
            logger.info(f"转发请求到DeepSeek API: {deepseek_url}")
            
            response = await client.post(
                deepseek_url,
                json=data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            
            # 检查响应状态
            if response.status_code != 200:
                logger.error(f"DeepSeek API返回错误: {response.status_code}, {response.text}")
                return JSONResponse(
                    content={"error": f"DeepSeek API返回错误: {response.status_code}", "details": response.text},
                    status_code=response.status_code
                )
            
            # 解析响应数据
            try:
                response_data = response.json()
                logger.info("成功从DeepSeek API获取响应")
                
                # 返回DeepSeek API的响应
                return JSONResponse(
                    content=response_data,
                    status_code=response.status_code
                )
            except Exception as e:
                logger.error(f"解析DeepSeek API响应失败: {str(e)}")
                return JSONResponse(
                    content={"error": "解析DeepSeek API响应失败", "details": str(e)},
                    status_code=500
                )
    
    except httpx.RequestError as e:
        logger.error(f"DeepSeek API请求错误: {str(e)}")
        raise HTTPException(status_code=503, detail=f"DeepSeek API请求错误: {str(e)}")
    
    except Exception as e:
        logger.error(f"代理请求失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"代理请求失败: {str(e)}")
