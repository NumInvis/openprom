import requests
import time
import sys

# 设置 UTF-8 编码
sys.stdout.reconfigure(encoding='utf-8')

print("等待服务器启动...")
time.sleep(3)

try:
    r = requests.get('http://localhost:8000', timeout=5)
    print(f"[OK] 状态码：{r.status_code}")
    print(f"[OK] Content-Type: {r.headers.get('content-type')}")
    print(f"[OK] 内容长度：{len(r.text)} 字节")
    print(f"\n前 300 个字符:")
    print(r.text[:300])
    
    # 检查是否包含关键元素
    if '<!DOCTYPE html>' in r.text:
        print("\n[OK] HTML 文档类型正确")
    if 'PORM' in r.text:
        print("[OK] 页面包含 PORM 标题")
    if 'styles.css' in r.text or 'app.js' in r.text:
        print("[OK] 页面引用了静态资源")
        
except Exception as e:
    print(f"[FAIL] 错误：{e}")
