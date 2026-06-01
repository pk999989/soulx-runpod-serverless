import runpod

def handler(job):
    data = job["input"]
    text = data.get("text", "")
    # 這裡呼叫 SoulX 生成 wav
    return {
        "ok": True,
        "message": "SoulX endpoint received job",
        "text": text
    }

runpod.serverless.start({"handler": handler})
