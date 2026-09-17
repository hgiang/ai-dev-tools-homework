cd /Users/dohg/Study/courses/aishippinglab/ai-dev-tools/ai-dev-tools-homework/03-deployment/agent-relay

# 1. dừng process nền (uvicorn, port-forward) nếu còn
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "port-forward svc/agent-relay" 2>/dev/null

# 2. Compose + container Q3  (-v xoá luôn volume pgdata)
docker compose down -v
docker rm -f relay 2>/dev/null

# 3. cluster kind
kind delete cluster --name agent-relay

# 4. image và layer cache không còn dùng
docker image rm agent-relay:local 2>/dev/null
docker system prune -f

# 5. file tạm trong repo (đều đã gitignore, xoá cho gọn)
rm -rf __pycache__ .pytest_cache agent-relay.db agent-relay.db-shm agent-relay.db-wal
rm -rf ../../.act

# 6. tắt VM Docker cho nhẹ máy
colima stop
