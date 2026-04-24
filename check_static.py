import os

frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
print(f'Frontend 目录：{frontend_dir}')
print(f'目录存在：{os.path.exists(frontend_dir)}')

if os.path.exists(frontend_dir):
    print(f'文件列表：{os.listdir(frontend_dir)}')
    
    # 检查关键文件
    for filename in ['index.html', 'styles.css', 'app.js']:
        filepath = os.path.join(frontend_dir, filename)
        exists = os.path.exists(filepath)
        size = os.path.getsize(filepath) if exists else 0
        print(f'  {filename}: 存在={exists}, 大小={size} 字节')
